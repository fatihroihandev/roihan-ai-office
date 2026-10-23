import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.db.models import ModelCapability, ModelUsage
from app.providers.base import GatewayBlocked, GenerateRequest, ProviderError, ProviderErrorKind as K
from app.providers.capabilities import sync_provider_models
from app.providers.cloud import AnthropicProvider, GeminiProvider, OpenAIProvider
from app.providers.ollama import OllamaProvider
from app.providers.runtime_settings import save_cloud_provider_settings, save_provider_settings
from app.schemas.ai import GenerateBody, GenerateOut, ModelOut, ProviderOut, ProviderSettingsUpdate, UsageOut, UsageRowOut
from app.security import require_token

router = APIRouter(prefix="/api", tags=["ai-control-center"], dependencies=[Depends(require_token)])

_STATUS = {K.unavailable: 503, K.timeout: 504, K.model_not_found: 404, K.invalid_request: 400,
           K.upstream_error: 502, K.cancelled: 409}


def _error(status: int, message: str, **extra) -> JSONResponse:
    return JSONResponse({"detail": message, **extra}, status_code=status)


async def _health_of(entry) -> dict | None:
    if not (entry.enabled and entry.implemented and entry.provider):
        return None
    h = await entry.provider.health_check()
    return {"status": h.status, "latency_ms": h.latency_ms, "version": h.version, "error_kind": h.error_kind}


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(request: Request):
    entries = request.app.state.registry.all()
    healths = await asyncio.gather(*(_health_of(e) for e in entries))
    return [
        {"name": e.name, "kind": e.kind, "is_paid": e.is_paid, "enabled": e.enabled,
         "implemented": e.implemented, "base_url": request.app.state.settings.ollama_base_url if e.name == "ollama" else None,
         "api_key_configured": bool(getattr(request.app.state.settings, f"{e.name}_api_key", "")) if e.name != "ollama" else None,
         "health": h}
        for e, h in zip(entries, healths)
    ]


@router.patch("/providers/{name}", response_model=ProviderOut)
async def update_provider(name: str, body: ProviderSettingsUpdate, request: Request):
    """Simpan status provider dan kunci cloud secara lokal; nilai kunci tidak pernah dikembalikan."""
    entry = request.app.state.registry.get(name)
    if entry is None:
        raise HTTPException(404, "Provider tidak ditemukan")
    if not entry.implemented:
        raise HTTPException(409, "Adapter provider ini belum tersedia")
    if body.clear_api_key and body.api_key is not None:
        raise HTTPException(422, "Pilih untuk mengganti atau menghapus API key, bukan keduanya")
    if body.api_key is not None and len(body.api_key) > 500:
        raise HTTPException(422, "API key terlalu panjang")
    if name == "ollama" and (body.api_key is not None or body.clear_api_key):
        raise HTTPException(422, "Ollama tidak menggunakan API key")
    if name != "ollama" and body.base_url is not None:
        raise HTTPException(422, "Endpoint provider cloud menggunakan alamat resmi")
    if body.enabled is None and body.base_url is None and body.api_key is None and not body.clear_api_key:
        raise HTTPException(422, "Tidak ada pengaturan provider yang diubah")

    settings = request.app.state.settings
    enabled = entry.enabled if body.enabled is None else body.enabled
    if name == "ollama":
        base_url = settings.ollama_base_url if body.base_url is None else body.base_url
        save_provider_settings(settings.data_dir, enabled=enabled, base_url=base_url)
        settings.ollama_enabled, settings.ollama_base_url = enabled, base_url
        entry.enabled = enabled
        if isinstance(entry.provider, OllamaProvider):
            entry.provider = OllamaProvider(base_url, settings.ollama_timeout_s)
    else:
        api_key = "" if body.clear_api_key else body.api_key or getattr(settings, f"{name}_api_key")
        if enabled and not api_key:
            raise HTTPException(422, "Masukkan API key sebelum mengaktifkan provider")
        if body.clear_api_key and enabled:
            raise HTTPException(422, "Nonaktifkan provider sebelum menghapus API key")
        save_cloud_provider_settings(settings.data_dir, name=name, enabled=enabled, api_key=api_key)
        setattr(settings, f"{name}_enabled", enabled)
        setattr(settings, f"{name}_api_key", api_key)
        entry.enabled = enabled
        provider_type = {"openai": OpenAIProvider, "gemini": GeminiProvider, "anthropic": AnthropicProvider}[name]
        entry.provider = provider_type(api_key)
    health = await _health_of(entry)
    return {"name": entry.name, "kind": entry.kind, "is_paid": entry.is_paid, "enabled": entry.enabled,
            "implemented": entry.implemented, "base_url": settings.ollama_base_url if name == "ollama" else None,
            "api_key_configured": bool(getattr(settings, f"{name}_api_key", "")) if name != "ollama" else None,
            "health": health}


