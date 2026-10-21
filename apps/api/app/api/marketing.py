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
                  "reason_required", "won_value_required", "status_not_settable", "invalid_reason", "channel_not_allowed", "invalid_content",
                  "invalid_metric", "paid_ads_unsupported", "name_required", "invalid_dates", "channel_not_in_campaign"}


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


# ================================================================== Phase 9: konten, kampanye, tindakan eksternal, serah-terima

from app.db.models import Campaign, ClientHandoff, ContentAsset, OutboundMessage  # noqa: E402
from app.marketing import external  # noqa: E402
from app.schemas.marketing import CampaignCreate, CampaignStatusBody, ContentCreate, ContentTaskBody, ContentUpdate, MetricBody  # noqa: E402


def _content_out(a: ContentAsset) -> dict:
    return {"id": a.id, "campaign_id": a.campaign_id, "product_id": a.product_id, "version_id": a.version_id, "kind": a.kind, "channel": a.channel,
            "title": a.title, "body": a.body, "status": a.status, "claim_check": a.claim_check, "scheduled_for": _iso(a.scheduled_for),
            "created_by": a.created_by, "task_id": a.task_id, "created_at": _iso(a.created_at)}


def _campaign_out(c: Campaign) -> dict:
    return {"id": c.id, "name": c.name, "product_id": c.product_id, "version_id": c.version_id, "objective": c.objective, "channels": c.channels,
            "status": c.status, "starts_on": _iso(c.starts_on), "ends_on": _iso(c.ends_on), "budget_idr": c.budget_idr}


def _outbound_out(m: OutboundMessage) -> dict:
    return {"id": m.id, "kind": m.kind, "ref_id": m.ref_id, "lead_id": m.lead_id, "channel": m.channel, "subject": m.subject, "body": m.body,
            "status": m.status, "task_id": m.task_id, "approval_id": m.approval_id, "dispatched_at": _iso(m.dispatched_at), "created_at": _iso(m.created_at)}


async def _commit(session: Session, fn, render):
    out = await _guard(fn)
    if isinstance(out, JSONResponse):
        session.rollback()
        return out
    session.commit()
    return render(out)


@router.get("/campaigns")
def list_campaigns(session: SessionDep):
    return [_campaign_out(c) for c in session.scalars(select(Campaign).order_by(Campaign.created_at.desc()))]


@router.post("/campaigns", status_code=201)
async def create_campaign(body: CampaignCreate, request: Request, session: SessionDep):
    out = await _commit(session, lambda: external.create_campaign(session, _policy(request), actor=ACTOR, **body.model_dump()), _campaign_out)
    return JSONResponse(out, status_code=201) if isinstance(out, dict) else out


def _campaign(session: Session, cid: str) -> Campaign:
    c = session.get(Campaign, cid)
    if c is None:
        raise HTTPException(404, "Kampanye tidak ditemukan")
    return c


@router.get("/campaigns/{cid}")
def get_campaign(cid: str, session: SessionDep):
    c = _campaign(session, cid)
    assets = session.scalars(select(ContentAsset).where(ContentAsset.campaign_id == c.id).order_by(ContentAsset.scheduled_for, ContentAsset.created_at))
    return _campaign_out(c) | {"report": external.campaign_report(session, c), "content": [_content_out(a) for a in assets]}


@router.post("/campaigns/{cid}/status")
async def campaign_status(cid: str, body: CampaignStatusBody, session: SessionDep):
    c = _campaign(session, cid)
    return await _commit(session, lambda: external.set_campaign_status(session, c, body.status, actor=ACTOR), _campaign_out)


@router.post("/campaigns/{cid}/metrics", status_code=201)
async def campaign_metric(cid: str, body: MetricBody, session: SessionDep):
    c = _campaign(session, cid)
    out = await _commit(session, lambda: external.record_metric(session, c, actor=ACTOR, **body.model_dump()), lambda _m: external.campaign_report(session, c))
    return JSONResponse(out, status_code=201) if isinstance(out, dict) else out


@router.get("/content")
def list_content(session: SessionDep, status: str | None = None, campaign_id: str | None = None):
    q = select(ContentAsset).order_by(ContentAsset.created_at.desc())
    if status:
        q = q.where(ContentAsset.status == status)
    if campaign_id:
        q = q.where(ContentAsset.campaign_id == campaign_id)
    return [_content_out(a) for a in session.scalars(q.limit(200))]


@router.post("/content", status_code=201)
async def create_content(body: ContentCreate, request: Request, session: SessionDep):
    out = await _commit(session, lambda: external.create_content(session, _policy(request), actor=ACTOR, **body.model_dump()), _content_out)
    return JSONResponse(out, status_code=201) if isinstance(out, dict) else out


def _content(session: Session, cid: str) -> ContentAsset:
    a = session.get(ContentAsset, cid)
    if a is None:
        raise HTTPException(404, "Konten tidak ditemukan")
    return a


