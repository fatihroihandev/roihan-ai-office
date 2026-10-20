from typing import Literal

from pydantic import BaseModel, Field, field_validator

VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,39}$"


def _strip(v):
    return v.strip() if isinstance(v, str) else v


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    line: Literal["owned_product", "service"] = "owned_product"
    description: str | None = Field(default=None, max_length=4000)
    target_customers: str | None = Field(default=None, max_length=2000)
    pricing_model: str | None = Field(default=None, max_length=2000)
    project_id: str | None = None

    _s = field_validator("name", "description", "target_customers", "pricing_model", mode="before")(_strip)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v:
            raise ValueError("Nama produk tidak boleh kosong")
        return v


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    target_customers: str | None = Field(default=None, max_length=2000)
    pricing_model: str | None = Field(default=None, max_length=2000)

    _s = field_validator("name", "description", "target_customers", "pricing_model", mode="before")(_strip)


class VersionCreate(BaseModel):
    version: str = Field(pattern=VERSION_PATTERN)
    release_notes: str | None = Field(default=None, max_length=8000)
    pin_commit: bool = False


class VersionUpdate(BaseModel):
    release_notes: str | None = Field(default=None, max_length=8000)
    limitations: list[str] | None = Field(default=None, max_length=30)
    limitations_confirmed: bool | None = None
    materials_reviewed: bool | None = None
    status: Literal["draft", "in_development", "internal_testing", "beta", "released", "deprecated", "archived"] | None = None

    @field_validator("limitations")
    @classmethod
    def _lim(cls, v):
        if v is None:
            return v
        cleaned = [x.strip() for x in v if x and x.strip()]
        if any(len(x) > 500 for x in cleaned):
            raise ValueError("Setiap batasan maksimal 500 karakter")
        return cleaned


class FeatureCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    task_ids: list[str] = Field(default_factory=list, max_length=20)

    _s = field_validator("text", mode="before")(_strip)

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        if not v:
            raise ValueError("Teks fitur tidak boleh kosong")
        return v


class EvidenceBody(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=20)


class ReasonBody(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AttestBody(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class PermissionBody(BaseModel):
    permission: Literal["not_allowed", "beta_only", "allowed"]
    reason: str | None = Field(default=None, max_length=1000)


class ClaimCheckBody(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