@router.get("/providers/{name}/health")
async def provider_health(name: str, request: Request):
    entry = request.app.state.registry.get(name)
    if entry is None:
        raise HTTPException(404, "Provider tidak ditemukan")
    return await _health_of(entry) or {"status": "unavailable", "latency_ms": None, "version": None, "error_kind": None}


@router.get("/models", response_model=list[ModelOut])
def list_models(request: Request, provider: str | None = None):
    with request.app.state.session_factory() as s:
        q = select(ModelCapability).order_by(ModelCapability.provider, ModelCapability.model_id)
        if provider:
            q = q.where(ModelCapability.provider == provider)
        return list(s.scalars(q))


@router.post("/models/sync", response_model=list[ModelOut])
async def sync_models(request: Request, provider: str = "ollama"):
    state = request.app.state
    entry = state.registry.get(provider)
    if entry is None:
        raise HTTPException(404, "Provider tidak ditemukan")
    if not (entry.enabled and entry.implemented and entry.provider):
        return _error(409, f"Provider '{provider}' tidak aktif atau belum tersedia", kind="provider_unavailable")
    try:
        return await sync_provider_models(state.session_factory, entry, state.settings.data_dir)
    except ProviderError as e:
        return _error(_STATUS[e.kind], e.message, kind=e.kind.value, retryable=e.retryable)


@router.post("/ai/generate", response_model=GenerateOut)
async def generate(body: GenerateBody, request: Request):
    settings = request.app.state.settings
    if len(body.prompt) > settings.ai_max_prompt_chars:
        return _error(413, f"Prompt melebihi batas {settings.ai_max_prompt_chars} karakter")
    if body.max_tokens > settings.ai_max_tokens_cap:
        return _error(422, f"max_tokens melebihi batas {settings.ai_max_tokens_cap}")

    model = body.model or settings.ollama_default_model
    req = GenerateRequest(prompt=body.prompt, system=body.system, max_tokens=body.max_tokens,
                          temperature=body.temperature, num_ctx=body.num_ctx,
                          **({"request_id": body.request_id} if body.request_id else {}))
    try:
        result = await request.app.state.gateway.generate(body.provider, model, req)
    except GatewayBlocked as e:
        return _error(403, e.message, kind="blocked", reason=e.reason, retryable=False)
    except ProviderError as e:
        return _error(_STATUS[e.kind], e.message, kind=e.kind.value, retryable=e.retryable)
    return GenerateOut(request_id=req.request_id, provider=body.provider, model=result.model, text=result.text,
                       truncated=result.truncated, usage=UsageOut(**vars(result.usage)))


@router.post("/ai/requests/{request_id}/cancel")
async def cancel_request(request_id: str, request: Request):
    return {"cancelled": await request.app.state.gateway.cancel(request_id)}


@router.get("/usage")
def usage(request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 50):
    with request.app.state.session_factory() as s:
        rows = list(s.scalars(select(ModelUsage).order_by(ModelUsage.created_at.desc()).limit(limit)))
        counts = dict(s.execute(select(ModelUsage.status, func.count()).group_by(ModelUsage.status)).all())
        tokens = s.execute(select(func.coalesce(func.sum(ModelUsage.prompt_tokens), 0),
                                  func.coalesce(func.sum(ModelUsage.completion_tokens), 0),
                                  func.coalesce(func.sum(ModelUsage.cost_idr), 0.0))).one()
    return {
        "summary": {"total": sum(counts.values()), "ok": counts.get("ok", 0), "error": counts.get("error", 0),
                    "blocked": counts.get("blocked", 0), "cancelled": counts.get("cancelled", 0),
                    "prompt_tokens": tokens[0], "completion_tokens": tokens[1], "total_cost_idr": tokens[2]},
        "items": [UsageRowOut.model_validate(r) for r in rows],
    }


@router.get("/budgets")
def budgets(request: Request):
    cfg = request.app.state.settings
    with request.app.state.session_factory() as s:
        spent = s.scalar(select(func.coalesce(func.sum(ModelUsage.cost_idr), 0.0)))
    return {
        "currency": cfg.budget_currency, "monthly_limit": cfg.budget_monthly_limit,
        "allow_paid_calls": cfg.budget_allow_paid_calls, "require_approval_for_paid_calls": True,
        "spent_total": spent, "routing": {"mode": "auto", "fallback_policy": "ask",
                                          "require_capability_match": True, "require_budget_check": True},
    }
