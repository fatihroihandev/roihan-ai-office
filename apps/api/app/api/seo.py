"""SEO & Digital Marketing (Phase 14): antre pekerjaan SEO/analitik, artefak, metrik manual, KPI, dan serah terima ke Engineering.

Semua artefak hanya untuk ditinjau. Serah terima membuat task DRAFT untuk Engineering (CEO yang mengantrekan); tidak ada perubahan
kode produksi atau publikasi dari sini.
"""
from typing import Annotated, Literal
from urllib.parse import urlsplit
from datetime import datetime, timezone
import ipaddress

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.marketing import ACTOR, _queue
from app.db.base import utcnow
from app.db.models import MarketingArtifact, Product, Project, SeoCampaign, SeoCampaignEvent, SeoKeyword, SeoMetric, SeoRecommendation, Site, Task
from app.marketing import seo, sites
from app.marketing.service import MarketingError
from app.security import require_token
from app.tasks import service as tasks

router = APIRouter(prefix="/api/marketing/seo", tags=["seo"], dependencies=[Depends(require_token)])


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


class AuditBody(BaseModel):
    url: str = Field(default="", max_length=500)
    html: str = Field(min_length=1, max_length=seo.MAX_HTML)
    robots_txt: str = Field(default="", max_length=20_000)
    sitemap_xml: str = Field(default="", max_length=100_000)


