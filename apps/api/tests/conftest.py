import shutil
import subprocess
import sys
from pathlib import Path

import pytest
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


@pytest.fixture
def migrated_db(tmp_path, _template_db):
    dest = tmp_path / "test.db"
    shutil.copyfile(_template_db, dest)
    return f"sqlite:///{dest.as_posix()}"


@pytest.fixture
def settings(migrated_db, tmp_path):
    return Settings(
        _env_file=None, app_local_token=TOKEN, database_url=migrated_db, ollama_enabled=False,
        data_dir=tmp_path / "data", max_upload_mb=1, worker_enabled=False,
    )


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {TOKEN}"}
