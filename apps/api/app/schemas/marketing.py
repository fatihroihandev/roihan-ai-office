from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _strip(v):
    return v.strip() if isinstance(v, str) else v


class SourceIn(_Body):
    source_type: str = Field(max_length=40)
    url: str | None = Field(default=None, max_length=2000)
    title: str | None = Field(default=None, max_length=200)
    collected_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)


class CompanyIn(_Body):
    name: str = Field(min_length=1, max_length=200)
    domain: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=120)
    size_band: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=120)
    website: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)

    _s = field_validator("name", "industry", "city", mode="before")(_strip)


class ContactIn(_Body):
    name: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)


class LeadCreate(_Body):
    company: CompanyIn
    contact: ContactIn | None = None
    source: SourceIn
    product_id: str | None = None


class LeadContactUpdate(_Body):
    contact_name: str | None = Field(default=None, max_length=120)
    contact_title: str | None = Field(default=None, max_length=120)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=40)


class StatusBody(_Body):
    status: str = Field(max_length=30)
    reason: str | None = Field(default=None, max_length=1000)
    override_reason: str | None = Field(default=None, max_length=1000)


class ForwardBody(_Body):
    override_reason: str | None = Field(default=None, max_length=1000)
    draft_outreach_product_id: str | None = None      # jika diisi, sekaligus membuat task draf outreach


class ReasonBody(_Body):
    reason: str | None = Field(default=None, max_length=1000)


class InteractionIn(_Body):
    kind: str = Field(max_length=20)
    summary: str = Field(min_length=1, max_length=4000)
    occurred_at: datetime | None = None


class ConvertBody(_Body):
    title: str = Field(min_length=1, max_length=200)
    value_estimate_idr: int | None = Field(default=None, ge=0, le=10**13)
    summary: str | None = Field(default=None, max_length=2000)


class StageBody(_Body):
    stage: str = Field(max_length=20)
    reason: str | None = Field(default=None, max_length=1000)
    won_value_idr: int | None = Field(default=None, ge=0, le=10**13)


class RequirementIn(_Body):
    text: str = Field(min_length=1, max_length=4000)
    priority: str = Field(default="normal", max_length=10)


class SentBody(_Body):
    note: str | None = Field(default=None, max_length=1000)


class SuppressionIn(_Body):
    kind: str = Field(max_length=10)
    value: str = Field(min_length=1, max_length=254)
    reason: str = Field(default="opt_out", max_length=20)


class IntakeBody(_Body):
    source: SourceIn
    raw_text: str = Field(min_length=1, max_length=8000)
    product_id: str | None = None


class ResearchBody(_Body):
    topic: str = Field(min_length=3, max_length=200)
    material: str = Field(min_length=1, max_length=8000)
    product_id: str | None = None


class OutreachTaskBody(_Body):
    lead_id: str
    product_id: str
    version_id: str | None = None
    channel: str = Field(default="email", pattern="^email$")
