"""SEO & Digital Marketing (Phase 14): antre pekerjaan SEO/analitik, artefak, metrik manual, KPI, dan serah terima ke Engineering.

Semua artefak hanya untuk ditinjau. Serah terima membuat task DRAFT untuk Engineering (CEO yang mengantrekan); tidak ada perubahan
kode produksi atau publikasi dari sini.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.marketing import ACTOR, _queue
from app.db.models import MarketingArtifact, Product, Project, SeoMetric, Site
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


def _view(a: MarketingArtifact, full: bool = False) -> dict:
    out = {"id": a.id, "kind": a.kind, "title": a.title, "summary": a.summary, "task_id": a.task_id, "created_at": a.created_at.isoformat(),
           "verified_count": a.verified_count, "unverified_count": a.unverified_count, "handed_off_to": a.handed_off_task_id}
    if full:
        out["data"] = a.data
    return out


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