class KeywordBody(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    material: str = Field(min_length=1, max_length=8000)
    product_id: str | None = None


class BriefBody(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    keyword: str | None = Field(default=None, max_length=200)
    material: str = Field(default="", max_length=8000)
    product_id: str | None = None


class MetricBody(BaseModel):
    metric: Literal["impressions", "clicks", "organic_sessions", "conversions", "position"]
    value: float = Field(ge=0)
    period: str = Field(pattern=r"^\d{4}-\d{2}(-\d{2})?$")
    page: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=300)


class HandoffBody(BaseModel):
    project_id: str | None = None  # kosong = proyek situs (bila artefak berasal dari audit situs)


class SiteTaskBody(BaseModel):
    topic: str | None = Field(default=None, max_length=200)
    material: str = Field(default="", max_length=8000)
    keyword: str | None = Field(default=None, max_length=200)


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    website_url: str = Field(min_length=8, max_length=1000)
    site_id: str | None = None
    target_country: str | None = Field(default=None, max_length=80)
    target_language: str | None = Field(default=None, max_length=40)
    target_location: str | None = Field(default=None, max_length=160)
    primary_keywords: list[str] = Field(default_factory=list, max_length=50)
    objective: Literal["keyword_rank", "organic_traffic", "clicks", "leads", "conversions"] = "organic_traffic"
    target_value: float | None = Field(default=None, ge=0)
    baseline: dict = Field(default_factory=dict)
    baseline_source: str = Field(default="not_provided", max_length=500)
    starts_on: datetime | None = None
    review_on: datetime | None = None
    api_budget_idr: int = Field(default=0, ge=0)
    external_budget_idr: int = Field(default=0, ge=0)
    autonomy: Literal["read_only", "staging_write", "approved_production_write"] = "read_only"


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    website_url: str | None = Field(default=None, min_length=8, max_length=1000)
    target_country: str | None = Field(default=None, max_length=80)
    target_language: str | None = Field(default=None, max_length=40)
    target_location: str | None = Field(default=None, max_length=160)
    primary_keywords: list[str] | None = Field(default=None, max_length=50)
    objective: Literal["keyword_rank", "organic_traffic", "clicks", "leads", "conversions"] | None = None
    target_value: float | None = Field(default=None, ge=0)
    baseline: dict | None = None
    baseline_source: str | None = Field(default=None, max_length=500)
    starts_on: datetime | None = None
    review_on: datetime | None = None
    api_budget_idr: int | None = Field(default=None, ge=0)
    external_budget_idr: int | None = Field(default=None, ge=0)
    autonomy: Literal["read_only", "staging_write", "approved_production_write"] | None = None


class CampaignStatusBody(BaseModel):
    status: Literal["draft", "auditing", "planning", "active", "paused", "target_review", "completed", "failed", "archived"]


class CampaignKeywordCreate(BaseModel):
    keyword: str = Field(min_length=2, max_length=240)
    intent: Literal["informational", "navigational", "commercial", "transactional", "mixed"] = "mixed"
    rationale: str = Field(default="", max_length=2000)
    target_page: str | None = Field(default=None, max_length=1000)


class CampaignKeywordDecision(BaseModel):
    status: Literal["approved", "rejected", "pending"]


class CampaignKeywordBulkDecision(BaseModel):
    keyword_ids: list[str] = Field(min_length=1, max_length=100)
    status: Literal["approved", "rejected", "pending"]


class CampaignKeywordSuggest(BaseModel):
    topic: str | None = Field(default=None, max_length=200)
    material: str = Field(default="", max_length=8000)


class CampaignBriefRequest(BaseModel):
    keyword_id: str
    material: str = Field(default="", max_length=8000)


class RecommendationDecision(BaseModel):
    status: Literal["approved", "rejected", "in_progress", "completed"]
    note: str | None = Field(default=None, max_length=1000)


def _view(a: MarketingArtifact, full: bool = False) -> dict:
    out = {"id": a.id, "kind": a.kind, "title": a.title, "summary": a.summary, "task_id": a.task_id, "created_at": a.created_at.isoformat(),
           "verified_count": a.verified_count, "unverified_count": a.unverified_count, "handed_off_to": a.handed_off_task_id}
    if full:
        out["data"] = a.data
    return out


CAMPAIGN_STATUSES = {"draft", "auditing", "planning", "active", "paused", "target_review", "completed", "failed", "archived"}
CAMPAIGN_TRANSITIONS = {
    "draft": {"auditing", "planning", "paused", "archived"},
    "auditing": {"planning", "active", "paused", "failed", "archived"},
    "planning": {"active", "paused", "failed", "archived"},
    "active": {"paused", "target_review", "completed", "failed", "archived"},
    "paused": {"auditing", "planning", "active", "archived"},
    "target_review": {"active", "completed", "paused", "archived"},
    "completed": {"archived"}, "failed": {"draft", "paused", "archived"}, "archived": set(),
}


def _campaign_or_404(session: Session, campaign_id: str) -> SeoCampaign:
    row = session.get(SeoCampaign, campaign_id)
    if row is None:
        raise HTTPException(404, "Kampanye SEO tidak ditemukan")
    return row


def _normalize_url(url: str) -> tuple[str, str]:
    value = url.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, "URL harus memakai HTTP/HTTPS dan tidak boleh berisi kredensial")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or "." not in host:
        raise HTTPException(422, "URL kampanye harus memakai domain publik")
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise HTTPException(422, "URL kampanye tidak boleh memakai alamat IP privat atau khusus")
    except ValueError:
        pass
    return value, host


