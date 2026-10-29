"""Adapter REST untuk provider AI cloud."""
import asyncio
import time
from abc import ABC
from typing import Any

import httpx

from app.providers.base import (
    GenerateRequest,
    GenerateResult,
    HealthResult,
    ModelInfo,
    ModelProvider,
    ProviderError,
    ProviderErrorKind as K,
    Usage,
)


class CloudProvider(ModelProvider, ABC):
    is_paid = True
    is_local = False
    api_base = ""
    api_version: str | None = None
    bulk_listing = True      # daftar model sudah memuat kemampuan; tidak perlu satu panggilan per model
    CACHE_TTL_S = 60.0       # health dan kemampuan memakai daftar model yang baru diambil (hemat kuota dan waktu)

    def __init__(self, api_key: str, timeout_s: float = 120, base_url: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        self._api_key = api_key.strip()
        self._base = (base_url or self.api_base).rstrip("/")
        self._timeout = timeout_s
        self._transport = transport
        self._inflight: dict[str, asyncio.Task] = {}
        self._cancel_requested: set[str] = set()
        self._cache: tuple[float, list[ModelInfo]] | None = None

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=timeout or self._timeout,
                                 headers=self._headers(), transport=self._transport)

    def _detail(self, response: httpx.Response) -> str:
        """Pesan galat dari provider (mis. 'API key not valid'); kunci tidak pernah ikut ditampilkan."""
        try:
            body = response.json()
            err = body.get("error") if isinstance(body, dict) else None
            msg = (err.get("message") if isinstance(err, dict) else err) or ""
        except ValueError:
            msg = ""
        msg = str(msg).replace(self._api_key, "[REDACTED]") if self._api_key else str(msg)
        return " ".join(msg.split())[:200]

    def _map_error(self, error: Exception) -> ProviderError:
        if isinstance(error, (httpx.ConnectError, httpx.ConnectTimeout)):
            return ProviderError(K.unavailable, "Provider AI tidak dapat dihubungi")
        if isinstance(error, httpx.TimeoutException):
            return ProviderError(K.timeout, "Provider AI tidak merespons dalam batas waktu")
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            detail = self._detail(error.response)
            suffix = f": {detail}" if detail else ""
            if status == 404:
                return ProviderError(K.model_not_found, f"Model atau endpoint tidak ditemukan oleh provider{suffix}")
            if status in (401, 403):
                return ProviderError(K.invalid_request, f"API key ditolak atau tidak punya akses (status {status}){suffix}")
            if status == 429:
                return ProviderError(K.upstream_error, f"Kuota atau batas laju provider terlampaui (status 429); coba lagi nanti{suffix}")
            if status in (400, 422):
                return ProviderError(K.invalid_request, f"Permintaan ditolak provider (status {status}){suffix}")
            return ProviderError(K.upstream_error, f"Provider AI mengembalikan status {status}{suffix}")
        return ProviderError(K.upstream_error, f"Kesalahan saat memanggil provider AI: {type(error).__name__}")

    async def _get_json(self, path: str, params: dict | None = None) -> dict:
        try:
            async with self._client(15) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as error:
            raise self._map_error(error) from error

    async def health_check(self) -> HealthResult:
        start = time.perf_counter()
        if not self._api_key:
            return HealthResult("down", error_kind=K.unavailable.value)
        try:
            await self._cached_models()
            return HealthResult("up", int((time.perf_counter() - start) * 1000), self.api_version)
        except ProviderError as error:
            return HealthResult("down", error_kind=error.kind.value)

    async def list_models(self) -> list[ModelInfo]:
        if not self._api_key:
            raise ProviderError(K.unavailable, "API key provider belum dikonfigurasi")
        models = await self._list_models()
        self._cache = (time.monotonic(), models)
        return models

    async def _cached_models(self) -> list[ModelInfo]:
        if self._cache and time.monotonic() - self._cache[0] < self.CACHE_TTL_S:
            return self._cache[1]
        return await self.list_models()

    async def get_capabilities(self, model: str) -> ModelInfo:
        for item in await self._cached_models():
            if item.model_id == model:
                return item
        raise ProviderError(K.model_not_found, "Model tidak ditemukan oleh provider")

    async def generate(self, model: str, request: GenerateRequest) -> GenerateResult:
        if not self._api_key:
            raise ProviderError(K.unavailable, "API key provider belum dikonfigurasi")
        task = asyncio.create_task(self._do_generate(model, request))
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
        task.cancel()
        return True

    async def _do_generate(self, model: str, request: GenerateRequest) -> GenerateResult:
        raise NotImplementedError

    async def _list_models(self) -> list[ModelInfo]:
        raise NotImplementedError


