import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from app.config import Settings
from app.db.base import utcnow
from app.db.models import Project, Task
from app.db.session import create_db_engine, create_session_factory
from app.projects.storage import ProjectStorage
from app.providers.gateway import ModelGateway
from app.providers.registry import build_registry
from app.routing.router import ModelRouter
from app.tasks import service
from app.tasks.worker import TaskWorker
from tests.conftest import TOKEN
from tests.fakes import FakeProvider


@dataclass
class Env:
    settings: Settings
    sf: object
    provider: FakeProvider
    gateway: ModelGateway
    router: ModelRouter
    storage: ProjectStorage
    worker: TaskWorker


def build_env(migrated_db, tmp_path, provider=None, executors=None, sandbox=None, **kw) -> Env:
    kw.setdefault("retry_backoff_base_s", 0.0)
    kw.setdefault("ollama_enabled", True)
    settings = Settings(_env_file=None, app_local_token=TOKEN, database_url=migrated_db, data_dir=tmp_path / "data",
                        worker_enabled=False, **kw)
    sf = create_session_factory(create_db_engine(migrated_db))
    provider = provider or FakeProvider()
    registry = build_registry(settings, {"ollama": provider})
    gateway, router = ModelGateway(registry, settings, sf), ModelRouter(registry, settings, sf)
    storage = ProjectStorage(settings.projects_dir)
    worker = TaskWorker(settings, sf, gateway, router, storage, executors, sandbox)
    return Env(settings, sf, provider, gateway, router, storage, worker)


def make_project(env: Env, name="Proyek Uji") -> str:
    with env.sf() as s:
        p = Project(name=name)
        s.add(p)
        s.commit()
        env.storage.create_layout(p.id)
        return p.id


def add_task(env: Env, project_id: str, title="Tugas", role="analyst", action_type="analysis", queue=True, **kw) -> str:
    with env.sf() as s:
        t = service.create_task(s, project_id=project_id, title=title, role=role, action_type=action_type, **kw)
        if queue:
            service.queue_task(s, t)
        s.commit()
        return t.id


def get(env: Env, task_id: str) -> Task:
    with env.sf() as s:
        return s.get(Task, task_id)


def set_available_now(env: Env, task_id: str) -> None:
    with env.sf() as s:
        s.get(Task, task_id).available_at = utcnow()
        s.commit()


def run(coro):
    return asyncio.run(coro)


def drain(env: Env, limit=20) -> int:
    """Jalankan worker sampai tidak ada pekerjaan siap."""
    n = 0
    while n < limit and run(env.worker.run_once()):
        n += 1
    return n


def events_of(env: Env, task_id: str) -> list:
    from app.db.models import TaskEvent
    with env.sf() as s:
        return [(e.from_status, e.to_status, e.reason) for e in
                s.scalars(select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.seq))]
