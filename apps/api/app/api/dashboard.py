"""Ringkasan operasional untuk CEO Office dan kantor virtual (Bagian 7.2). Hanya membaca; tidak ada status yang disimpan atau disimulasikan.

Satu panggilan mengembalikan SATU potret konsisten (agen + hitungan + keputusan yang menunggu), sehingga tampilan yang dimuat ulang
setelah reconnect selalu sama dengan keadaan backend.
"""
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Approval, ContentAsset, ModelUsage, OutboundMessage, OutreachRecord, Project, Task
from app.marketing import service as marketing
from app.marketing.policy import Policy
from app.security import require_token
from app.tasks.agents import agent_statuses
from app.tasks.state import STATUSES

router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(require_token)])
MAX_ITEMS = 12


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _naive(dt):
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo else dt


@router.get("/dashboard")
def dashboard(request: Request, session: SessionDep):
    settings = request.app.state.settings
    now = utcnow()

    counts = dict(session.execute(select(Task.status, func.count()).group_by(Task.status)).all())
    projects = session.scalar(select(func.count()).select_from(Project).where(Project.deleted_at.is_(None), Project.status == "active")) or 0

    needs: list[dict] = []
    approvals = session.scalars(select(Approval).where(Approval.status == "pending").order_by(Approval.created_at)).all()
    for a in approvals[:MAX_ITEMS]:
        needs.append({"kind": "approval", "id": a.id, "title": (a.payload or {}).get("title", a.action_type), "risk": a.risk_level, "href": "/approvals"})
    for t in session.scalars(select(Task).where(Task.status == "blocked").order_by(Task.updated_at.desc()).limit(MAX_ITEMS)):
        needs.append({"kind": "task_blocked", "id": t.id, "title": t.title, "reason": t.blocked_reason, "href": f"/tasks/{t.id}"})
    for t in session.scalars(select(Task).where(Task.status == "failed").order_by(Task.updated_at.desc()).limit(MAX_ITEMS)):
        needs.append({"kind": "task_failed", "id": t.id, "title": t.title, "reason": t.last_error_kind, "href": f"/tasks/{t.id}"})

    policy = Policy.from_settings(settings)
    mk = marketing.analytics(session)
    marketing_block = {
        "leads_total": mk["leads_total"], "by_status": mk["by_status"], "opportunities_open": mk["opportunities_open"],
        "content_ready": session.scalar(select(func.count()).select_from(ContentAsset).where(ContentAsset.status == "ready_for_review")) or 0,
        "outreach_ready": session.scalar(select(func.count()).select_from(OutreachRecord).where(OutreachRecord.status == "ready_for_review")) or 0,
        "outbox_waiting": session.scalar(select(func.count()).select_from(OutboundMessage).where(OutboundMessage.status == "queued_manual")) or 0,
        "retention_due": len(marketing.retention_due(session, policy, now)),
    }

    since = _naive(now) - timedelta(hours=24)
    usage = [u for u in session.scalars(select(ModelUsage).order_by(ModelUsage.created_at.desc()).limit(5000)) if _naive(u.created_at) >= since]
    ai = {
        "calls_24h": len(usage), "errors_24h": sum(1 for u in usage if u.status == "error"), "blocked_24h": sum(1 for u in usage if u.status == "blocked"),
        "paid_calls_24h": sum(1 for u in usage if u.is_paid),
        "tokens_24h": sum((u.prompt_tokens or 0) + (u.completion_tokens or 0) for u in usage),
        "paid_providers_enabled": any([settings.openai_enabled, settings.gemini_enabled, settings.anthropic_enabled]),
    }
    worker = getattr(request.app.state, "worker", None)
    return {
        "generated_at": now.isoformat(),
        "projects_active": projects,
        "tasks": {s: counts.get(s, 0) for s in STATUSES},
        "approvals_pending": len(approvals),
        "needs_decision": needs[: MAX_ITEMS * 2],
        "marketing": marketing_block,
        "ai": ai,
        "worker": {"enabled": settings.worker_enabled, "running": worker is not None, "current_task_id": worker.current_task_id if worker else None},
        "agents": agent_statuses(session),
    }
