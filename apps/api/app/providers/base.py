"""Kontrak provider internal (Bagian 8.3). Semua provider mengikuti antarmuka yang sama."""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class ProviderErrorKind(str, Enum):
    unavailable = "unavailable"          # provider tidak dapat dihubungi
    timeout = "timeout"
    model_not_found = "model_not_found"
    invalid_request = "invalid_request"
    upstream_error = "upstream_error"    # provider membalas error 5xx
    cancelled = "cancelled"


_RETRYABLE = {ProviderErrorKind.unavailable, ProviderErrorKind.timeout, ProviderErrorKind.upstream_error}


class ProviderError(Exception):
    """Error yang sudah dinormalisasi. `retryable` menjadi masukan untuk retry policy (Bagian 12.3)."""

    def __init__(self, kind: ProviderErrorKind, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.kind in _RETRYABLE


class GatewayBlocked(Exception):
    """Pemanggilan ditolak oleh kebijakan (provider nonaktif, berbayar, atau belum diimplementasikan)."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class GenerateRequest:
    prompt: str
    system: str | None = None
    max_tokens: int = 512
    temperature: float = 0.2
    num_ctx: int = 4096
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    json_schema: dict | None = None  # structured output: keluaran dibatasi skema (jika provider mendukung)


@dataclass
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    duration_ms: int | None = None


@dataclass
class GenerateResult:
    text: str
    model: str
    usage: Usage
    truncated: bool = False  # True jika berhenti karena batas token, bukan selesai alami


@dataclass
class ModelInfo:
    model_id: str
    context_limit: int | None = None
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    details: dict = field(default_factory=dict)


@dataclass
class HealthResult:
    status: str  # "up" | "down"
    latency_ms: int | None = None
    version: str | None = None
    error_kind: str | None = None


class ModelProvider(ABC):
    name: str
    is_paid: bool = False
    is_local: bool = True

    @abstractmethod
    async def health_check(self) -> HealthResult: ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def get_capabilities(self, model: str) -> ModelInfo: ...

    @abstractmethod
    async def generate(self, model: str, request: GenerateRequest) -> GenerateResult: ...

    @abstractmethod
    async def cancel(self, request_id: str) -> bool: ...
