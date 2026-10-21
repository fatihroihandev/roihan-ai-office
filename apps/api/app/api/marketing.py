from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ClientRequirement, Company, Lead, LeadInteraction, LeadSource, MarketResearch, OutreachRecord, Product, SalesOpportunity,
    SuppressionEntry,
)
from app.marketing import access, service
from app.marketing.agents import ensure_marketing_project
from app.marketing.access import AccessDenied
from app.marketing.policy import Policy
from app.marketing.privacy import PolicyError, mask_email, mask_name, mask_phone
from app.schemas.marketing import (
    ConvertBody, ForwardBody, IntakeBody, InteractionIn, LeadContactUpdate, LeadCreate, OutreachTaskBody, ReasonBody, RequirementIn,
    ResearchBody, SentBody, StageBody, StatusBody, SuppressionIn,
)
from app.projects.storage import ProjectStorage
from app.security import require_token
from app.tasks import service as tasks

router = APIRouter(prefix="/api/marketing", tags=["marketing"], dependencies=[Depends(require_token)])
ACTOR = "ceo"
_UNPROCESSABLE = {"invalid_kind", "invalid_summary", "invalid_stage", "invalid_value", "invalid_priority", "invalid_text", "title_required",
                  "reason_required", "won_value_required", "status_not_settable", "invalid_reason"}


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _policy(request: Request) -> Policy:
    return Policy.from_settings(request.app.state.settings)


def _iso(dt):
    return dt.isoformat() if dt else None


async def _guard(call):
    try:
        return call()
    except PolicyError as e:
        return JSONResponse({"detail": e.message, "code": e.code, **e.details}, status_code=422)
    except service.MarketingError as e:
        return JSONResponse({"detail": e.message, "code": e.code, **e.details}, status_code=422 if e.code in _UNPROCESSABLE else 409)
    except AccessDenied as e:
        return JSONResponse({"detail": str(e), "code": "forbidden"}, status_code=403)


def _lead(session: Session, lead_id: str) -> Lead:
    row = session.get(Lead, lead_id)
    if row is None:
        raise HTTPException(404, "Prospek tidak ditemukan")
    return row


def _lead_out(session: Session, lead: Lead, reveal: bool = False) -> dict:
    comp, src = session.get(Company, lead.company_id), session.get(LeadSource, lead.source_id)
    contact = {"name": mask_name(lead.contact_name), "title": lead.contact_title, "email": mask_email(lead.contact_email),
               "phone": mask_phone(lead.contact_phone), "masked": True}
    if reveal:
        contact = {**service.pii_for_actor(session, lead, ACTOR), "masked": False}
    return {
        "id": lead.id, "status": lead.status, "score": lead.score, "score_breakdown": lead.score_breakdown, "basis": lead.basis,
        "owner": lead.owner, "do_not_contact": lead.do_not_contact, "anonymized": lead.anonymized_at is not None,
        "forwarded_at": _iso(lead.forwarded_at), "collected_at": _iso(lead.collected_at), "last_interaction_at": _iso(lead.last_interaction_at),
        "product_id": lead.product_id, "created_by": lead.created_by, "contact": contact,
        "company": {"id": comp.id, "name": comp.name, "industry": comp.industry, "size_band": comp.size_band, "city": comp.city,
                    "website": comp.website, "domain": comp.domain},
        "source": {"id": src.id, "type": src.source_type, "url": src.url, "title": src.title, "collected_at": _iso(src.collected_at),
                   "collected_by": src.collected_by, "method": src.method},
    }


def _opp_out(session: Session, o: SalesOpportunity) -> dict:
    reqs = session.scalars(select(ClientRequirement).where(ClientRequirement.opportunity_id == o.id).order_by(ClientRequirement.created_at))
    return {"id": o.id, "lead_id": o.lead_id, "title": o.title, "stage": o.stage, "value_estimate_idr": o.value_estimate_idr,
            "won_value_idr": o.won_value_idr, "summary": o.summary, "outcome_reason": o.outcome_reason, "closed_at": _iso(o.closed_at),
            "requirements": [{"id": r.id, "text": r.text, "priority": r.priority, "recorded_by": r.recorded_by} for r in reqs]}


