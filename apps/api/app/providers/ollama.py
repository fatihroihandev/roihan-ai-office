import asyncio
import time

import httpx

from app.providers.base import (
    GenerateRequest, GenerateResult, HealthResult, ModelInfo, ModelProvider, ProviderError,
    ProviderErrorKind as K, Usage,
)


def _info_from(model_id: str, show_or_tag: dict) -> ModelInfo:
    caps = show_or_tag.get("capabilities")
    model_info = show_or_tag.get("model_info") or {}
    details = show_or_tag.get("details") or {}
    ctx = next((v for k, v in model_info.items() if k.endswith(".context_length")), details.get("context_length"))
    return ModelInfo(
        model_id=model_id,
        context_limit=ctx if isinstance(ctx, int) else None,
        # None = tidak diketahui; hanya True/False jika Ollama melaporkan daftar capabilities
        supports_tools=("tools" in caps) if isinstance(caps, list) else None,
        supports_vision=("vision" in caps) if isinstance(caps, list) else None,
        details={k: details.get(k) for k in ("family", "parameter_size", "quantization_level", "format") if details.get(k)},
    )


class OllamaProvider(ModelProvider):
    name = "ollama"
    is_paid = False
    is_local = True

    def __init__(self, base_url: str, timeout_s: float = 300, transport: httpx.AsyncBaseTransport | None = None):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._transport = transport
        self._inflight: dict[str, asyncio.Task] = {}
        self._cancel_requested: set[str] = set()

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=timeout, transport=self._transport)

    @staticmethod
    def _map_http_error(e: Exception) -> ProviderError:
        if isinstance(e, httpx.ConnectError | httpx.ConnectTimeout):
            return ProviderError(K.unavailable, "Ollama tidak dapat dihubungi. Pastikan Ollama berjalan.")
        if isinstance(e, httpx.TimeoutException):
            return ProviderError(K.timeout, "Ollama tidak merespons dalam batas waktu")
        if isinstance(e, httpx.HTTPStatusError):
            code = e.response.status_code
            try:
                msg = e.response.json().get("error") or e.response.text
            except Exception:
                msg = e.response.text
            if code == 404:
                return ProviderError(K.model_not_found, msg or "Model tidak ditemukan")
            if 400 <= code < 500:
                return ProviderError(K.invalid_request, msg or "Permintaan tidak valid")
            return ProviderError(K.upstream_error, msg or f"Ollama mengembalikan status {code}")
        return ProviderError(K.upstream_error, f"Kesalahan tak terduga saat memanggil Ollama: {type(e).__name__}")

    async def health_check(self) -> HealthResult:
        start = time.perf_counter()
        try:
            async with self._client(2.0) as c:
                r = await c.get("/api/version")
                r.raise_for_status()
            return HealthResult("up", int((time.perf_counter() - start) * 1000), r.json().get("version"))
        except Exception as e:
            return HealthResult("down", error_kind=self._map_http_error(e).kind.value)

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with self._client(10.0) as c:
                r = await c.get("/api/tags")
                r.raise_for_status()
        except Exception as e:
            raise self._map_http_error(e) from e
        return [_info_from(m["name"], m) for m in r.json().get("models", [])]

    async def get_capabilities(self, model: str) -> ModelInfo:
        try:
            async with self._client(10.0) as c:
                r = await c.post("/api/show", json={"model": model})
                r.raise_for_status()
        except Exception as e:
            raise self._map_http_error(e) from e
        return _info_from(model, r.json())

    async def _do_generate(self, model: str, req: GenerateRequest) -> GenerateResult:
        body = {
            "model": model, "prompt": req.prompt, "stream": False,
            "options": {"temperature": req.temperature, "num_predict": req.max_tokens, "num_ctx": req.num_ctx},
        }
        if req.system:
            body["system"] = req.system
        if req.json_schema:
            body["format"] = req.json_schema
        start = time.perf_counter()
        try:
            async with self._client(self._timeout) as c:
                r = await c.post("/api/generate", json=body)
                r.raise_for_status()
        except Exception as e:
            raise self._map_http_error(e) from e
        d = r.json()
        return GenerateResult(
            text=d.get("response", ""), model=model, truncated=d.get("done_reason") == "length",
            usage=Usage(d.get("prompt_eval_count"), d.get("eval_count"), int((time.perf_counter() - start) * 1000)),
        )

    async def generate(self, model: str, request: GenerateRequest) -> GenerateResult:
        task = asyncio.ensure_future(self._do_generate(model, request))
        self._inflight[request.request_id] = task
        try:
            return await task
        except asyncio.CancelledError:
            if request.request_id in self._cancel_requested:
                raise ProviderError(K.cancelled, "Permintaan dibatalkan") from None
            raise
        finally:
            self._inflight.pop(request.request_id, None)
            self._cancel_requested.discard(request.request_id)

    async def cancel(self, request_id: str) -> bool:
        task = self._inflight.get(request_id)
        if task is None or task.done():
            return False
        self._cancel_requested.add(request_id)
        task.cancel()  # menutup koneksi sehingga Ollama menghentikan generasi
        return True
