from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    task_id: str
    project_id: str
    kind: str
    action_type: str
    risk_level: str
    status: str
    payload: dict
    requested_by: str
    decided_by: str | None
    decided_at: datetime | None
    decision_reason: str | None
    expires_at: datetime
    used_at: datetime | None


class Decision(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    task_id: str
    reviewed_task_ids: list
    commit: str | None
    verdict: str
    summary: str
    verdict_reasons: list
    criteria: list
    findings: list
    unresolved_risks: list
    evidence: dict
