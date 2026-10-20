import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import (
    Approval, CodeReview, Execution, Project, RoutingDecision, Task, TaskAttempt, TaskEvent, TestResult, TestRun,
)
from app.reporting.builder import build_project_report, build_task_report, next_steps, project_summary, unresolved_issues
from app.schemas.tasks import PlanBody, TaskCreate, TaskDetail, TaskOut, TestRunOut
from app.security import require_token
from app.tasks import service
from app.tasks.catalog import ROLES
from app.tasks.service import TaskError
from app.tasks.state import STATUSES, InvalidTransition, change_status

router = APIRouter(prefix="/api", tags=["tasks"], dependencies=[Depends(require_token)])


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _project_or_404(session: Session, project_id: str) -> Project:
    p = session.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise HTTPException(404, "Proyek tidak ditemukan")
    return p


def _task_or_404(session: Session, task_id: str) -> Task:
    t = session.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "Task tidak ditemukan")
    return t


def _ttl(request: Request) -> int:
    return request.app.state.settings.approval_ttl_hours


def _guard(fn):
    try:
        return fn()
    except (TaskError, InvalidTransition) as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post("/projects/{project_id}/plan", response_model=TaskOut, status_code=201)
def create_plan(project_id: str, body: PlanBody, request: Request, session: SessionDep):
    """Manager menyusun rencana: dibuat sebagai task `planning` yang dikerjakan worker."""
    _project_or_404(session, project_id)
    t = service.create_task(session, project_id=project_id, title=f"Susun rencana: {body.goal[:80]}",
                            description=body.goal, role="manager", action_type="planning",
                            acceptance_criteria=["Rencana berisi task terukur dengan acceptance criteria"],
                            factors={"complexity": 3, "uncertainty": 3, "reasoning": 4})
    service.queue_task(session, t, ttl_hours=_ttl(request))
    session.commit()
    return t


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, session: SessionDep):
    _project_or_404(session, body.project_id)
    t = _guard(lambda: service.create_task(session, **body.model_dump()))
    session.commit()
    return t


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(session: SessionDep, project_id: str | None = None,
               status_filter: Annotated[str | None, Query(alias="status")] = None, role: str | None = None,
               limit: Annotated[int, Query(ge=1, le=500)] = 200, offset: Annotated[int, Query(ge=0)] = 0):
    if status_filter and status_filter not in STATUSES:
        raise HTTPException(422, "Status tidak dikenal")
    if role and role not in ROLES:
        raise HTTPException(422, "Role tidak dikenal")
    q = select(Task)
    if project_id:
        q = q.where(Task.project_id == project_id)
    if status_filter:
        q = q.where(Task.status == status_filter)
    if role:
        q = q.where(Task.role == role)
    return list(session.scalars(q.order_by(Task.created_at.desc(), Task.id).limit(limit).offset(offset)))


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(task_id: str, session: SessionDep):
    t = _task_or_404(session, task_id)
    base = TaskOut.model_validate(t).model_dump()
    return TaskDetail(
        **base, result=t.result, depends_on=service.dependency_ids(session, t.id),
        attempts=list(session.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id).order_by(TaskAttempt.number))),
        events=list(session.scalars(select(TaskEvent).where(TaskEvent.task_id == t.id).order_by(TaskEvent.seq))),
        routing=list(session.scalars(select(RoutingDecision).where(RoutingDecision.task_id == t.id)
                                     .order_by(RoutingDecision.created_at))),
        executions=list(session.scalars(select(Execution).where(Execution.task_id == t.id).order_by(Execution.created_at))),
        test_runs=[
            TestRunOut.model_validate(r).model_copy(update={"results": [
                x for x in session.scalars(select(TestResult).where(TestResult.test_run_id == r.id).order_by(TestResult.created_at))]})
            for r in session.scalars(select(TestRun).where(TestRun.task_id == t.id).order_by(TestRun.created_at))
        ],
        approvals=list(session.scalars(select(Approval).where(Approval.task_id == t.id).order_by(Approval.created_at))),
        reviews=[r for r in session.scalars(select(CodeReview).where(CodeReview.project_id == t.project_id).order_by(CodeReview.created_at))
                 if r.task_id == t.id or t.id in (r.reviewed_task_ids or [])],
    )


@router.post("/tasks/{task_id}/queue", response_model=TaskOut)
def queue_task(task_id: str, request: Request, session: SessionDep):
    t = _guard(lambda: service.queue_task(session, _task_or_404(session, task_id), ttl_hours=_ttl(request)))
    session.commit()
    return t


@router.post("/projects/{project_id}/tasks/queue-drafts", response_model=list[TaskOut])
def queue_drafts(project_id: str, request: Request, session: SessionDep):
    _project_or_404(session, project_id)
    tasks = _guard(lambda: service.queue_drafts(session, project_id, ttl_hours=_ttl(request)))
    session.commit()
    return tasks


@router.post("/tasks/{task_id}/retry", response_model=TaskOut)
def retry_task(task_id: str, request: Request, session: SessionDep):
    t = _guard(lambda: service.requeue_task(session, _task_or_404(session, task_id), ttl_hours=_ttl(request)))
    session.commit()
    return t


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(task_id: str, request: Request, session: SessionDep):
    t = _task_or_404(session, task_id)
    if t.status == "running":
        worker = getattr(request.app.state, "worker", None)
        if worker is not None and await worker.cancel_running(task_id):
            for _ in range(50):  # tunggu worker menuntaskan pembatalan (maks. ~5 detik)
                session.expire_all()
                if session.get(Task, task_id).status != "running":
                    break
                await asyncio.sleep(0.1)
            return session.get(Task, task_id)
        # Tidak ada worker yang memegang task ini (yatim): batalkan langsung
        _guard(lambda: change_status(session, t, "cancelled", reason="cancelled_orphan", actor="ceo"))
    else:
        _guard(lambda: service.cancel_task(session, t))
    session.commit()
    return t


@router.get("/tasks/{task_id}/report")
def task_report(task_id: str, session: SessionDep):
    """Laporan task (Bagian 17): seluruh fakta berasal dari database dan dibuat saat diminta."""
    _task_or_404(session, task_id)
    markdown, facts = build_task_report(session, task_id)
    return {"task_id": task_id, "generated_at": utcnow().isoformat(), "markdown": markdown,
            "unresolved": unresolved_issues(facts), "next_steps": next_steps(facts)}


@router.get("/projects/{project_id}/report")
def project_report(project_id: str, session: SessionDep):
    project = _project_or_404(session, project_id)
    markdown, facts = build_project_report(session, project_id, project_name=project.name)
    return {"project_id": project_id, "generated_at": utcnow().isoformat(), "markdown": markdown,
            "summary": project_summary(facts), "tasks": len(facts)}


@router.get("/agents")
def agents(session: SessionDep, project_id: str | None = None):
    """Status agent diturunkan dari status task di backend (Bagian 7.3), bukan disimpan terpisah."""
    from app.tasks.agents import agent_statuses
    return agent_statuses(session, project_id)


@router.get("/worker")
def worker_status(request: Request, session: SessionDep):
    worker = getattr(request.app.state, "worker", None)
    counts = dict(session.execute(select(Task.status, func.count()).group_by(Task.status)).all())
    return {
        "enabled": request.app.state.settings.worker_enabled, "running": worker is not None,
        "current_task_id": worker.current_task_id if worker else None,
        "max_concurrent_tasks": request.app.state.settings.max_concurrent_tasks,
        "counts": {s: counts.get(s, 0) for s in STATUSES},
    }