def _outreach_out(o: OutreachRecord) -> dict:
    return {"id": o.id, "lead_id": o.lead_id, "product_id": o.product_id, "version_id": o.version_id, "task_id": o.task_id, "channel": o.channel,
            "subject": o.subject, "body": o.body, "status": o.status, "claim_check": o.claim_check, "sent_at": _iso(o.sent_at),
            "sent_note": o.sent_note, "created_at": _iso(o.created_at)}


def _queue(session: Session, request: Request, *, title: str, role: str, action: str, params: dict, description: str = "") -> dict:
    pid = ensure_marketing_project(session, ProjectStorage(request.app.state.settings.projects_dir))
    t = tasks.create_task(session, project_id=pid, title=title, description=description, role=role, action_type=action, params=params,
                          created_by=ACTOR, max_retries=1)
    tasks.queue_task(session, t)
    session.commit()
    return {"task_id": t.id, "project_id": pid, "status": t.status}


# ------------------------------------------------------------------ kebijakan, analitik

@router.get("/policy")
def get_policy(request: Request):
    return _policy(request).describe()


@router.get("/analytics")
def get_analytics(session: SessionDep):
    return service.analytics(session)


# ------------------------------------------------------------------ prospek

@router.get("/leads")
def list_leads(session: SessionDep, status: str | None = None, limit: int = Query(100, ge=1, le=500)):
    q = select(Lead).order_by(Lead.created_at.desc(), Lead.id)
    if status:
        q = q.where(Lead.status == status)
    return [_lead_out(session, l) for l in session.scalars(q.limit(limit))]


@router.post("/leads", status_code=201)
async def create_lead(body: LeadCreate, request: Request, session: SessionDep):
    def go():
        lead = service.create_lead(session, _policy(request), actor=ACTOR, company=body.company.model_dump(), contact=body.contact.model_dump() if body.contact else None,
                                   source=body.source.model_dump(), product_id=body.product_id)
        session.commit()
        return JSONResponse(_lead_out(session, lead), status_code=201)
    out = await _guard(go)
    if isinstance(out, JSONResponse) and out.status_code >= 400:
        session.rollback()
    return out


@router.get("/leads/{lead_id}")
def get_lead(lead_id: str, session: SessionDep, reveal: bool = False):
    lead = _lead(session, lead_id)
    out = _lead_out(session, lead, reveal and lead.anonymized_at is None)
    if reveal:
        session.commit()      # menyimpan audit pembacaan data pribadi
    inter = session.scalars(select(LeadInteraction).where(LeadInteraction.lead_id == lead.id).order_by(LeadInteraction.occurred_at))
    out["interactions"] = [{"id": i.id, "kind": i.kind, "occurred_at": _iso(i.occurred_at), "summary": i.summary, "recorded_by": i.recorded_by} for i in inter]
    out["outreach"] = [_outreach_out(o) for o in session.scalars(select(OutreachRecord).where(OutreachRecord.lead_id == lead.id).order_by(OutreachRecord.created_at))]
    out["opportunities"] = [_opp_out(session, o) for o in session.scalars(select(SalesOpportunity).where(SalesOpportunity.lead_id == lead.id))]
    return out


async def _mutate(session: Session, request: Request, lead: Lead, fn):
    out = await _guard(fn)
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return _lead_out(session, lead)


@router.patch("/leads/{lead_id}")
async def update_lead(lead_id: str, body: LeadContactUpdate, request: Request, session: SessionDep):
    lead = _lead(session, lead_id)
    return await _mutate(session, request, lead, lambda: service.update_contact(session, _policy(request), lead, actor=ACTOR, **body.model_dump(exclude_unset=True)))


@router.post("/leads/{lead_id}/rescore")
async def rescore(lead_id: str, request: Request, session: SessionDep):
    lead = _lead(session, lead_id)
    return await _mutate(session, request, lead, lambda: service.recompute_score(session, _policy(request), lead))


@router.post("/leads/{lead_id}/status")
async def set_status(lead_id: str, body: StatusBody, request: Request, session: SessionDep):
    lead = _lead(session, lead_id)
    return await _mutate(session, request, lead, lambda: service.set_status(session, _policy(request), lead, body.status, actor=ACTOR,
                                                                              reason=body.reason, override_reason=body.override_reason))


