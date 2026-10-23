"""Adapter provider cloud: daftar model (Gemini/OpenAI/Anthropic), pesan galat yang jelas, cache, dan pengaturan lewat API."""
import asyncio
import json

import httpx
import pytest

from app.providers.base import ProviderError, ProviderErrorKind as K
from app.providers.capabilities import sync_provider_models
from app.providers.cloud import AnthropicProvider, GeminiProvider, OpenAIProvider
from app.providers.registry import ProviderEntry
from tests.helpers import build_env


def gemini(handler, key="AIza-rahasia-123"):
    return GeminiProvider(key, transport=httpx.MockTransport(handler))


def pages(request: httpx.Request):
    token = request.url.params.get("pageToken")
    if token is None:
        return httpx.Response(200, json={"models": [
            {"name": "models/gemini-2.5-flash", "displayName": "Flash", "inputTokenLimit": 1048576, "outputTokenLimit": 65536, "supportedGenerationMethods": ["generateContent", "countTokens"]},
            {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
        ], "nextPageToken": "p2"})
    return httpx.Response(200, json={"models": [
        {"name": "models/gemini-2.5-pro", "inputTokenLimit": 2000000, "supportedGenerationMethods": ["generateContent"]}]})


def test_gemini_lists_only_generative_models_across_pages_and_sends_key_in_header():
    seen = []

    def handler(r):
        seen.append(r)
        return pages(r)

    models = asyncio.run(gemini(handler).list_models())
    assert [m.model_id for m in models] == ["gemini-2.5-flash", "gemini-2.5-pro"]
    assert models[0].context_limit == 1048576 and models[0].details["display_name"] == "Flash"
    assert all(r.headers["x-goog-api-key"] == "AIza-rahasia-123" and "key=" not in str(r.url) for r in seen)   # kunci tidak di URL


def test_missing_key_is_reported_not_called():
    with pytest.raises(ProviderError) as e:
        asyncio.run(gemini(lambda r: pytest.fail("tidak boleh memanggil jaringan"), key="").list_models())
    assert e.value.kind == K.unavailable


@pytest.mark.parametrize("status,kind,fragment", [(400, K.invalid_request, "API key not valid"), (403, K.invalid_request, "ditolak"), (401, K.invalid_request, "ditolak"),
                                                  (429, K.upstream_error, "Kuota"), (500, K.upstream_error, "500")])
def test_errors_include_provider_reason_and_never_the_key(status, kind, fragment):
    key = "AIza-rahasia-123"
    body = {"error": {"message": f"API key not valid. Please pass a valid API key. ({key})"}}
    p = gemini(lambda r: httpx.Response(status, json=body), key=key)
    with pytest.raises(ProviderError) as e:
        asyncio.run(p.list_models())
    assert e.value.kind == kind and fragment in e.value.message and key not in e.value.message


def test_health_and_capabilities_reuse_one_listing_call():
    calls = []

    def handler(r):
        calls.append(r)
        return httpx.Response(200, json={"models": [{"name": "models/gemini-x", "supportedGenerationMethods": ["generateContent"]}]})

    async def go():
        p = gemini(handler)
        assert (await p.list_models())[0].model_id == "gemini-x"
        for _ in range(5):
            assert (await p.health_check()).status == "up"
            assert (await p.get_capabilities("gemini-x")).model_id == "gemini-x"
    asyncio.run(go())
    assert len(calls) == 1                                  # dulu: satu panggilan per pemeriksaan kesehatan dan per model
    with pytest.raises(ProviderError):
        asyncio.run(gemini(handler).get_capabilities("tidak-ada"))


def test_sync_makes_a_single_listing_call_for_cloud_providers(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    calls = []

    def handler(r):
        calls.append(r)
        return pages(r)

    entry = ProviderEntry("gemini", "cloud", True, True, True, gemini(handler))
    rows = asyncio.run(sync_provider_models(env.sf, entry, tmp_path))
    assert [r.model_id for r in rows] == ["gemini-2.5-flash", "gemini-2.5-pro"] and all(r.is_paid for r in rows)
    assert len(calls) == 2                                  # 2 halaman, bukan 1 + 2 x jumlah model


def test_openai_and_anthropic_listings():
    oa = OpenAIProvider("sk-x", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [{"id": "gpt-x", "owned_by": "o"}]})))
    assert [m.model_id for m in asyncio.run(oa.list_models())] == ["gpt-x"]

    def an(r):
        first = r.url.params.get("after_id") is None
        return httpx.Response(200, json={"data": [{"id": "a1" if first else "a2", "max_input_tokens": 200000}], "has_more": first, "last_id": "a1"})
    models = asyncio.run(AnthropicProvider("k", transport=httpx.MockTransport(an)).list_models())
    assert [m.model_id for m in models] == ["a1", "a2"] and models[0].context_limit == 200000


