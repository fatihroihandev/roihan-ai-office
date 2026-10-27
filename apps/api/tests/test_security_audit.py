"""Audit keamanan Fase 11: setiap rute API wajib terautentikasi kecuali daftar putih yang kecil dan disengaja."""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PUBLIC = {
    ("GET", "/api/health"),
    ("GET", "/api/auth/status"),
    ("POST", "/api/auth/bootstrap"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
}  # liveness minimal tanpa data; WebSocket memakai tiket sekali pakai yang diterbitkan lewat rute bertoken


def _routes(app):
    """Semua operasi HTTP /api dari skema OpenAPI (router FastAPI terbaru dimuat malas, jadi app.routes tidak cukup)."""
    ops = []
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if path.startswith("/api") and method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                ops.append((method.upper(), path))
    return ops


def test_every_api_route_rejects_requests_without_token(settings):
    app = create_app(settings)
    c = TestClient(app, raise_server_exceptions=False)
    checked = 0
    for method, route in _routes(app):
        if (method, route) in PUBLIC:
            continue
        path = re.sub(r"\{[^}]+\}", "x", route)
        resp = c.request(method, path)                     # tanpa header Authorization
        assert resp.status_code == 401, f"{method} {route} -> {resp.status_code} (rute tanpa autentikasi)"
        bad = c.request(method, path, headers={"Authorization": "Bearer salah"})
        assert bad.status_code == 401, f"{method} {route} menerima token salah"
        checked += 1
    assert checked > 80   # pastikan audit benar-benar menyisir banyak rute


def test_public_routes_expose_no_data(client):
    body = client.get("/api/health").json()
    assert set(body) <= {"status", "version"}


def test_websocket_requires_valid_single_use_ticket(client, auth):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws?ticket=palsu", headers={"origin": "http://localhost:3000"}):
            pass
    t = client.post("/api/events/ticket", headers=auth).json()["ticket"]
    with client.websocket_connect(f"/api/ws?ticket={t}", headers={"origin": "http://localhost:3000"}):
        pass
    with pytest.raises(WebSocketDisconnect):             # tiket sekali pakai
        with client.websocket_connect(f"/api/ws?ticket={t}", headers={"origin": "http://localhost:3000"}):
            pass


def test_websocket_rejects_foreign_origin(client, auth):
    from starlette.websockets import WebSocketDisconnect
    t = client.post("/api/events/ticket", headers=auth).json()["ticket"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/ws?ticket={t}", headers={"origin": "http://evil.example"}):
            pass


def test_cors_does_not_allow_foreign_origin(client):
    r = client.options("/api/projects", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_secure_defaults(settings):
    from app.config import Settings
    s = Settings(_env_file=None, app_local_token="token-uji-1234567890")
    assert not (s.openai_enabled or s.gemini_enabled or s.anthropic_enabled or s.budget_allow_paid_calls)
    assert s.require_approval_for_external_actions and s.restrict_workspace_access and s.redact_secrets_in_logs
    assert all("localhost" in o or "127.0.0.1" in o for o in s.cors_origins)
