import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.db.models import ModelCapability, ModelUsage
from app.providers.base import GatewayBlocked, GenerateRequest, ProviderError, ProviderErrorKind as K
from app.providers.capabilities import sync_provider_models
from app.schemas.ai import GenerateBody, GenerateOut, ModelOut, UsageOut, UsageRowOut
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


@router.get("/providers")
async def list_providers(request: Request):
    entries = request.app.state.registry.all()
    healths = await asyncio.gather(*(_health_of(e) for e in entries))
    return [
        {"name": e.name, "kind": e.kind, "is_paid": e.is_paid, "enabled": e.enabled,
         "implemented": e.implemented, "health": h}
        for e, h in zip(entries, healths)
    ]


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
