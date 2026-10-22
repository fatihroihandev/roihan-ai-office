import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, approvals, backups, dashboard, engineering, events, health, marketing, products, projects, tasks
from app.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory
from app.logging_config import correlation_id, new_correlation_id, setup_logging
from app.providers.base import ModelProvider
from app.providers.gateway import ModelGateway
from app.projects.storage import ProjectStorage
from app.providers.registry import build_registry
from app.routing.router import ModelRouter
from app.sandbox.base import Sandbox
from app.sandbox.factory import build_sandbox
from app.tasks.executors import Executor
from app.tasks.worker import TaskWorker

logger = logging.getLogger("roihan.api")

# Respons API adalah JSON: tidak boleh ditebak tipenya, dibingkai, di-cache, atau membocorkan referrer.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


async def _backup_loop(app: FastAPI) -> None:
    """Cadangan terjadwal: satu segera bila belum ada yang cukup baru, lalu tiap `backup_interval_hours`. Kegagalan hanya dicatat."""
    from app.api.backups import run_backup

    settings = app.state.settings
    interval = settings.backup_interval_hours * 3600
    while True:
        try:
            await asyncio.to_thread(run_backup, settings, "auto")
        except Exception:
            logger.exception("backup terjadwal gagal")
        await asyncio.sleep(interval)


def create_app(settings: Settings | None = None, providers: dict[str, ModelProvider] | None = None,
               executors: dict[str, Executor] | None = None, sandbox: Sandbox | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.secret_values, settings.redact_secrets_in_logs)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if settings.worker_enabled:
            worker = app.state.worker
            task = asyncio.create_task(worker.run_forever())
        backup_task = asyncio.create_task(_backup_loop(app)) if settings.backup_enabled else None
        yield
        if backup_task is not None:
            backup_task.cancel()
        if task is not None:
            app.state.worker.stop()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="Roihan Software House API", version=health.APP_VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = create_db_engine(settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.registry = build_registry(settings, providers)
    app.state.gateway = ModelGateway(app.state.registry, settings, app.state.session_factory)
    app.state.router = ModelRouter(app.state.registry, settings, app.state.session_factory)
    app.state.ws_tickets = {}
    app.state.sandbox = sandbox or build_sandbox(settings)
    if settings.worker_enabled or executors is not None:
        app.state.worker = TaskWorker(settings, app.state.session_factory, app.state.gateway, app.state.router,
                                      ProjectStorage(settings.projects_dir), executors, app.state.sandbox)

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
            for k, v in SECURITY_HEADERS.items():
                response.headers.setdefault(k, v)
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
    app.include_router(tasks.router)
    app.include_router(events.router)
    app.include_router(engineering.router)
    app.include_router(approvals.router)
    app.include_router(products.router)
    app.include_router(marketing.router)
    app.include_router(dashboard.router)
    app.include_router(backups.router)
    return app


def get_app() -> FastAPI:
    """Factory untuk uvicorn: uvicorn app.main:get_app --factory"""
    return create_app()