def test_gemini_generate_parses_text_and_usage():
    def handler(r):
        assert r.url.path.endswith("/models/gemini-x:generateContent")
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "halo"}]}, "finishReason": "STOP"}],
                                         "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2}})
    from app.providers.base import GenerateRequest
    res = asyncio.run(gemini(handler).generate("gemini-x", GenerateRequest(prompt="hai")))
    assert res.text == "halo" and res.usage.prompt_tokens == 3 and res.usage.completion_tokens == 2 and res.truncated is False


# ------------------------------------------------------------------ pengaturan lewat API

def test_cloud_settings_flow_never_returns_key_and_requires_key_to_enable(client, auth, settings, monkeypatch):
    async def fake_get_json(self, path, params=None):
        return {"models": [{"name": "models/gemini-x", "supportedGenerationMethods": ["generateContent"]}]}
    monkeypatch.setattr(GeminiProvider, "_get_json", fake_get_json)

    assert client.patch("/api/providers/gemini", json={"enabled": True}, headers=auth).status_code == 422          # tanpa key
    r = client.patch("/api/providers/gemini", json={"enabled": True, "api_key": "AIza-rahasia-123"}, headers=auth)
    assert r.status_code == 200 and r.json()["api_key_configured"] is True and r.json()["health"]["status"] == "up"
    assert "AIza-rahasia-123" not in r.text and "AIza-rahasia-123" not in client.get("/api/providers", headers=auth).text
    rows = client.post("/api/models/sync?provider=gemini", headers=auth).json()
    assert [m["model_id"] for m in rows] == ["gemini-x"] and rows[0]["is_paid"] is True
    saved = json.loads((settings.data_dir / "ai-provider-settings.json").read_text(encoding="utf-8"))
    assert saved["gemini"]["enabled"] is True
    assert client.patch("/api/providers/gemini", json={"clear_api_key": True}, headers=auth).status_code == 422   # nonaktifkan dulu
    off = client.patch("/api/providers/gemini", json={"enabled": False, "clear_api_key": True}, headers=auth)
    assert off.status_code == 200 and off.json()["api_key_configured"] is False and off.json()["enabled"] is False
    assert client.patch("/api/providers/gemini", json={"base_url": "http://x.example"}, headers=auth).status_code == 422
    assert client.patch("/api/providers/ollama", json={"api_key": "x"}, headers=auth).status_code == 422


def test_paid_calls_stay_blocked_even_with_key_and_enabled(client, auth, monkeypatch):
    async def fake_get_json(self, path, params=None):
        return {"models": []}
    monkeypatch.setattr(GeminiProvider, "_get_json", fake_get_json)
    client.patch("/api/providers/gemini", json={"enabled": True, "api_key": "AIza-x"}, headers=auth)
    r = client.post("/api/ai/generate", json={"provider": "gemini", "model": "gemini-x", "prompt": "uji"}, headers=auth)
    assert r.status_code == 403 and r.json()["kind"] == "blocked"                       # budget_allow_paid_calls tetap false