def _campaign_view(session: Session, c: SeoCampaign, detail: bool = False) -> dict:
    out = {"id": c.id, "name": c.name, "website_url": c.website_url, "allowed_domains": c.allowed_domains,
           "site_id": c.site_id, "project_id": c.project_id, "target_country": c.target_country, "target_language": c.target_language,
           "target_location": c.target_location, "primary_keywords": c.primary_keywords, "objective": c.objective,
           "target_value": c.target_value, "baseline": c.baseline, "baseline_source": c.baseline_source,
           "starts_on": c.starts_on.isoformat() if c.starts_on else None,
           "review_on": c.review_on.isoformat() if c.review_on else None, "api_budget_idr": c.api_budget_idr,
           "external_budget_idr": c.external_budget_idr, "autonomy": c.autonomy, "approval_policy": c.approval_policy,
           "status": c.status, "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat()}
    out["keywords"] = [_keyword_view(k) for k in session.scalars(select(SeoKeyword).where(SeoKeyword.campaign_id == c.id).order_by(SeoKeyword.created_at, SeoKeyword.id))]
    out["recommendations"] = [_recommendation_view(r) for r in session.scalars(select(SeoRecommendation).where(SeoRecommendation.campaign_id == c.id).order_by(SeoRecommendation.priority_order, SeoRecommendation.created_at))]
    if detail:
        out["external_integrations"] = {"search_console": "not_connected", "analytics": "not_connected"}
    out["history"] = [{"id": e.id, "kind": e.kind, "actor": e.actor, "details": e.details, "created_at": e.created_at.isoformat()}
                       for e in session.scalars(select(SeoCampaignEvent).where(SeoCampaignEvent.campaign_id == c.id).order_by(SeoCampaignEvent.created_at.desc()).limit(100 if detail else 10))]
    return out


def _keyword_view(k: SeoKeyword) -> dict:
    return {"id": k.id, "campaign_id": k.campaign_id, "keyword": k.keyword, "intent": k.intent, "source": k.source,
            "rationale": k.rationale, "target_page": k.target_page, "volume": k.volume, "competition": k.competition,
            "evidence_quote": k.evidence_quote, "approval_status": k.approval_status,
            "approved_at": k.approved_at.isoformat() if k.approved_at else None, "created_at": k.created_at.isoformat()}


def _recommendation_view(r: SeoRecommendation) -> dict:
    return {"id": r.id, "artifact_id": r.artifact_id, "finding_id": r.finding_id, "category": r.category,
            "title": r.title, "severity": r.severity, "evidence": r.evidence, "recommendation": r.recommendation,
            "impact_basis": r.impact_basis, "confidence": r.confidence, "effort": r.effort, "risk": r.risk,
            "dependencies": r.dependencies, "acceptance_criteria": r.acceptance_criteria, "verification_method": r.verification_method,
            "priority_order": r.priority_order, "status": r.status, "decision_note": r.decision_note,
            "created_at": r.created_at.isoformat()}


def _event(session: Session, campaign_id: str, kind: str, details: dict | None = None) -> None:
    session.add(SeoCampaignEvent(campaign_id=campaign_id, kind=kind, actor=ACTOR, details=details or {}))


def _ensure_no_active_campaign_task(session: Session, campaign_id: str) -> None:
    active = session.scalar(select(Task.id).where(Task.params["campaign_id"].as_string() == campaign_id,
        Task.status.in_(["draft", "pending_approval", "queued", "running", "interrupted"])).limit(1))
    if active:
        raise HTTPException(409, "Masih ada task SEO kampanye yang belum selesai; tunggu atau periksa task tersebut sebelum membuat duplikat")


@router.get("/campaigns")
def list_campaigns(session: SessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 100):
    rows = session.scalars(select(SeoCampaign).order_by(SeoCampaign.updated_at.desc()).limit(limit))
    return [_campaign_view(session, c) for c in rows]


@router.post("/campaigns", status_code=201)
def create_campaign(body: CampaignCreate, session: SessionDep):
    url, host = _normalize_url(body.website_url)
    site = session.get(Site, body.site_id) if body.site_id else None
    if body.site_id and (site is None or site.status != "active"):
        raise HTTPException(404, "Situs aktif tidak ditemukan")
    if site:
        _, site_host = _normalize_url(site.url)
        if host != site_host:
            raise HTTPException(422, "URL kampanye harus satu domain dengan situs proyek yang dipilih")
    starts = body.starts_on
    review = body.review_on
    if starts and starts.tzinfo is None:
        starts = starts.replace(tzinfo=timezone.utc)
    if review and review.tzinfo is None:
        review = review.replace(tzinfo=timezone.utc)
    if starts and review and review < starts:
        raise HTTPException(422, "Tanggal evaluasi tidak boleh sebelum tanggal mulai")
    c = SeoCampaign(name=body.name.strip(), website_url=url, allowed_domains=[host], site_id=site.id if site else None,
                    project_id=site.project_id if site else None, target_country=body.target_country, target_language=body.target_language,
                    target_location=body.target_location, primary_keywords=list(dict.fromkeys(k.strip() for k in body.primary_keywords if k.strip())),
                    objective=body.objective, target_value=body.target_value, baseline=body.baseline, baseline_source=body.baseline_source,
                    starts_on=starts, review_on=review,
                    api_budget_idr=body.api_budget_idr, external_budget_idr=body.external_budget_idr, autonomy=body.autonomy,
                    approval_policy={"production_write_requires_approval": True, "external_publish_requires_approval": True}, status="draft")
    session.add(c)
    session.flush()
    _event(session, c.id, "created", {"site_id": c.site_id, "autonomy": c.autonomy})
    session.commit()
    return _campaign_view(session, c, detail=True)


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str, session: SessionDep):
    return _campaign_view(session, _campaign_or_404(session, campaign_id), detail=True)