class OpenAIProvider(CloudProvider):
    name = "openai"
    api_base = "https://api.openai.com/v1"
    api_version = "v1"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _list_models(self) -> list[ModelInfo]:
        data = await self._get_json("/models")
        return [ModelInfo(item["id"], details={"owned_by": item.get("owned_by")})
                for item in data.get("data", []) if item.get("id")]

    async def _do_generate(self, model: str, request: GenerateRequest) -> GenerateResult:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})
        body: dict[str, Any] = {"model": model, "messages": messages,
                                "max_completion_tokens": request.max_tokens,
                                "temperature": request.temperature}
        if request.json_schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "response", "strict": True, "schema": request.json_schema}}
        start = time.perf_counter()
        try:
            async with self._client() as client:
                response = await client.post("/chat/completions", json=body)
                response.raise_for_status()
        except Exception as error:
            raise self._map_error(error) from error
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        usage = data.get("usage") or {}
        return GenerateResult(str(content or ""), model,
                              Usage(usage.get("prompt_tokens"), usage.get("completion_tokens"),
                                    int((time.perf_counter() - start) * 1000)),
                              truncated=choice.get("finish_reason") == "length")


class GeminiProvider(CloudProvider):
    name = "gemini"
    api_base = "https://generativelanguage.googleapis.com/v1beta"
    api_version = "v1beta"

    def __init__(self, api_key: str, timeout_s: float = 120, base_url: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None, is_paid: bool = False):
        super().__init__(api_key, timeout_s, base_url, transport)
        self.is_paid = is_paid

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key}

    async def _list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        token = None
        while True:
            params = {"pageSize": 100}
            if token:
                params["pageToken"] = token
            data = await self._get_json("/models", params)
            for item in data.get("models", []):
                methods = item.get("supportedGenerationMethods") or []
                if "generateContent" not in methods:
                    continue
                model_id = item.get("name", "").removeprefix("models/")
                if model_id:
                    models.append(ModelInfo(model_id, item.get("inputTokenLimit"),
                        details={"display_name": item.get("displayName"),
                                 "output_token_limit": item.get("outputTokenLimit")}))
            token = data.get("nextPageToken")
            if not token:
                return models

    async def _do_generate(self, model: str, request: GenerateRequest) -> GenerateResult:
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": {"temperature": request.temperature, "maxOutputTokens": request.max_tokens},
        }
        if request.system:
            body["systemInstruction"] = {"parts": [{"text": request.system}]}
        if request.json_schema:
            body["generationConfig"].update({"responseMimeType": "application/json",
                                              "responseSchema": request.json_schema})
        start = time.perf_counter()
        try:
            async with self._client() as client:
                response = await client.post(f"/models/{model}:generateContent", json=body)
                if response.status_code == 400 and "Developer instruction is not enabled" in response.text:
                    body.pop("systemInstruction", None)
                    body["contents"] = [{"role": "user", "parts": [{"text": f"{request.system}\n\n{request.prompt}"}]}]
                    response = await client.post(f"/models/{model}:generateContent", json=body)
                response.raise_for_status()
        except Exception as error:
            raise self._map_error(error) from error
        data = response.json()
        candidates = data.get("candidates") or [{}]
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        usage = data.get("usageMetadata") or {}
        return GenerateResult(text, model,
            Usage(usage.get("promptTokenCount"), usage.get("candidatesTokenCount"),
                  int((time.perf_counter() - start) * 1000)),
            truncated=candidates[0].get("finishReason") == "MAX_TOKENS")


class AnthropicProvider(CloudProvider):
    name = "anthropic"
    api_base = "https://api.anthropic.com/v1"
    api_version = "2023-06-01"

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key, "anthropic-version": self.api_version or "2023-06-01"}

    async def _list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        before_id = None
        while True:
            params = {"limit": 100}
            if before_id:
                params["after_id"] = before_id
            data = await self._get_json("/models", params)
            for item in data.get("data", []):
                if item.get("id"):
                    capabilities = item.get("capabilities") or {}
                    image_input = capabilities.get("image_input") or {}
                    input_tokens = item.get("max_input_tokens")
                    models.append(ModelInfo(item["id"],
                        context_limit=input_tokens if isinstance(input_tokens, int) and input_tokens > 0 else None,
                        supports_vision=image_input.get("supported") if isinstance(image_input, dict) else None,
                        details={"display_name": item.get("display_name"),
                                 "max_output_tokens": item.get("max_tokens"),
                                 "lifecycle": item.get("lifecycle")}))
            if not data.get("has_more"):
                return models
            before_id = data.get("last_id")
            if not before_id:
                return models

    async def _do_generate(self, model: str, request: GenerateRequest) -> GenerateResult:
        system = request.system or ""
        body = {"model": model, "max_tokens": request.max_tokens,
                "temperature": request.temperature, "messages": [{"role": "user", "content": request.prompt}]}
        if system:
            body["system"] = system
        if request.json_schema:
            body["output_config"] = {"format": {"type": "json_schema", "schema": request.json_schema}}
        start = time.perf_counter()
        try:
            async with self._client() as client:
                response = await client.post("/messages", json=body)
                response.raise_for_status()
        except Exception as error:
            raise self._map_error(error) from error
        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        usage = data.get("usage") or {}
        return GenerateResult(text, model,
            Usage(usage.get("input_tokens"), usage.get("output_tokens"),
                  int((time.perf_counter() - start) * 1000)),
            truncated=data.get("stop_reason") == "max_tokens")
