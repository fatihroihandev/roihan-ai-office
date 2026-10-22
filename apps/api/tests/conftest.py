import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

API_DIR = Path(__file__).resolve().parents[1]
TOKEN = "token-uji-1234567890"


@pytest.fixture(scope="session")
def _template_db(tmp_path_factory):
    """Jalankan migrasi sekali per sesi tes; tiap tes memakai salinannya (jauh lebih cepat)."""
    path = tmp_path_factory.mktemp("template") / "template.db"
    subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"url=sqlite:///{path.as_posix()}", "upgrade", "head"],
        cwd=API_DIR, check=True, capture_output=True,
    )
    return path


# Evaluasi Phase 12: bila TEST_POSTGRES_URL (mis. postgresql+psycopg://user:pw@127.0.0.1:55432) diisi, seluruh tes memakai database PostgreSQL
# sementara per tes (dikloning dari templat yang sudah dimigrasi). Tanpa variabel itu, perilaku tetap SQLite seperti biasa.
PG_URL = os.environ.get("TEST_POSTGRES_URL")


@pytest.fixture(scope="session")
def _pg_template():
    if not PG_URL:
        yield None
        return
    admin = create_engine(f"{PG_URL}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text("DROP DATABASE IF EXISTS roihan_tpl WITH (FORCE)"))
        c.execute(text("CREATE DATABASE roihan_tpl"))
    subprocess.run([sys.executable, "-m", "alembic", "-x", f"url={PG_URL}/roihan_tpl", "upgrade", "head"], cwd=API_DIR, check=True, capture_output=True)
    yield admin
    admin.dispose()


@pytest.fixture
def migrated_db(tmp_path, _template_db, _pg_template):
    if _pg_template is not None:
        import uuid
        name = f"t_{uuid.uuid4().hex[:12]}"
        with _pg_template.connect() as c:
            c.execute(text(f"CREATE DATABASE {name} TEMPLATE roihan_tpl"))
        yield f"{PG_URL}/{name}"
        with _pg_template.connect() as c:
            c.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        return
    dest = tmp_path / "test.db"
    shutil.copyfile(_template_db, dest)
    yield f"sqlite:///{dest.as_posix()}"


@pytest.fixture
def settings(migrated_db, tmp_path):
    return Settings(
        _env_file=None, app_local_token=TOKEN, database_url=migrated_db, ollama_enabled=False,
        data_dir=tmp_path / "data", max_upload_mb=1, worker_enabled=False, backup_enabled=False,
    )


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {TOKEN}"}