@router.post("/leads/{lead_id}/forward")
async def forward(lead_id: str, body: ForwardBody, request: Request, session: SessionDep):
    lead = _lead(session, lead_id)
    out = await _mutate(session, request, lead, lambda: service.forward_to_sales(session, _policy(request), lead, actor=ACTOR, override_reason=body.override_reason))
    if isinstance(out, JSONResponse) or not body.draft_outreach_product_id:
        return out
    if session.get(Product, body.draft_outreach_product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")
    out["outreach_task"] = _queue(session, request, title=f"Draf outreach untuk prospek {lead.id[:8]}", role="sales_client_relations", action="draft_outreach",
                                  params={"lead_id": lead.id, "product_id": body.draft_outreach_product_id, "channel": "email"})
    return out


@router.post("/leads/{lead_id}/opt-out")
async def opt_out(lead_id: str, body: ReasonBody, request: Request, session: SessionDep):
    lead = _lead(session, lead_id)
    return await _mutate(session, request, lead, lambda: service.opt_out(session, lead, actor=ACTOR, reason=body.reason))


@router.post("/leads/{lead_id}/erase")
async def erase(lead_id: str, body: ReasonBody, request: Request, session: SessionDep):
    lead = _lead(session, lead_id)
    return await _mutate(session, request, lead, lambda: service.erase(session, lead, actor=ACTOR, reason=body.reason))


@router.post("/leads/{lead_id}/interactions", status_code=201)
async def add_interaction(lead_id: str, body: InteractionIn, session: SessionDep):
    lead = _lead(session, lead_id)
    out = await _guard(lambda: service.add_interaction(session, lead, actor=ACTOR, kind=body.kind, summary=body.summary, occurred_at=body.occurred_at))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return JSONResponse({"id": out.id, "kind": out.kind, "occurred_at": _iso(out.occurred_at), "summary": out.summary}, status_code=201)


@router.post("/leads/{lead_id}/convert", status_code=201)
async def convert(lead_id: str, body: ConvertBody, session: SessionDep):
    lead = _lead(session, lead_id)
    out = await _guard(lambda: service.convert_to_opportunity(session, lead, actor=ACTOR, title=body.title,
                                                              value_estimate_idr=body.value_estimate_idr, summary=body.summary))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return JSONResponse(_opp_out(session, out), status_code=201)


# ------------------------------------------------------------------ peluang

@router.get("/opportunities")
def list_opportunities(session: SessionDep):
    return [_opp_out(session, o) for o in session.scalars(select(SalesOpportunity).order_by(SalesOpportunity.created_at.desc()))]


def _opp(session: Session, opp_id: str) -> SalesOpportunity:
    o = session.get(SalesOpportunity, opp_id)
    if o is None:
        raise HTTPException(404, "Peluang tidak ditemukan")
    return o


@router.post("/opportunities/{opp_id}/stage")
async def set_stage(opp_id: str, body: StageBody, session: SessionDep):
    opp = _opp(session, opp_id)
    out = await _guard(lambda: service.set_opportunity_stage(session, opp, body.stage, actor=ACTOR, reason=body.reason, won_value_idr=body.won_value_idr))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return _opp_out(session, opp)


@router.post("/opportunities/{opp_id}/requirements", status_code=201)
async def add_requirement(opp_id: str, body: RequirementIn, session: SessionDep):
    opp = _opp(session, opp_id)
    out = await _guard(lambda: service.add_requirement(session, opp, actor=ACTOR, text=body.text, priority=body.priority))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return JSONResponse(_opp_out(session, opp), status_code=201)


# ------------------------------------------------------------------ outreach

@router.get("/outreach")
def list_outreach(session: SessionDep, status: str | None = None):
    q = select(OutreachRecord).order_by(OutreachRecord.created_at.desc())
    if status:
        q = q.where(OutreachRecord.status == status)
    return [_outreach_out(o) for o in session.scalars(q.limit(200))]


def _outreach(session: Session, oid: str) -> OutreachRecord:
    o = session.get(OutreachRecord, oid)
    if o is None:
        raise HTTPException(404, "Draf tidak ditemukan")
    return o


@router.post("/outreach/{oid}/mark-sent")
async def mark_sent(oid: str, body: SentBody, session: SessionDep):
    o = _outreach(session, oid)
    out = await _guard(lambda: service.mark_outreach_sent(session, o, actor=ACTOR, note=body.note))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return _outreach_out(o)


@router.post("/outreach/{oid}/cancel")
async def cancel(oid: str, session: SessionDep):
    o = _outreach(session, oid)
    out = await _guard(lambda: service.cancel_outreach(session, o, actor=ACTOR))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return _outreach_out(o)


# ------------------------------------------------------------------ pekerjaan agent

@router.post("/tasks/research", status_code=201)
def research_task(body: ResearchBody, request: Request, session: SessionDep):
    if body.product_id and session.get(Product, body.product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")
    return _queue(session, request, title=f"Riset: {body.topic[:80]}", role="market_research", action="market_research",
                  params={"topic": body.topic, "material": body.material, "product_id": body.product_id})


@router.post("/tasks/intake", status_code=201)
def intake_task(body: IntakeBody, request: Request, session: SessionDep):
    policy = _policy(request)
    try:                                           # tolak sumber terlarang/tidak sah sebelum membuat task
        from app.marketing.policy import validate_source_type, validate_url
        rule = validate_source_type(policy, body.source.source_type)
        validate_url(body.source.url, rule["needs_url"])
    except PolicyError as e:
        return JSONResponse({"detail": e.message, "code": e.code}, status_code=422)
    if body.product_id and session.get(Product, body.product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")
    return _queue(session, request, title=f"Intake prospek ({body.source.source_type})", role="lead_generation", action="lead_intake",
                  params={"source": {"source_type": body.source.source_type, "url": body.source.url, "title": body.source.title},
                          "raw_text": body.raw_text, "product_id": body.product_id})


@router.post("/tasks/outreach", status_code=201)
def outreach_task(body: OutreachTaskBody, request: Request, session: SessionDep):
    lead = _lead(session, body.lead_id)
    if lead.forwarded_at is None:
        return JSONResponse({"detail": "Prospek belum diteruskan ke Sales", "code": "not_forwarded"}, status_code=409)
    if session.get(Product, body.product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")
    return _queue(session, request, title=f"Draf outreach untuk prospek {lead.id[:8]}", role="sales_client_relations", action="draft_outreach",
                  params={"lead_id": lead.id, "product_id": body.product_id, "version_id": body.version_id, "channel": body.channel})


@router.get("/research")
def list_research(session: SessionDep):
    return [{"id": r.id, "topic": r.topic, "summary": r.summary, "items": r.items, "verified_count": r.verified_count,
             "unverified_count": r.unverified_count, "task_id": r.task_id, "created_at": _iso(r.created_at)}
            for r in session.scalars(select(MarketResearch).order_by(MarketResearch.created_at.desc()).limit(100))]


# ------------------------------------------------------------------ suppression dan retensi

@router.get("/suppression")
def list_suppression(session: SessionDep):
    """Hanya hash; nilai asli tidak pernah disimpan atau ditampilkan."""
    return [{"id": s.id, "kind": s.kind, "reason": s.reason, "hash_prefix": s.value_hash[:12], "created_at": _iso(s.created_at)}
            for s in session.scalars(select(SuppressionEntry).order_by(SuppressionEntry.created_at.desc()))]


@router.post("/suppression", status_code=201)
async def add_suppression(body: SuppressionIn, session: SessionDep):
    out = await _guard(lambda: service.add_suppression(session, kind=body.kind, value=body.value, reason=body.reason, actor=ACTOR))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return JSONResponse({"id": out.id, "kind": out.kind, "reason": out.reason}, status_code=201)


@router.get("/retention")
def retention_status(request: Request, session: SessionDep):
    policy = _policy(request)
    return {"policy": policy.describe()["retention"], "due": service.retention_due(session, policy)}


@router.post("/retention/run")
async def retention_run(request: Request, session: SessionDep, dry_run: bool = True):
    policy = _policy(request)
    if dry_run:
        return {"dry_run": True, "due": service.retention_due(session, policy)}
    out = await _guard(lambda: service.apply_retention(session, policy, actor=ACTOR))
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return {"dry_run": False, "anonymized": out}
