from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.providers.runtime_settings import valid_base_url


class ProviderSettingsUpdate(BaseModel):
    enabled: bool | None = None
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    api_key: str | None = Field(default=None, repr=False)
    clear_api_key: bool = False

    @field_validator("base_url")
    @classmethod
    def _valid_base_url(cls, value: str | None) -> str | None:
        if value is not None and not valid_base_url(value):
            raise ValueError("Alamat provider harus berupa URL HTTP/HTTPS tanpa kredensial, query, atau fragment")
        return value.strip().rstrip("/") if value is not None else None

    @field_validator("api_key")
    @classmethod
    def _trim_api_key(cls, value: str | None) -> str | None:
        value = value.strip() if value is not None else None
        return value or None


class ProviderHealthOut(BaseModel):
    status: str
    latency_ms: int | None = None
    version: str | None = None
    error_kind: str | None = None


class ProviderOut(BaseModel):
    name: str
    kind: str
    is_paid: bool
    enabled: bool
    implemented: bool
    base_url: str | None = None
    api_key_configured: bool | None = None
    health: ProviderHealthOut | None = None


class GenerateBody(BaseModel):
    provider: str = "ollama"
    model: str | None = None
    prompt: str = Field(min_length=1)
    system: str | None = Field(default=None, max_length=4000)
    max_tokens: int = Field(default=512, ge=1)
    temperature: float = Field(default=0.2, ge=0, le=1)
    num_ctx: int = Field(default=4096, ge=512, le=8192)
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{8,64}$")

    @field_validator("prompt")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Prompt tidak boleh kosong")
        return v


class UsageOut(BaseModel):
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int | None


class GenerateOut(BaseModel):
    request_id: str
    provider: str
    model: str
    text: str
    truncated: bool
    usage: UsageOut


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    model_id: str
    available: bool
    is_paid: bool
    context_limit: int | None
    max_output: int | None
    supports_tools: bool | None
    supports_structured: bool | None
    supports_vision: bool | None
    supports_streaming: bool | None
    cost_estimate_idr_per_1k: float | None
    validation_status: str
    benchmark: dict | None
    details: dict | None
    refreshed_at: datetime


class UsageRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    provider: str
    model: str
    purpose: str
    status: str
    error_kind: str | None
    prompt_chars: int
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: int | None
    is_paid: bool
    cost_idr: float
