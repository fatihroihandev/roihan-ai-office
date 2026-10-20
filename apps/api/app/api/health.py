import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.security import require_token

router = APIRouter(prefix="/api", tags=["health"])

APP_VERSION = "0.1.0"


def _check_db(engine) -> str:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "up"
    except Exception:
        return "down"


async def _check_ollama(settings) -> str:
    if not settings.ollama_enabled:
        return "disabled"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
        return "up" if r.status_code == 200 else "down"
    except Exception:
        return "down"


@router.get("/health")
def health(request: Request):
    """Publik dan minimal: hanya status keseluruhan."""
    db = _check_db(request.app.state.engine)
    return {"status": "ok" if db == "up" else "error", "version": APP_VERSION}


@router.get("/health/details", dependencies=[Depends(require_token)])
async def health_details(request: Request):
    settings = request.app.state.settings
    db = _check_db(request.app.state.engine)
    ollama = await _check_ollama(settings)
    if db != "up":
        status = "error"
    elif ollama == "down":
        status = "degraded"
    else:
        status = "ok"
    return {
        "status": status,
        "version": APP_VERSION,
        "environment": settings.app_env,
        "components": {"database": db, "ollama": ollama},
        "paid_calls_allowed": settings.budget_allow_paid_calls,
    }
