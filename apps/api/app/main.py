import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, health, projects
from app.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory
from app.logging_config import correlation_id, new_correlation_id, setup_logging
from app.providers.base import ModelProvider
from app.providers.gateway import ModelGateway
from app.providers.registry import build_registry

logger = logging.getLogger("roihan.api")


def create_app(settings: Settings | None = None, providers: dict[str, ModelProvider] | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.secret_values, settings.redact_secrets_in_logs)

    app = FastAPI(title="Roihan Software House API", version=health.APP_VERSION)
    app.state.settings = settings
    app.state.engine = create_db_engine(settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.registry = build_registry(settings, providers)
    app.state.gateway = ModelGateway(app.state.registry, settings, app.state.session_factory)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        cid = request.headers.get("x-request-id") or new_correlation_id()
        token = correlation_id.set(cid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = cid
            logger.info(
                "request",
                extra={"method": request.method, "path": request.url.path, "status": response.status_code,
                       "duration_ms": round((time.perf_counter() - start) * 1000, 1)},
            )
            return response
        finally:
            correlation_id.reset(token)

    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(ai.router)
    return app


def get_app() -> FastAPI:
    """Factory untuk uvicorn: uvicorn app.main:get_app --factory"""
    return create_app()
