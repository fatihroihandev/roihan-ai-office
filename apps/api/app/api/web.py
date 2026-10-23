"""Akses web terkendali (Phase 16): pengaturan, uji manual, serta pekerjaan riset dan pencarian prospek berbasis web.

Model TIDAK mengakses internet. Backend mencari/mengambil halaman (dengan saklar, batas harian, SSRF-guard, robots.txt, audit), lalu teksnya
diberikan kepada agent sebagai bahan; semua pemeriksaan bukti dan privasi agent yang ada tetap berlaku.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.marketing import _queue
from app.db.models import Product, WebRequest
from app.marketing.policy import Policy, validate_source_type, validate_url
from app.marketing.privacy import PolicyError
from app.security import require_token
from app.web.guard import WebError
from app.web.service import redact_contacts, save_web_settings, wrap_untrusted

router = APIRouter(prefix="/api/web", tags=["web"], dependencies=[Depends(require_token)])
_STATUS = {"disabled": 409, "no_search_key": 409, "quota": 429, "search_quota": 429, "timeout": 504, "search_auth": 502, "search_failed": 502,
           "network_error": 502, "dns_failed": 422, "http_error": 422}
MAX_MATERIAL = 8000


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def _err(e: WebError) -> JSONResponse:
    return JSONResponse({"detail": e.message, "code": e.code}, status_code=_STATUS.get(e.code, 422))


class WebSettingsUpdate(BaseModel):
    """Update web access and select either Brave Search or Tavily for discovery."""
    enabled: bool | None = None
    daily_limit: int | None = Field(default=None, ge=1, le=5000)
    web_search_provider: Literal["brave", "tavily"] | None = Field(default=None, description="Provider used for public web search")
    brave_api_key: str | None = Field(default=None, repr=False, max_length=300, description="Stored locally and never returned")
    tavily_api_key: str | None = Field(default=None, repr=False, max_length=300, description="Stored locally and never returned")
    clear_api_key: bool = Field(default=False, description="Clear the selected provider's API key")


class WebApiKeyStatus(BaseModel):
    brave: bool
    tavily: bool


class WebStatusOut(BaseModel):
    enabled: bool
    search_provider: Literal["brave", "tavily"]
    search_available: bool
    api_key_configured: bool
    api_keys_configured: WebApiKeyStatus
    daily_limit: int
    used_today: int
    remaining_today: int


class SearchBody(BaseModel):
    query: str = Field(min_length=2, max_length=300)


class FetchBody(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class ResearchBody(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    query: str | None = Field(default=None, max_length=300)
    max_pages: int = Field(default=3, ge=1, le=4)
    product_id: str | None = None


class ProspectingBody(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    source_type: str = Field(default="public_website", max_length=40)
    max_pages: int = Field(default=3, ge=1, le=5)
    product_id: str | None = None


@router.get("", response_model=WebStatusOut)
def status(request: Request):
    return request.app.state.web.status()


@router.patch("", response_model=WebStatusOut)
def update(body: WebSettingsUpdate, request: Request):
    s = request.app.state.settings
    provided_keys = [k for k in (body.brave_api_key, body.tavily_api_key) if k and k.strip()]
    if body.clear_api_key and provided_keys:
        raise HTTPException(422, "Pilih mengganti atau menghapus API key, bukan keduanya")
    if len(provided_keys) > 1:
        raise HTTPException(422, "Kirim satu API key penyedia pencarian saja")
    if (body.enabled is None and body.daily_limit is None and body.web_search_provider is None
            and not provided_keys and not body.clear_api_key):
        raise HTTPException(422, "Tidak ada pengaturan yang diubah")
    if body.enabled is not None:
        s.web_access_enabled = body.enabled
    if body.daily_limit is not None:
        s.web_daily_limit = body.daily_limit
    if body.web_search_provider is not None:
        s.web_search_provider = body.web_search_provider
    if body.clear_api_key:
        if s.web_search_provider == "tavily":
            s.tavily_api_key = ""
        else:
            s.brave_api_key = ""
    elif body.brave_api_key and body.brave_api_key.strip():
        s.brave_api_key = body.brave_api_key.strip()
    elif body.tavily_api_key and body.tavily_api_key.strip():
        s.tavily_api_key = body.tavily_api_key.strip()
    save_web_settings(s)
    return request.app.state.web.status()


@router.get("/requests")
def requests_log(session: SessionDep, limit: int = 30):
    rows = session.scalars(select(WebRequest).order_by(WebRequest.created_at.desc()).limit(max(1, min(limit, 200))))
    return [{"id": r.id, "created_at": r.created_at.isoformat(), "kind": r.kind, "target": r.target, "status": r.status, "bytes": r.bytes, "detail": r.detail, "task_id": r.task_id}
            for r in rows]


@router.post("/search")
async def search(body: SearchBody, request: Request):
    try:
        return {"results": await request.app.state.web.search(body.query)}
    except WebError as e:
        return _err(e)


@router.post("/fetch")
async def fetch(body: FetchBody, request: Request):
    try:
        page = await request.app.state.web.fetch(body.url)
    except WebError as e:
        return _err(e)
    return {**page, "text": page["text"][:2000]}


def _check_product(session: Session, product_id: str | None) -> None:
    if product_id and session.get(Product, product_id) is None:
        raise HTTPException(404, "Produk tidak ditemukan")


@router.post("/tasks/research", status_code=201)
async def research(body: ResearchBody, request: Request, session: SessionDep):
    """Cari di web lalu antrekan task Market Research dengan teks halaman sebagai materi (kontak pribadi disamarkan)."""
    _check_product(session, body.product_id)
    try:
        got = await request.app.state.web.gather(body.query or body.topic, body.max_pages)
    except WebError as e:
        return _err(e)
    if not got["docs"]:
        return JSONResponse({"detail": "Tidak ada halaman yang dapat diambil", "failed": got["failed"], "code": "no_pages"}, status_code=422)
    share = MAX_MATERIAL // len(got["docs"])
    material = "\n\n".join(wrap_untrusted(d["url"], redact_contacts(f"{d['title']}\n{d['description']}\n{d['text']}"))[:share] for d in got["docs"])[:MAX_MATERIAL]
    out = _queue(session, request, title=f"Riset web: {body.topic[:70]}", role="market_research", action="market_research",
                 params={"topic": body.topic, "material": material, "product_id": body.product_id})
    return {**out, "sources": [{"url": d["url"], "title": d["title"], "injection_suspected": d["injection_suspected"]} for d in got["docs"]], "failed": got["failed"]}


@router.post("/tasks/prospecting", status_code=201)
async def prospecting(body: ProspectingBody, request: Request, session: SessionDep):
    """Cari di web lalu antrekan satu task intake prospek per halaman. Agent hanya mengekstrak yang tertulis; aturan sumber dan privasi tetap berlaku."""
    _check_product(session, body.product_id)
    policy = Policy.from_settings(request.app.state.settings)
    try:
        rule = validate_source_type(policy, body.source_type)
    except PolicyError as e:
        return JSONResponse({"detail": e.message, "code": e.code}, status_code=422)
    try:
        got = await request.app.state.web.gather(body.query, body.max_pages)
    except WebError as e:
        return _err(e)
    queued, skipped = [], list(got["failed"])
    for d in got["docs"]:
        try:
            validate_url(d["url"], rule["needs_url"])
        except PolicyError as e:
            skipped.append({"url": d["url"], "code": e.code, "message": e.message})
            continue
        raw = f"{d['title']}\n{d['description']}\n{d['text']}"[:MAX_MATERIAL]
        out = _queue(session, request, title=f"Intake web: {d['title'][:60] or d['url'][:60]}", role="lead_generation", action="lead_intake",
                     params={"source": {"source_type": body.source_type, "url": d["url"], "title": d["title"][:200]}, "raw_text": raw, "product_id": body.product_id})
        queued.append({"task_id": out["task_id"], "url": d["url"], "title": d["title"], "injection_suspected": d["injection_suspected"]})
    if not queued:
        return JSONResponse({"detail": "Tidak ada halaman yang dapat diproses", "skipped": skipped, "code": "no_pages"}, status_code=422)
    return {"queued": queued, "skipped": skipped}
