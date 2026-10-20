"""Operasi task: pembuatan, antrean, dependensi, dan transisi yang dipicu manusia atau worker."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.approvals import service as approvals
from app.db.base import utcnow
from app.db.models import Task, TaskDependency
from app.routing.scoring import category, difficulty_score, normalize_factors
from app.tasks.catalog import ACTION_RISK, ROLES, needs_approval, risk_for
from app.tasks.state import add_event, change_status


class TaskError(ValueError):
    pass


def create_task(session: Session, *, project_id: str, title: str, role: str, action_type: str,
                description: str = "", acceptance_criteria: list[str] | None = None,
                depends_on: list[str] | None = None, priority: int = 0, factors: dict | None = None,
                preferred_model: str | None = None, requires_tools: bool = False, max_retries: int = 2,
                created_by: str = "ceo", parent_task_id: str | None = None) -> Task:
    if role not in ROLES:
        raise TaskError(f"Role tidak dikenal: {role}")
    if action_type not in ACTION_RISK:
        raise TaskError(f"Jenis tindakan tidak dikenal: {action_type}")
    deps = list(dict.fromkeys(depends_on or []))
    for dep_id in deps:
        dep = session.get(Task, dep_id)
        if dep is None or dep.project_id != project_id:
            raise TaskError(f"Dependensi tidak valid: {dep_id}")

    norm = normalize_factors(factors)
    score = difficulty_score(norm)
    risk = risk_for(action_type)
    task = Task(
        project_id=project_id, parent_task_id=parent_task_id, title=title.strip(), description=description.strip(),
        role=role, action_type=action_type, priority=priority, acceptance_criteria=acceptance_criteria or [],
        risk_level=risk, requires_approval=needs_approval(risk), difficulty_factors=norm, difficulty_score=score,
        difficulty_category=category(score), preferred_model=preferred_model, requires_tools=requires_tools,
        max_retries=max_retries, created_by=created_by,
    )
    session.add(task)
    session.flush()
    for dep_id in deps:
        session.add(TaskDependency(task_id=task.id, depends_on_id=dep_id))
    add_event(session, task, "task.created", to_status="draft", actor=created_by,
              payload={"role": role, "action_type": action_type, "depends_on": deps})
    return task


def dependency_ids(session: Session, task_id: str) -> list[str]:
    return list(session.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task_id)))


def queue_task(session: Session, task: Task, actor: str = "ceo", ttl_hours: int = approvals.DEFAULT_TTL_HOURS) -> Task:
    """draft -> queued, atau pending_approval jika tindakan berisiko tinggi (Bagian 9.3)."""
    if task.status != "draft":
        raise TaskError(f"Hanya task berstatus draft yang dapat diantrekan (status sekarang: {task.status})")
    if task.requires_approval and not task.approved:
        change_status(session, task, "pending_approval", reason=f"risk_{task.risk_level}", actor=actor)
        approvals.open_approval(session, task, ttl_hours)
        return task
    return change_status(session, task, "queued", actor=actor)


def queue_drafts(session: Session, project_id: str, actor: str = "ceo", ttl_hours: int = approvals.DEFAULT_TTL_HOURS) -> list[Task]:
    drafts = session.scalars(select(Task).where(Task.project_id == project_id, Task.status == "draft")
                             .order_by(Task.created_at, Task.id)).all()
    return [queue_task(session, t, actor, ttl_hours) for t in drafts]


def requeue_task(session: Session, task: Task, actor: str = "ceo", ttl_hours: int = approvals.DEFAULT_TTL_HOURS) -> Task:
    """Retry manual: failed/blocked/interrupted -> queued dengan jatah retry otomatis yang baru.

    Tindakan berisiko tinggi tidak boleh diulang tanpa approval baru (approval sekali pakai): task kembali ke
    pending_approval dan meminta approval baru.
    """
    if task.status not in {"failed", "blocked", "interrupted"}:
        raise TaskError(f"Task berstatus {task.status} tidak dapat dicoba ulang")
    task.attempts_baseline = task.attempt_count
    task.available_at = utcnow()
    if task.requires_approval:
        change_status(session, task, "pending_approval", reason="manual_retry_needs_approval", actor=actor)
        approvals.open_approval(session, task, ttl_hours)
        return task
    return change_status(session, task, "queued", reason="manual_retry", actor=actor)


def cancel_task(session: Session, task: Task, actor: str = "ceo") -> Task:
    """Pembatalan task yang tidak sedang berjalan. Task running dibatalkan lewat worker."""
    if task.status == "running":
        raise TaskError("Task sedang berjalan; batalkan melalui worker")
    change_status(session, task, "cancelled", reason="cancelled_by_user", actor=actor)
    approvals.cancel_open(session, task.id, "task dibatalkan")
    return task


def retry_delay(base_s: float, retries_used: int) -> timedelta:
    return timedelta(seconds=min(300.0, base_s * (2 ** max(0, retries_used))))
