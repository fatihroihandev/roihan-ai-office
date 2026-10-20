import asyncio

import httpx
import pytest

from app.providers.base import GenerateRequest, ProviderError, ProviderErrorKind as K
from app.providers.ollama import OllamaProvider


def provider(handler, timeout=5):
    return OllamaProvider("http://ollama.test", timeout, transport=httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


def test_health_up_and_down():
    up = provider(lambda r: httpx.Response(200, json={"version": "0.40.6"}))
    h = run(up.health_check())
    assert h.status == "up" and h.version == "0.40.6" and h.latency_ms is not None

    def refuse(request):
        raise httpx.ConnectError("refused")
    h = run(provider(refuse).health_check())
    assert h.status == "down" and h.error_kind == "unavailable"


def test_list_models_reads_capabilities_without_assuming():
    def handler(request):
        return httpx.Response(200, json={"models": [
            {"name": "a:7b", "details": {"context_length": 32768, "family": "qwen2"}, "capabilities": ["completion", "tools"]},
            {"name": "b:1b", "details": {}},  # tanpa daftar capabilities: tidak boleh diasumsikan
        ]})
    a, b = run(provider(handler).list_models())
    assert (a.model_id, a.context_limit, a.supports_tools, a.supports_vision) == ("a:7b", 32768, True, False)
    assert (b.context_limit, b.supports_tools, b.supports_vision) == (None, None, None)


def test_get_capabilities_uses_model_info_context():
    def handler(request):
        assert request.url.path == "/api/show"
        return httpx.Response(200, json={"capabilities": ["completion", "vision"],
                                         "model_info": {"qwen2.context_length": 4096}})
    info = run(provider(handler).get_capabilities("m"))
    assert info.context_limit == 4096 and info.supports_vision is True and info.supports_tools is False


def test_generate_maps_usage_and_options():
    seen = {}

    def handler(request):
        import json
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"response": "halo", "done_reason": "stop",
                                         "prompt_eval_count": 11, "eval_count": 22})
    res = run(provider(handler).generate("m:1", GenerateRequest("hai", system="sys", max_tokens=64, temperature=0.1, num_ctx=2048)))
    assert res.text == "halo" and not res.truncated
    assert (res.usage.prompt_tokens, res.usage.completion_tokens) == (11, 22)
    assert seen["stream"] is False and seen["system"] == "sys"
    assert seen["options"] == {"temperature": 0.1, "num_predict": 64, "num_ctx": 2048}


def test_generate_flags_truncation():
    p = provider(lambda r: httpx.Response(200, json={"response": "x", "done_reason": "length"}))
    assert run(p.generate("m", GenerateRequest("hai"))).truncated is True


@pytest.mark.parametrize("make,kind,retryable", [
    (lambda r: httpx.Response(404, json={"error": "model 'x' not found"}), K.model_not_found, False),
    (lambda r: httpx.Response(400, json={"error": "bad"}), K.invalid_request, False),
    (lambda r: httpx.Response(500, json={"error": "boom"}), K.upstream_error, True),
])
def test_generate_http_errors_are_normalised(make, kind, retryable):
    with pytest.raises(ProviderError) as e:
        run(provider(make).generate("m", GenerateRequest("hai")))
    assert e.value.kind == kind and e.value.retryable is retryable


def test_generate_connection_and_timeout_errors():
    def refuse(request):
        raise httpx.ConnectError("refused")

    def slow(request):
        raise httpx.ReadTimeout("lambat")
    with pytest.raises(ProviderError) as e1:
        run(provider(refuse).generate("m", GenerateRequest("hai")))
    with pytest.raises(ProviderError) as e2:
        run(provider(slow).generate("m", GenerateRequest("hai")))
    assert (e1.value.kind, e1.value.retryable) == (K.unavailable, True)
    assert (e2.value.kind, e2.value.retryable) == (K.timeout, True)


def test_cancel_inflight_request():
    async def handler(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json={"response": "terlambat"})

    async def scenario():
        p = provider(handler)
        req = GenerateRequest("hai", request_id="req-cancel-1")
        task = asyncio.create_task(p.generate("m", req))
        await asyncio.sleep(0.1)
        assert await p.cancel("req-cancel-1") is True
        with pytest.raises(ProviderError) as e:
            await task
        assert e.value.kind == K.cancelled and e.value.retryable is False
        assert await p.cancel("req-cancel-1") is False  # sudah selesai

    run(scenario())
