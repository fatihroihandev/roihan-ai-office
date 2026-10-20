import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.providers.base import ProviderError, ProviderErrorKind as K
from tests.fakes import FakeProvider


@pytest.fixture
def fake():
    return FakeProvider()


@pytest.fixture
def settings(settings):
    return settings.model_copy(update={"ollama_enabled": True})


@pytest.fixture
def client(settings, fake):
    return TestClient(create_app(settings, providers={"ollama": fake}))


def test_endpoints_require_token(client):
    for method, path in [("get", "/api/providers"), ("get", "/api/models"), ("post", "/api/models/sync"),
                         ("post", "/api/ai/generate"), ("get", "/api/usage"), ("get", "/api/budgets")]:
        assert getattr(client, method)(path).status_code == 401, path


def test_providers_list_shows_cloud_as_disabled_and_not_implemented(client, auth):
    by = {p["name"]: p for p in client.get("/api/providers", headers=auth).json()}
    assert by["ollama"]["health"]["status"] == "up" and by["ollama"]["is_paid"] is False
    for n in ("openai", "gemini", "anthropic"):
        assert (by[n]["enabled"], by[n]["implemented"], by[n]["is_paid"], by[n]["health"]) == (False, False, True, None)


def test_sync_populates_registry_with_unknowns_left_null(client, auth):
    rows = client.post("/api/models/sync", headers=auth).json()
    [m] = rows
    assert (m["provider"], m["model_id"], m["context_limit"], m["supports_tools"]) == ("ollama", "fake-model:1b", 8192, True)
    assert m["supports_structured"] is None and m["supports_streaming"] is None and m["max_output"] is None
    assert m["validation_status"] == "unvalidated"
    assert client.get("/api/models?provider=ollama", headers=auth).json()[0]["model_id"] == "fake-model:1b"
    assert client.get("/api/models?provider=openai", headers=auth).json() == []


def test_sync_attaches_latest_benchmark_and_marks_removed_models(client, auth, settings, fake):
    bench = settings.data_dir / "benchmarks"
    bench.mkdir(parents=True)
    report = {"json": {"rate": 1.0}, "codegen": {"rate": 0.9}, "bugfix": {"rate": 1.0},
              "speed": {"avg_tok_per_s": 6.6}, "finished_at": "2026-10-20T03:00:00Z"}
    (bench / "fake-model_1b_20261020_100000.json").write_text(json.dumps(report), encoding="utf-8")
    m = client.post("/api/models/sync", headers=auth).json()[0]
    assert m["validation_status"] == "benchmarked"
    assert m["benchmark"]["codegen_pass_rate"] == 0.9 and m["benchmark"]["avg_tok_per_s"] == 6.6

    fake.models = []
    m = client.post("/api/models/sync", headers=auth).json()[0]
    assert m["available"] is False


def test_sync_for_cloud_provider_is_refused(client, auth):
    assert client.post("/api/models/sync?provider=openai", headers=auth).status_code == 409
    assert client.post("/api/models/sync?provider=tidak-ada", headers=auth).status_code == 404


def test_generate_success_and_usage_log(client, auth, fake):
    r = client.post("/api/ai/generate", json={"prompt": "hai", "request_id": "abcd-1234"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "jawaban:hai" and body["provider"] == "ollama" and body["request_id"] == "abcd-1234"
    assert body["model"] == "qwen2.5-coder:7b"  # model default dari konfigurasi
    assert body["usage"] == {"prompt_tokens": 5, "completion_tokens": 7, "duration_ms": 12}

    u = client.get("/api/usage", headers=auth).json()
    assert u["summary"]["total"] == 1 and u["summary"]["ok"] == 1 and u["summary"]["total_cost_idr"] == 0
    assert u["summary"]["prompt_tokens"] == 5 and u["summary"]["completion_tokens"] == 7
    assert "prompt" not in u["items"][0] and u["items"][0]["status"] == "ok"


def test_generate_validation_and_limits(client, auth):
    post = lambda **kw: client.post("/api/ai/generate", json=kw, headers=auth)
    assert post(prompt="").status_code == 422
    assert post(prompt="   ").status_code == 422
    assert post(prompt="x", temperature=2).status_code == 422
    assert post(prompt="x", num_ctx=99999).status_code == 422
    assert post(prompt="x", request_id="../bad").status_code == 422
    assert post(prompt="x", max_tokens=5000).status_code == 422
    assert post(prompt="x" * 20001).status_code == 413


@pytest.mark.parametrize("kind,status,retryable", [
    (K.unavailable, 503, True), (K.timeout, 504, True), (K.model_not_found, 404, False),
    (K.invalid_request, 400, False), (K.upstream_error, 502, True), (K.cancelled, 409, False),
])
def test_generate_error_mapping(settings, auth, kind, status, retryable):
    c = TestClient(create_app(settings, providers={"ollama": FakeProvider(error=ProviderError(kind, "pesan"))}))
    r = c.post("/api/ai/generate", json={"prompt": "hai"}, headers=auth)
    assert r.status_code == status
    assert r.json() == {"detail": "pesan", "kind": kind.value, "retryable": retryable}


def test_paid_provider_request_is_forbidden_and_logged(settings, auth):
    settings = settings.model_copy(update={"openai_enabled": True, "openai_api_key": "k" * 10})
    client = TestClient(create_app(settings, providers={"ollama": FakeProvider(), "openai": FakeProvider("openai", is_paid=True)}))
    r = client.post("/api/ai/generate", json={"provider": "openai", "model": "gpt-x", "prompt": "hai"}, headers=auth)
    assert r.status_code == 403
    assert r.json()["kind"] == "blocked" and r.json()["reason"] == "paid_calls_disabled"
    u = client.get("/api/usage", headers=auth).json()
    assert u["summary"]["blocked"] == 1 and u["items"][0]["is_paid"] is True and u["items"][0]["cost_idr"] == 0


def test_cancel_unknown_request(client, auth):
    assert client.post("/api/ai/requests/tidak-ada/cancel", headers=auth).json() == {"cancelled": False}


def test_budgets_reflect_policy(client, auth):
    b = client.get("/api/budgets", headers=auth).json()
    assert b["allow_paid_calls"] is False and b["monthly_limit"] == 0 and b["currency"] == "IDR"
    assert b["require_approval_for_paid_calls"] is True and b["spent_total"] == 0
