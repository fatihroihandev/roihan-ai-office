"""Pengujian Single-Owner Authentication & Session Management (Addendum v2.1)."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TOKEN = "token-uji-1234567890"


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        app_local_token=TOKEN,
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path}/test_auth.db",
        worker_enabled=False,
        max_failed_logins=3,
        lockout_minutes=10,
    )
    # Ensure tables exist
    from app.db.base import Base
    from app.db.session import create_db_engine
    engine = create_db_engine(settings.database_url)
    Base.metadata.create_all(engine)

    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_auth_status_uninitialized(client):
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    data = r.json()
    assert data["initialized"] is False
    assert data["authenticated"] is False


def test_bootstrap_owner_success_and_locks_subsequent(client):
    # 1. Bootstrap pertama berhasil
    r = client.post(
        "/api/auth/bootstrap",
        json={
            "email": "owner@roihan.id",
            "password": "PasswordSuperRahasia123!",
            "full_name": "Roihan Fatih",
        },
    )
    assert r.status_code == 200
    res = r.json()
    assert res["status"] == "success"
    assert res["user"]["email"] == "owner@roihan.id"
    assert "token" not in res
    assert "roihan_session" in r.cookies
    token = r.cookies["roihan_session"]

    # 2. Status sekarang terinisialisasi
    r_stat = client.get("/api/auth/status")
    assert r_stat.json()["initialized"] is True

    # 3. Pendaftaran kedua DITOLAK permanen (Single-Owner restriction)
    r_second = client.post(
        "/api/auth/bootstrap",
        json={
            "email": "hacker@evil.com",
            "password": "PasswordHacker123!",
            "full_name": "Intruder",
        },
    )
    assert r_second.status_code == 403
    assert "telah diinisialisasi" in r_second.json()["detail"]


def test_login_and_logout_flow(client):
    # Bootstrap
    client.post(
        "/api/auth/bootstrap",
        json={"email": "owner@roihan.id", "password": "PasswordAman123!", "full_name": "Roihan"},
    )

    # Login salah
    r_fail = client.post(
        "/api/auth/login",
        json={"email": "owner@roihan.id", "password": "SalahPassword123!"},
    )
    assert r_fail.status_code == 401

    # Login sukses
    r_ok = client.post(
        "/api/auth/login",
        json={"email": "owner@roihan.id", "password": "PasswordAman123!"},
    )
    assert r_ok.status_code == 200
    assert "token" not in r_ok.json()
    assert "roihan_session" in r_ok.cookies
    token = r_ok.cookies["roihan_session"]

    # Akses endpoint protected /api/auth/me dengan Bearer token
    r_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    assert r_me.json()["email"] == "owner@roihan.id"

    # Logout
    r_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r_logout.status_code == 200

    # Setelah logout, token ditolak
    r_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_after.status_code == 401


def test_login_rate_limiting_lockout(client):
    client.post(
        "/api/auth/bootstrap",
        json={"email": "owner@roihan.id", "password": "PasswordKuat123!", "full_name": "Roihan"},
    )

    # 3x percobaan gagal (max_failed_logins = 3)
    for _ in range(3):
        client.post("/api/auth/login", json={"email": "owner@roihan.id", "password": "WrongPassword"})

    # Percobaan ke-4 harus terkunci (429 Too Many Requests / account_locked)
    r_locked = client.post("/api/auth/login", json={"email": "owner@roihan.id", "password": "PasswordKuat123!"})
    assert r_locked.status_code == 429
    assert "terkunci" in r_locked.json()["detail"].lower()


def test_require_token_accepts_session_token_and_local_token(client):
    # Bootstrap
    r_boot = client.post(
        "/api/auth/bootstrap",
        json={"email": "owner@roihan.id", "password": "PasswordKuat123!", "full_name": "Roihan"},
    )
    session_token = r_boot.cookies["roihan_session"]

    # 1. Akses API tasks dengan session_token pemilik
    r1 = client.get("/api/tasks", headers={"Authorization": f"Bearer {session_token}"})
    assert r1.status_code == 200

    # 2. Akses API tasks dengan APP_LOCAL_TOKEN (backward compatibility)
    r2 = client.get("/api/tasks", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r2.status_code == 200

    # 3. Akses API tasks tanpa token / token palsu -> DITOLAK 401
    r3 = client.get("/api/tasks", headers={"Authorization": "Bearer token-palsu-ngawur"})
    assert r3.status_code == 401


def test_session_token_is_hashed_in_database(client):
    r_boot = client.post(
        "/api/auth/bootstrap",
        json={"email": "owner@roihan.id", "password": "PasswordKuat123!", "full_name": "Roihan"},
    )
    raw_token = r_boot.cookies["roihan_session"]
    from app.db.models import OwnerSession
    from app.auth.service import hash_session_token
    from sqlalchemy import select
    app = client.app
    with app.state.session_factory() as s:
        sess = s.scalar(select(OwnerSession).limit(1))
        assert sess is not None
        # Database hanya menyimpan SHA-256 hash 64-karakter, bukan raw token
        assert sess.session_token != raw_token
        assert sess.session_token == hash_session_token(raw_token)
        assert len(sess.session_token) == 64
