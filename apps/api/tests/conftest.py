import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

API_DIR = Path(__file__).resolve().parents[1]
TOKEN = "token-uji-1234567890"


@pytest.fixture
def migrated_db(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"url={url}", "upgrade", "head"],
        cwd=API_DIR, check=True, capture_output=True,
    )
    return url


@pytest.fixture
def settings(migrated_db):
    return Settings(_env_file=None, app_local_token=TOKEN, database_url=migrated_db, ollama_enabled=False)


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {TOKEN}"}