@router.get("/content/{cid}")
def get_content(cid: str, session: SessionDep):
    return _content_out(_content(session, cid))


@router.patch("/content/{cid}")
async def update_content(cid: str, body: ContentUpdate, request: Request, session: SessionDep):
    a = _content(session, cid)
    return await _commit(session, lambda: external.update_content(session, _policy(request), a, actor=ACTOR, **body.model_dump(exclude_unset=True)), _content_out)


@router.post("/content/{cid}/request-publish", status_code=201)
async def request_publish(cid: str, request: Request, session: SessionDep):
    """Minta approval CEO untuk mempublikasikan isi PERSIS ini. Hanya membuat task berisiko kritis yang menunggu approval."""
    a = _content(session, cid)
    err = await _guard(lambda: external.check_publish_allowed(session, _policy(request), a))
    if isinstance(err, JSONResponse):
        return err
    out = _queue(session, request, title=f"Publikasi: {a.title[:60]}", role="content_promotion", action="publish",
                 params={"content_id": a.id, "body_hash": a.body_hash, "channel": a.channel, "title": a.title, "preview": a.body[:400]})
    return JSONResponse(out, status_code=201)


@router.post("/tasks/content", status_code=201)
def content_task(body: ContentTaskBody, request: Request, session: SessionDep):
    policy = _policy(request)
    if body.kind not in external.CONTENT_KINDS or body.channel not in policy.content_channels:
        return JSONResponse({"detail": "Jenis konten atau kanal tidak diizinkan", "code": "channel_not_allowed"}, status_code=422)
    if session.get(Product, body.product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")
    return _queue(session, request, title=f"Konten {body.kind} untuk {body.channel}", role="content_promotion", action="draft_content", params=body.model_dump())


@router.post("/outreach/{oid}/request-send", status_code=201)
async def request_send(oid: str, request: Request, session: SessionDep):
    """Minta approval CEO untuk mengirim isi PERSIS draf ini. Batas frekuensi, jangan-hubungi, dan klaim diperiksa sekarang dan lagi saat dieksekusi."""
    o = _outreach(session, oid)
    err = await _guard(lambda: external.check_send_allowed(session, _policy(request), o))
    if isinstance(err, JSONResponse):
        return err
    lead = session.get(Lead, o.lead_id)
    domain = (lead.contact_email or "").rsplit("@", 1)[-1]
    out = _queue(session, request, title=f"Kirim outreach ke {domain}", role="sales_client_relations", action="external_outreach",
                 params={"outreach_id": o.id, "body_hash": external.outreach_hash(o), "channel": o.channel, "recipient_domain": domain,
                         "subject": o.subject, "preview": o.body[:400]})
    return JSONResponse(out, status_code=201)


@router.get("/outbox")
def list_outbox(session: SessionDep, status: str | None = None):
    q = select(OutboundMessage).order_by(OutboundMessage.created_at.desc())
    if status:
        q = q.where(OutboundMessage.status == status)
    return [_outbound_out(m) for m in session.scalars(q.limit(200))]


def _msg(session: Session, mid: str) -> OutboundMessage:
    m = session.get(OutboundMessage, mid)
    if m is None:
        raise HTTPException(404, "Pesan tidak ditemukan")
    return m


@router.post("/outbox/{mid}/dispatch")
async def dispatch(mid: str, session: SessionDep):
    m = _msg(session, mid)
    out = await _guard(lambda: external.dispatch_manual(session, m, actor=ACTOR))
    if isinstance(out, JSONResponse):
        session.commit()      # penolakan karena prospek tidak lagi dapat dihubungi membatalkan pesan di kotak keluar; simpan pembatalan itu
        return out
    session.commit()
    return _outbound_out(out)


@router.post("/outbox/{mid}/cancel")
async def cancel_outbox(mid: str, body: ReasonBody, session: SessionDep):
    m = _msg(session, mid)
    return await _commit(session, lambda: external.cancel_outbound(session, m, actor=ACTOR, reason=body.reason), _outbound_out)


@router.post("/opportunities/{opp_id}/handoff", status_code=201)
async def handoff(opp_id: str, request: Request, session: SessionDep):
    opp = _opp(session, opp_id)
    storage = ProjectStorage(request.app.state.settings.projects_dir)
    out = await _commit(session, lambda: external.create_handoff(session, storage, opp, actor=ACTOR),
                        lambda h: {"id": h.id, "opportunity_id": h.opportunity_id, "project_id": h.project_id, "task_ids": h.task_ids, "requirements": h.requirements})
    return JSONResponse(out, status_code=201) if isinstance(out, dict) else out


@router.get("/handoffs")
def list_handoffs(session: SessionDep):
    return [{"id": h.id, "opportunity_id": h.opportunity_id, "project_id": h.project_id, "task_ids": h.task_ids, "requirements": h.requirements,
             "created_at": _iso(h.created_at)} for h in session.scalars(select(ClientHandoff).order_by(ClientHandoff.created_at.desc()))]
