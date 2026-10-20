"""Status agent diturunkan dari status task (Bagian 7.3). Tidak ada status yang disimpan atau disimulasikan."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Task
from app.tasks.catalog import ROLES

RUNNING_STATUS = {
    "manager": "planning", "analyst": "planning", "developer": "working", "qa": "testing", "reviewer": "reviewing",
    "reporter": "working", "market_research": "researching", "lead_generation": "prospecting",
    "content_promotion": "creating_content", "sales_client_relations": "client_followup",
}
COMPLETED_VISIBLE_FOR = timedelta(seconds=60)


def _naive(dt):
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo else dt


def _recovered(mine: list[Task], failed: Task) -> bool:
    """Kegagalan tidak lagi dianggap error jika ada task lain pada role yang sama selesai setelahnya."""
    done = [t.finished_at for t in mine if t.status == "completed" and t.finished_at]
    return bool(done) and failed.finished_at is not None and _naive(max(done)) > _naive(failed.finished_at)


def agent_statuses(session: Session, project_id: str | None = None) -> list[dict]:
    q = select(Task)
    if project_id:
        q = q.where(Task.project_id == project_id)
    tasks = session.scalars(q.order_by(Task.updated_at.desc())).all()
    now = _naive(utcnow())

    out = []
    for role, department in ROLES.items():
        mine = [t for t in tasks if t.role == role]
        by = lambda st: next((t for t in mine if t.status == st), None)  # noqa: E731 (terbaru dulu)
        queued = sum(1 for t in mine if t.status == "queued")
        current = None

        if (t := by("running")):
            status, current = RUNNING_STATUS[role], t
        elif (t := by("pending_approval")):
            status, current = "awaiting_approval", t
        elif (t := by("blocked")):
            status, current = "blocked", t
        elif (t := by("failed")) and not _recovered(mine, t):
            status, current = "error", t
        elif (t := by("completed")) and t.finished_at and now - _naive(t.finished_at) <= COMPLETED_VISIBLE_FOR:
            status, current = "completed", t
        else:
            status = "idle"

        out.append({"role": role, "department": department, "status": status, "queued": queued,
                    "current_task_id": current.id if current else None,
                    "current_task_title": current.title if current else None})
    return out
