from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
