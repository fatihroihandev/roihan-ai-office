"""Mesin status task (Bagian 12.1). Semua perubahan status wajib lewat `change_status`."""
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Task, TaskEvent

STATUSES = ["draft", "pending_approval", "queued", "running", "blocked", "completed", "failed", "cancelled", "interrupted"]

ALLOWED: dict[str, set[str]] = {
    "draft": {"pending_approval", "queued", "cancelled"},
    "pending_approval": {"queued", "cancelled"},
    # queued/blocked/failed/interrupted -> pending_approval: approval lama habis/terpakai dan tindakan berisiko perlu approval baru
    "queued": {"running", "blocked", "cancelled", "pending_approval"},
    "running": {"completed", "failed", "blocked", "interrupted", "cancelled"},
    "blocked": {"queued", "cancelled", "pending_approval"},
    "interrupted": {"queued", "failed", "cancelled", "pending_approval"},
    "failed": {"queued", "cancelled", "pending_approval"},
    "completed": set(),
    "cancelled": set(),
}
TERMINAL = {"completed", "cancelled"}

# Nama event WebSocket per status tujuan (Bagian 16.2)
EVENT_TYPE = {"running": "task.started"}


class InvalidTransition(ValueError):
    pass


def add_event(session: Session, task: Task, type_: str, *, from_status=None, to_status=None, reason=None,
              actor="system", payload=None) -> TaskEvent:
    ev = TaskEvent(task_id=task.id, project_id=task.project_id, type=type_, from_status=from_status,
                   to_status=to_status, reason=reason, actor=actor, payload=payload)
    session.add(ev)
    return ev


def change_status(session: Session, task: Task, to: str, *, reason: str | None = None, actor: str = "system",
                  payload: dict | None = None) -> Task:
    frm = task.status
    if to not in ALLOWED.get(frm, set()):
        raise InvalidTransition(f"Transisi {frm} -> {to} tidak diizinkan")
    task.status = to
    now = utcnow()
    if to == "running" and task.started_at is None:
        task.started_at = now
    if to in {"completed", "failed", "cancelled"}:
        task.finished_at = now
    elif to in {"queued", "running"}:
        task.finished_at = None
    task.blocked_reason = reason if to == "blocked" else None
    task.updated_at = now
    add_event(session, task, EVENT_TYPE.get(to, f"task.{to}"), from_status=frm, to_status=to, reason=reason,
              actor=actor, payload=payload)
    return task
