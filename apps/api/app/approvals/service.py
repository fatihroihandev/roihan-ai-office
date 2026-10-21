"""Approval Center (Bagian 12.5).

Aturan yang ditegakkan di sini (bukan di prompt):
  - approval terikat pada isi tindakan (sidik jari SHA-256); jika isi task berubah, approval tidak berlaku
  - sekali pakai: dikonsumsi saat task mulai berjalan; retry tindakan berisiko meminta approval baru
  - punya masa berlaku; yang kedaluwarsa tidak dapat dieksekusi
  - hanya manusia (CEO) yang dapat memutuskan; agent dan sistem tidak pernah dapat menyetujui
  - setiap keputusan tercatat di audit_logs (siapa, kapan, alasan, task)
"""
import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Approval, AuditLog, Task, TaskDependency
from app.tasks.state import add_event, change_status

HUMAN_ACTORS = {"ceo"}
DEFAULT_TTL_HOURS = 24


class ApprovalError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _naive(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo else dt


def task_payload(session: Session, task: Task) -> dict:
    """Isi tindakan yang disetujui. Perubahan pada salah satu field ini membatalkan approval."""
    deps = sorted(session.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task.id)))
    payload = {
        "title": task.title, "description": task.description, "role": task.role, "action_type": task.action_type,
        "risk_level": task.risk_level, "acceptance_criteria": list(task.acceptance_criteria or []), "depends_on": deps,
    }
    if task.params:      # parameter menentukan apa yang dilakukan (mis. prospek mana); hanya ikut jika ada agar approval lama tetap sah
        payload["params"] = task.params
    return payload


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def open_approval(session: Session, task: Task, ttl_hours: int = DEFAULT_TTL_HOURS, requested_by: str = "system") -> Approval:
    """Buat permintaan approval untuk task (atau kembalikan yang masih terbuka dan belum kedaluwarsa)."""
    now = _naive(utcnow())
    existing = session.scalars(select(Approval).where(Approval.task_id == task.id, Approval.status == "pending")).all()
    for a in existing:
        if _naive(a.expires_at) > now and a.payload_hash == fingerprint(task_payload(session, task)):
            return a
        a.status = "cancelled"
        a.decision_reason = "digantikan oleh permintaan baru"
    payload = task_payload(session, task)
    approval = Approval(task_id=task.id, project_id=task.project_id, action_type=task.action_type, risk_level=task.risk_level,
                        payload=payload, payload_hash=fingerprint(payload), requested_by=requested_by,
                        expires_at=utcnow() + timedelta(hours=ttl_hours))
    session.add(approval)
    session.flush()
    add_event(session, task, "approval.required", actor=requested_by,
              payload={"approval_id": approval.id, "risk_level": task.risk_level, "action_type": task.action_type,
                       "expires_at": approval.expires_at.isoformat()})
    return approval


def _audit(session: Session, action: str, approval: Approval, actor: str, reason: str | None) -> None:
    session.add(AuditLog(actor=actor, action=action, entity_type="approval", entity_id=approval.id,
                         details={"task_id": approval.task_id, "action_type": approval.action_type,
                                  "risk_level": approval.risk_level, "reason": reason}))


def decide(session: Session, approval: Approval, decision: str, actor: str, reason: str | None = None) -> Approval:
    if decision not in {"approved", "rejected"}:
        raise ApprovalError("invalid_decision", "Keputusan harus approved atau rejected")
    if actor not in HUMAN_ACTORS:
        # agent, Manager, worker, dan sistem tidak pernah boleh memutuskan approval (termasuk miliknya sendiri)
        raise ApprovalError("agent_cannot_approve", f"'{actor}' bukan pihak yang berwenang memutuskan approval")
    if approval.status != "pending":
        raise ApprovalError("not_pending", f"Approval berstatus {approval.status}; tidak dapat diputuskan lagi")
    task = session.get(Task, approval.task_id)
    now = _naive(utcnow())
    if _naive(approval.expires_at) <= now:
        _resolve(session, approval, task, "expired", "system", "kedaluwarsa", cancel_task=True)
        raise ApprovalError("expired", "Approval sudah kedaluwarsa")
    if task is None or task.status != "pending_approval":
        raise ApprovalError("task_not_waiting", "Task tidak lagi menunggu approval")
    if approval.payload_hash != fingerprint(task_payload(session, task)):
        _resolve(session, approval, task, "cancelled", "system", "isi task berubah sejak approval diminta", cancel_task=False)
        raise ApprovalError("payload_changed", "Isi task berubah sejak approval diminta; minta approval baru")

    if decision == "approved":
        _resolve(session, approval, task, "approved", actor, reason, cancel_task=False)
        change_status(session, task, "queued", reason="approved", actor=actor)
    else:
        _resolve(session, approval, task, "rejected", actor, reason, cancel_task=True)
    _audit(session, f"approval.{'approve' if decision == 'approved' else 'reject'}", approval, actor, reason)
    return approval


def _resolve(session: Session, approval: Approval, task: Task | None, status: str, actor: str, reason: str | None,
             cancel_task: bool) -> None:
    approval.status, approval.decided_by, approval.decided_at, approval.decision_reason = status, actor, utcnow(), reason
    if task is not None:
        add_event(session, task, "approval.resolved", actor=actor,
                  payload={"approval_id": approval.id, "status": status, "decided_by": actor, "reason": reason})
        if cancel_task and task.status == "pending_approval":
            change_status(session, task, "cancelled", reason=f"approval_{status}", actor=actor)


def valid_for_execution(session: Session, task: Task) -> Approval | None:
    """Approval yang disetujui, belum terpakai, belum kedaluwarsa, dan masih cocok dengan isi task saat ini."""
    now = _naive(utcnow())
    current = fingerprint(task_payload(session, task))
    for a in session.scalars(select(Approval).where(Approval.task_id == task.id, Approval.status == "approved",
                                                    Approval.used_at.is_(None)).order_by(Approval.created_at.desc())):
        if _naive(a.expires_at) > now and a.payload_hash == current:
            return a
    return None


def consume(session: Session, approval: Approval) -> None:
    approval.used_at = utcnow()


def expire_due(session: Session) -> int:
    """Kedaluwarsakan permintaan yang tidak dijawab; task yang menunggunya dibatalkan."""
    now = _naive(utcnow())
    n = 0
    for a in session.scalars(select(Approval).where(Approval.status == "pending")).all():
        if _naive(a.expires_at) <= now:
            _resolve(session, a, session.get(Task, a.task_id), "expired", "system", "tidak diputuskan sebelum kedaluwarsa", cancel_task=True)
            n += 1
    return n


def cancel_open(session: Session, task_id: str, reason: str) -> None:
    for a in session.scalars(select(Approval).where(Approval.task_id == task_id, Approval.status == "pending")):
        a.status, a.decision_reason, a.decided_at, a.decided_by = "cancelled", reason, utcnow(), "system"


def ensure_open_for_pending_tasks(session: Session, ttl_hours: int = DEFAULT_TTL_HOURS) -> int:
    """Setiap task pending_approval harus punya permintaan approval terbuka (mis. task lama dari fase sebelumnya)."""
    n = 0
    for t in session.scalars(select(Task).where(Task.status == "pending_approval")).all():
        has = session.scalar(select(Approval.id).where(Approval.task_id == t.id, Approval.status == "pending").limit(1))
        if has is None:
            open_approval(session, t, ttl_hours)
            n += 1
    return n
