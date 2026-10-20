def test_health_public_is_minimal(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "0.1.0"}
    assert r.headers["x-request-id"]


def test_request_id_is_echoed(client):
    r = client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_details_require_token(client):
    assert client.get("/api/health/details").status_code == 401
    assert client.get("/api/health/details", headers={"Authorization": "Bearer salah"}).status_code == 401


def test_details_with_token(client, auth):
    r = client.get("/api/health/details", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["components"] == {"database": "up", "ollama": "disabled"}
    assert body["paid_calls_allowed"] is False


def test_cors_only_allows_frontend_origin(client):
    ok = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    bad = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers
