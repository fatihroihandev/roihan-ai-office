"""Ringkasan operasional untuk CEO Office dan kantor virtual (Bagian 7.2). Hanya membaca; tidak ada status yang disimpan atau disimulasikan.

Satu panggilan mengembalikan SATU potret konsisten (agen + hitungan + keputusan yang menunggu), sehingga tampilan yang dimuat ulang
setelah reconnect selalu sama dengan keadaan backend.
"""
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import Approval, ContentAsset, ModelUsage, OutboundMessage, OutreachRecord, Project, Task, TaskEvent
from app.marketing import service as marketing
from app.power import service as power_service
from app.marketing.policy import Policy
from app.security import require_token
from app.tasks.agents import agent_statuses
from app.tasks.catalog import ROLES
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
        "power": power_service.snapshot(session),
        "agents": agent_statuses(session),
    }


# ================================================================== insight: grafik untuk dashboard (Phase 10)

FUNNEL = ["new", "qualified", "contacted", "meeting", "opportunity", "won"]
OUT_STATUS = ["lost", "disqualified", "do_not_contact"]


def _day(dt):
    return _naive(dt).date() if dt is not None else None


@router.get("/dashboard/insights")
def insights(request: Request, session: SessionDep, days: Annotated[int, Query(ge=7, le=60)] = 14):
    """Data grafik: throughput harian, progres proyek, beban kerja agent, kualitas 7 hari, aktivitas AI per jam, corong prospek, dan jejak terbaru.
    Semuanya dihitung dari tabel yang ada; nilai yang belum diketahui `null` (bukan nol)."""
    now = _naive(utcnow())
    today = now.date()
    tasks = list(session.scalars(select(Task)))

    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    created = {d: 0 for d in day_list}
    completed = {d: 0 for d in day_list}
    failed = {d: 0 for d in day_list}
    for t in tasks:
        d = _day(t.created_at)
        if d in created:
            created[d] += 1
        f = _day(t.finished_at)
        if f in completed and t.status == "completed":
            completed[f] += 1
        if f in failed and t.status == "failed":
            failed[f] += 1
    throughput = [{"date": d.isoformat(), "created": created[d], "completed": completed[d], "failed": failed[d]} for d in day_list]

    projects = []
    for p in session.scalars(select(Project).where(Project.deleted_at.is_(None), Project.status == "active")):
        mine = [t for t in tasks if t.project_id == p.id]
        c = {s: sum(1 for t in mine if t.status == s) for s in STATUSES}
        live = [t for t in mine if t.status == "running"]
        denom = len(mine) - c["cancelled"]
        projects.append({
            "id": p.id, "name": p.name, "total": len(mine), "counts": c, "percent": round(100 * c["completed"] / denom) if denom > 0 else None,
            "current": live[0].title if live else None,
        })
    projects.sort(key=lambda x: (-(x["counts"]["running"] > 0), -x["total"], x["name"]))

    week_ago = now - timedelta(days=7)
    workload = []
    for role in ROLES:
        mine = [t for t in tasks if t.role == role]
        recent = [t for t in mine if t.finished_at is not None and _naive(t.finished_at) >= week_ago]
        workload.append({
            "role": role, "running": sum(1 for t in mine if t.status == "running"),
            "queued": sum(1 for t in mine if t.status in {"queued", "pending_approval"}),
            "blocked": sum(1 for t in mine if t.status == "blocked"),
            "completed_7d": sum(1 for t in recent if t.status == "completed"), "failed_7d": sum(1 for t in recent if t.status == "failed"),
        })

    finished = [t for t in tasks if t.finished_at is not None and _naive(t.finished_at) >= week_ago and t.status in {"completed", "failed"}]
    done = [t for t in finished if t.status == "completed"]
    durations = [(_naive(t.finished_at) - _naive(t.started_at)).total_seconds() / 60 for t in done if t.started_at is not None]
    quality = {
        "finished_7d": len(finished),
        "success_rate_7d": round(len(done) / len(finished), 4) if finished else None,
        "avg_minutes": round(sum(durations) / len(durations), 1) if durations else None,
    }

    since = now - timedelta(hours=24)
    buckets = [{"hour": (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0), "calls": 0, "tokens": 0, "errors": 0} for i in range(23, -1, -1)]
    index = {b["hour"]: b for b in buckets}
    for u in session.scalars(select(ModelUsage).order_by(ModelUsage.created_at.desc()).limit(5000)):
        ts = _naive(u.created_at)
        if ts < since:
            continue
        b = index.get(ts.replace(minute=0, second=0, microsecond=0))
        if b is not None:
            b["calls"] += 1
            b["tokens"] += (u.prompt_tokens or 0) + (u.completion_tokens or 0)
            b["errors"] += 1 if u.status == "error" else 0
    ai_hourly = [{**b, "hour": b["hour"].isoformat()} for b in buckets]

    by_status = marketing.analytics(session)["by_status"]
    reached = [sum(by_status.get(s, 0) for s in FUNNEL[i:]) for i in range(len(FUNNEL))]
    funnel = {"stages": [{"stage": s, "now": by_status.get(s, 0), "reached": r} for s, r in zip(FUNNEL, reached)],
              "out": {s: by_status.get(s, 0) for s in OUT_STATUS},
              "note": "reached = prospek yang statusnya sudah mencapai tahap ini atau lebih jauh (tidak termasuk yang keluar)"}

    names = {t.id: t for t in tasks}
    project_name = {p.id: p.name for p in session.scalars(select(Project))}
    activity = []
    for e in session.scalars(select(TaskEvent).order_by(TaskEvent.seq.desc()).limit(16)):
        t = names.get(e.task_id)
        activity.append({
            "seq": e.seq, "type": e.type, "to_status": e.to_status, "actor": e.actor, "reason": e.reason, "at": _naive(e.created_at).isoformat(),
            "task_id": e.task_id, "title": t.title if t else None, "role": t.role if t else None, "project": project_name.get(e.project_id),
        })
    return {"generated_at": now.isoformat(), "days": days, "throughput": throughput, "projects": projects[:8], "workload": workload, "quality": quality,
            "ai_hourly": ai_hourly, "funnel": funnel, "activity": activity}