@router.get("/campaigns/{campaign_id}/report")
def export_campaign_report(campaign_id: str, session: SessionDep):
    c = _campaign_or_404(session, campaign_id)
    campaign = _campaign_view(session, c, detail=True)
    artifacts = session.scalars(select(MarketingArtifact).order_by(MarketingArtifact.created_at.desc()).limit(2000))
    related = [{"id": a.id, "kind": a.kind, "title": a.title, "summary": a.summary, "task_id": a.task_id,
                "created_at": a.created_at.isoformat(), "data": a.data}
               for a in artifacts if (a.data or {}).get("campaign_id") == c.id]
    report = {"report_type": "seo_campaign", "generated_at": utcnow().isoformat(), "campaign": campaign,
              "artifacts": related, "data_quality": {"gsc": "not_connected", "analytics": "not_connected",
                  "rankings": "unavailable unless imported from an authorized source", "estimates": "not generated"}}
    return JSONResponse(report, headers={"Content-Disposition": f'attachment; filename="seo-campaign-{c.id}.json"'})


@router.patch("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, body: CampaignUpdate, session: SessionDep):
    c = _campaign_or_404(session, campaign_id)
    if c.status in {"completed", "archived"}:
        raise HTTPException(409, "Kampanye selesai/arsip tidak dapat diubah")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "website_url" in changes and changes["website_url"]:
        normalized, host = _normalize_url(changes["website_url"])
        if host not in c.allowed_domains:
            raise HTTPException(422, "Domain website harus tetap berada dalam domain yang diizinkan")
        changes["website_url"] = normalized
    if "primary_keywords" in changes and changes["primary_keywords"] is not None:
        changes["primary_keywords"] = list(dict.fromkeys(k.strip() for k in changes["primary_keywords"] if k.strip()))
    for key in ("starts_on", "review_on"):
        if key in changes and changes[key] and changes[key].tzinfo is None:
            changes[key] = changes[key].replace(tzinfo=timezone.utc)
    old = {k: (getattr(c, k).isoformat() if isinstance(getattr(c, k), datetime) else getattr(c, k)) for k in changes}
    for key, value in changes.items():
        setattr(c, key, value)
    if c.starts_on and c.review_on and c.review_on < c.starts_on:
        raise HTTPException(422, "Tanggal evaluasi tidak boleh sebelum tanggal mulai")
    _event(session, c.id, "configuration_updated", {"fields": sorted(changes), "before": old})
    session.commit()
    return _campaign_view(session, c, detail=True)


@router.post("/campaigns/{campaign_id}/status")
def set_campaign_status(campaign_id: str, body: CampaignStatusBody, session: SessionDep):
    c = _campaign_or_404(session, campaign_id)
    if body.status == c.status:
        return _campaign_view(session, c)
    if body.status not in CAMPAIGN_TRANSITIONS[c.status]:
        raise HTTPException(409, f"Transisi kampanye {c.status} -> {body.status} tidak diizinkan")
    previous = c.status
    c.status = body.status
    _event(session, c.id, "status_changed", {"from": previous, "to": c.status})
    session.commit()
    return _campaign_view(session, c)


@router.post("/campaigns/{campaign_id}/tasks/audit", status_code=201)
def campaign_audit(campaign_id: str, request: Request, session: SessionDep):
    c = _campaign_or_404(session, campaign_id)
    if not c.site_id and not getattr(request.app.state.settings, "web_access_enabled", False):
        raise HTTPException(422, "Akses web dinonaktifkan; aktifkan akses web di AI Control Center atau daftarkan situs proyek")
    if c.site_id:
        site = session.get(Site, c.site_id)
        if site is None or site.status != "active":
            raise HTTPException(409, "Situs kampanye tidak aktif")
    if c.status not in {"draft", "planning", "paused"}:
        raise HTTPException(409, f"Audit tidak dapat dimulai pada status {c.status}")
    _ensure_no_active_campaign_task(session, c.id)
    result = _queue(session, request, title=f"Audit SEO kampanye: {c.name[:70]}", role="seo_specialist", action="seo_audit",
                    params={"site_id": c.site_id, "campaign_id": c.id, "url": c.website_url})
    c.status = "auditing"
    _event(session, c.id, "audit_queued", {"task_id": result["task_id"]})
    session.commit()
    return result


@router.post("/campaigns/{campaign_id}/tasks/keywords", status_code=201)
def campaign_keyword_suggestions(campaign_id: str, body: CampaignKeywordSuggest, request: Request, session: SessionDep):
    c = _campaign_or_404(session, campaign_id)
    topic = (body.topic or ", ".join(c.primary_keywords[:10]) or c.name).strip()
    if not c.site_id and not body.material.strip():
        raise HTTPException(422, "Tambahkan materi bisnis atau daftarkan situs dari proyek agar agent punya sumber nyata untuk riset keyword")
    if c.status in {"completed", "archived", "failed"}:
        raise HTTPException(409, f"Saran keyword tidak dapat dibuat pada status {c.status}")
    _ensure_no_active_campaign_task(session, c.id)
    result = _queue(session, request, title=f"Saran keyword SEO: {c.name[:70]}", role="seo_specialist", action="keyword_research",
                    params={"campaign_id": c.id, "site_id": c.site_id, "topic": topic, "material": body.material.strip()})
    _event(session, c.id, "keyword_suggestions_queued", {"task_id": result["task_id"]})
    session.commit()
    return result


@router.post("/campaigns/{campaign_id}/tasks/content-plan", status_code=201)
def campaign_content_plan(campaign_id: str, body: CampaignBriefRequest, request: Request, session: SessionDep):
    c = _campaign_or_404(session, campaign_id)
    keyword = session.scalar(select(SeoKeyword).where(SeoKeyword.id == body.keyword_id, SeoKeyword.campaign_id == c.id))
    if keyword is None:
        raise HTTPException(404, "Keyword kampanye tidak ditemukan")
    if keyword.approval_status != "approved":
        raise HTTPException(409, "Setujui keyword sebelum membuat content plan")
    if not c.site_id and not body.material.strip():
        raise HTTPException(422, "Tambahkan materi sumber atau daftarkan situs proyek sebelum membuat content plan")
    _ensure_no_active_campaign_task(session, c.id)
    result = _queue(session, request, title=f"Content plan SEO: {keyword.keyword[:90]}", role="seo_specialist", action="content_brief",
                    params={"campaign_id": c.id, "site_id": c.site_id, "topic": keyword.keyword, "keyword": keyword.keyword,
                            "material": body.material.strip()})
    _event(session, c.id, "content_plan_queued", {"task_id": result["task_id"], "keyword_id": keyword.id})
    session.commit()
    return result


@router.get("/campaigns/{campaign_id}/keywords")
def campaign_keywords(campaign_id: str, session: SessionDep):
    _campaign_or_404(session, campaign_id)
    return [_keyword_view(k) for k in session.scalars(select(SeoKeyword).where(SeoKeyword.campaign_id == campaign_id).order_by(SeoKeyword.created_at, SeoKeyword.id))]


@router.post("/campaigns/{campaign_id}/keywords", status_code=201)
def add_campaign_keyword(campaign_id: str, body: CampaignKeywordCreate, session: SessionDep):
    _campaign_or_404(session, campaign_id)
    keyword = " ".join(body.keyword.split())
    if session.scalar(select(SeoKeyword.id).where(SeoKeyword.campaign_id == campaign_id, SeoKeyword.keyword == keyword)):
        raise HTTPException(409, "Keyword tersebut sudah ada di kampanye")
    row = SeoKeyword(campaign_id=campaign_id, keyword=keyword, intent=body.intent, rationale=body.rationale.strip(),
                     target_page=body.target_page, source="manual", approval_status="pending")
    session.add(row)
    session.flush()
    _event(session, campaign_id, "keyword_added", {"keyword_id": row.id, "source": "manual"})
    session.commit()
    return _keyword_view(row)


@router.post("/campaigns/{campaign_id}/keywords/{keyword_id}/decision")
def decide_campaign_keyword(campaign_id: str, keyword_id: str, body: CampaignKeywordDecision, session: SessionDep):
    _campaign_or_404(session, campaign_id)
    row = session.scalar(select(SeoKeyword).where(SeoKeyword.id == keyword_id, SeoKeyword.campaign_id == campaign_id))
    if row is None:
        raise HTTPException(404, "Keyword kampanye tidak ditemukan")
    row.approval_status = body.status
    row.approved_at = utcnow() if body.status == "approved" else None
    _event(session, campaign_id, "keyword_decided", {"keyword_id": row.id, "decision": body.status})
    session.commit()
    return _keyword_view(row)


@router.post("/campaigns/{campaign_id}/recommendations/{recommendation_id}/decision")
def decide_campaign_recommendation(campaign_id: str, recommendation_id: str, body: RecommendationDecision, session: SessionDep):
    _campaign_or_404(session, campaign_id)
    row = session.scalar(select(SeoRecommendation).where(SeoRecommendation.id == recommendation_id,
                                                          SeoRecommendation.campaign_id == campaign_id))
    if row is None:
        raise HTTPException(404, "Rekomendasi kampanye tidak ditemukan")
    transitions = {"proposed": {"approved", "rejected"}, "approved": {"in_progress", "completed"},
                   "in_progress": {"completed"}, "rejected": set(), "completed": set()}
    if body.status not in transitions.get(row.status, set()):
        raise HTTPException(409, f"Transisi rekomendasi {row.status} -> {body.status} tidak diizinkan")
    previous = row.status
    row.status, row.decision_note = body.status, body.note
    _event(session, campaign_id, "recommendation_status_changed", {"recommendation_id": row.id, "from": previous,
                                                                   "to": row.status, "note": body.note})
    session.commit()
    return _recommendation_view(row)


@router.post("/campaigns/{campaign_id}/keywords/decisions")
def bulk_decide_campaign_keywords(campaign_id: str, body: CampaignKeywordBulkDecision, session: SessionDep):
    _campaign_or_404(session, campaign_id)
    ids = list(dict.fromkeys(body.keyword_ids))
    rows = list(session.scalars(select(SeoKeyword).where(SeoKeyword.campaign_id == campaign_id, SeoKeyword.id.in_(ids))))
    if len(rows) != len(ids):
        raise HTTPException(404, "Satu atau lebih keyword tidak ditemukan dalam kampanye ini")
    when = utcnow() if body.status == "approved" else None
    for row in rows:
        row.approval_status, row.approved_at = body.status, when
    _event(session, campaign_id, "keywords_decided_bulk", {"keyword_ids": ids, "decision": body.status})
    session.commit()
    return [_keyword_view(row) for row in rows]


@router.delete("/campaigns/{campaign_id}/keywords/{keyword_id}", status_code=204)
def delete_campaign_keyword(campaign_id: str, keyword_id: str, session: SessionDep):
    _campaign_or_404(session, campaign_id)
    row = session.scalar(select(SeoKeyword).where(SeoKeyword.id == keyword_id, SeoKeyword.campaign_id == campaign_id))
    if row is None:
        raise HTTPException(404, "Keyword kampanye tidak ditemukan")
    _event(session, campaign_id, "keyword_deleted", {"keyword_id": row.id})
    session.delete(row)
    session.commit()


@router.post("/tasks/audit", status_code=201)
def audit_task(body: AuditBody, request: Request, session: SessionDep):
    return _queue(session, request, title=f"Audit SEO: {body.url[:80] or 'halaman'}", role="seo_specialist", action="seo_audit",
                  params={"url": body.url, "html": body.html, "robots_txt": body.robots_txt, "sitemap_xml": body.sitemap_xml})


@router.post("/tasks/keywords", status_code=201)
def keywords_task(body: KeywordBody, request: Request, session: SessionDep):
    if body.product_id and session.get(Product, body.product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")
    return _queue(session, request, title=f"Kata kunci: {body.topic[:80]}", role="seo_specialist", action="keyword_research",
                  params={"topic": body.topic, "material": body.material, "product_id": body.product_id})


@router.post("/tasks/brief", status_code=201)
def brief_task(body: BriefBody, request: Request, session: SessionDep):
    if body.product_id and session.get(Product, body.product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")
    return _queue(session, request, title=f"Brief konten: {body.topic[:80]}", role="seo_specialist", action="content_brief",
                  params={"topic": body.topic, "keyword": body.keyword, "material": body.material, "product_id": body.product_id})


@router.post("/tasks/analysis", status_code=201)
def analysis_task(request: Request, session: SessionDep):
    return _queue(session, request, title="Laporan analitik pemasaran", role="marketing_analytics", action="marketing_analysis", params={})


@router.get("/artifacts")
def artifacts(session: SessionDep, kind: Literal["audit", "keywords", "brief", "analysis"] | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 30):
    q = select(MarketingArtifact).order_by(MarketingArtifact.created_at.desc()).limit(limit)
    if kind:
        q = q.where(MarketingArtifact.kind == kind)
    return [_view(a) for a in session.scalars(q)]


@router.get("/artifacts/{artifact_id}")
def artifact(artifact_id: str, session: SessionDep):
    a = session.get(MarketingArtifact, artifact_id)
    if a is None:
        raise HTTPException(404, "Artefak tidak ditemukan")
    return _view(a, full=True)


@router.post("/metrics", status_code=201)
def add_metric(body: MetricBody, session: SessionDep):
    try:
        row = seo.record_metric(session, body.metric, body.value, page=body.page, period=body.period, recorded_by=ACTOR, note=body.note)
    except MarketingError as e:
        return JSONResponse({"detail": e.message, "code": e.code}, status_code=422)
    session.commit()
    return {"id": row.id, "metric": row.metric, "value": row.value, "period": row.period, "page": row.page}


@router.get("/metrics")
def metrics(session: SessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    rows = session.scalars(select(SeoMetric).order_by(SeoMetric.created_at.desc()).limit(limit))
    return [{"id": m.id, "metric": m.metric, "value": m.value, "period": m.period, "page": m.page, "note": m.note, "recorded_by": m.recorded_by} for m in rows]


@router.get("/kpis")
def kpis(session: SessionDep):
    return seo.kpis(session)


@router.post("/artifacts/{artifact_id}/handoff", status_code=201)
def handoff(artifact_id: str, body: HandoffBody, session: SessionDep):
    """Rekomendasi teknis -> satu task DRAFT untuk Engineering (tidak otomatis diantrekan). Satu artefak hanya dapat diserahkan sekali."""
    a = session.get(MarketingArtifact, artifact_id)
    if a is None:
        raise HTTPException(404, "Artefak tidak ditemukan")
    if a.kind != "audit":
        raise HTTPException(422, "Hanya artefak audit yang memuat rekomendasi teknis")
    if a.handed_off_task_id:
        raise HTTPException(409, "Artefak ini sudah diserahkan ke Engineering")
    site = session.get(Site, a.data.get("site_id")) if a.data.get("site_id") else None
    project_id = body.project_id or (site.project_id if site else None)
    if not project_id:
        raise HTTPException(422, "Tentukan proyek Engineering tujuan")
    if session.get(Project, project_id) is None:
        raise HTTPException(404, "Proyek tidak ditemukan")
    todo = [f for f in a.data.get("findings", []) if f["severity"] in {"critical", "warning"} and f["recommendation"]]
    if not todo:
        raise HTTPException(422, "Tidak ada temuan kritis/peringatan yang perlu ditangani")
    desc = "Rekomendasi hasil audit SEO (belum diverifikasi oleh QA):\n" + "\n".join(f"- [{f['severity']}] {'[' + f['page'] + '] ' if f.get('page') else ''}{f['message']} -> {f['recommendation']}" for f in todo)
    t = tasks.create_task(session, project_id=project_id, title=f"Perbaikan SEO: {a.title[:90]}", description=desc[:3900], role="developer",
                          action_type="code_change", created_by="seo_specialist",
                          acceptance_criteria=["Temuan kritis/peringatan pada audit tertangani", "Audit SEO diulang dan temuan tidak muncul lagi", "QA dan Reviewer lulus"])
    a.handed_off_task_id = t.id
    session.commit()
    return {"task_id": t.id, "status": t.status, "findings": len(todo)}


# ------------------------------------------------------------------ situs yang dipasarkan

def _site_or_404(session: Session, site_id: str) -> Site:
    s = session.get(Site, site_id)
    if s is None:
        raise HTTPException(404, "Situs tidak ditemukan")
    return s


def _site_view(session: Session, request: Request, s: Site, detail: bool = False) -> dict:
    from app.projects.storage import ProjectStorage
    out = {"id": s.id, "name": s.name, "url": s.url, "project_id": s.project_id, "language": s.language, "status": s.status}
    audits = session.scalars(select(MarketingArtifact).where(MarketingArtifact.kind == "audit").order_by(MarketingArtifact.created_at.desc()).limit(50)).all()
    mine = next((a for a in audits if (a.data or {}).get("site_id") == s.id), None)
    out["last_audit"] = {"id": mine.id, "created_at": mine.created_at.isoformat(), "counts": mine.data.get("counts")} if mine else None
    if detail:
        storage = ProjectStorage(request.app.state.settings.projects_dir)
        bundle = sites.collect_pages(sites.site_root(storage, s), s.url)
        out["pages"] = [{"path": p["path"], "url": p["url"], "bytes": len(p["html"])} for p in bundle["pages"]]
        out["has_robots"], out["has_sitemap"] = bool(bundle["robots_txt"].strip()), bool(bundle["sitemap_xml"].strip())
    return out


@router.get("/sites")
def list_sites(request: Request, session: SessionDep):
    return [_site_view(session, request, s) for s in session.scalars(select(Site).where(Site.status == "active").order_by(Site.created_at))]


@router.get("/sites/{site_id}")
def get_site(site_id: str, request: Request, session: SessionDep):
    return _site_view(session, request, _site_or_404(session, site_id), detail=True)


@router.post("/sites/{site_id}/tasks/audit", status_code=201)
def site_audit(site_id: str, request: Request, session: SessionDep):
    s = _site_or_404(session, site_id)
    return _queue(session, request, title=f"Audit SEO situs: {s.name[:60]}", role="seo_specialist", action="seo_audit", params={"site_id": s.id})


@router.post("/sites/{site_id}/tasks/keywords", status_code=201)
def site_keywords(site_id: str, body: SiteTaskBody, request: Request, session: SessionDep):
    s = _site_or_404(session, site_id)
    return _queue(session, request, title=f"Kata kunci situs: {s.name[:60]}", role="seo_specialist", action="keyword_research",
                  params={"site_id": s.id, "topic": body.topic, "material": body.material})


@router.post("/sites/{site_id}/tasks/brief", status_code=201)
def site_brief(site_id: str, body: SiteTaskBody, request: Request, session: SessionDep):
    s = _site_or_404(session, site_id)
    return _queue(session, request, title=f"Brief konten situs: {s.name[:60]}", role="seo_specialist", action="content_brief",
                  params={"site_id": s.id, "topic": body.topic or f"Situs {s.name}", "keyword": body.keyword, "material": body.material})
