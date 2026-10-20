from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tasks.catalog import ACTIONS, ROLES


class TaskCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    role: Literal[tuple(ROLES)]  # type: ignore[valid-type]
    action_type: Literal[tuple(ACTIONS)]  # type: ignore[valid-type]
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=10)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    priority: int = Field(default=0, ge=-100, le=100)
    factors: dict | None = None
    preferred_model: str | None = Field(default=None, max_length=100)
    requires_tools: bool = False

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Judul tidak boleh kosong")
        return v.strip()


class PlanBody(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)

    @field_validator("goal")
    @classmethod
    def _goal(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Tujuan tidak boleh kosong")
        return v.strip()


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    parent_task_id: str | None
    title: str
    description: str
    role: str
    action_type: str
    status: str
    priority: int
    acceptance_criteria: list
    risk_level: str
    requires_approval: bool
    approved: bool
    difficulty_score: float | None
    difficulty_category: str | None
    preferred_model: str | None
    attempt_count: int
    max_retries: int
    available_at: datetime
    blocked_reason: str | None
    last_error: str | None
    last_error_kind: str | None
    verification: dict | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    number: int
    status: str
    error_kind: str | None
    error_message: str | None
    retryable: bool | None
    started_at: datetime
    finished_at: datetime | None
    provider: str | None
    model: str | None
    usage: dict | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    task_id: str
    project_id: str
    type: str
    from_status: str | None
    to_status: str | None
    reason: str | None
    actor: str
    payload: dict | None
    created_at: datetime


class RoutingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    attempt_id: str | None
    difficulty_score: float | None
    difficulty_category: str | None
    risk_level: str
    provider: str
    model: str
    num_ctx: int
    candidates: list
    reasons: list
    created_at: datetime


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    kind: str
    argv: list
    status: str
    exit_code: int | None
    duration_ms: int | None
    timed_out: bool
    output_truncated: bool
    stdout: str
    stderr: str
    sandbox: str


class TestResultOut(BaseModel):
    __test__ = False
    model_config = ConfigDict(from_attributes=True)

    name: str
    classname: str | None
    outcome: str
    message: str | None
    duration_ms: int | None


class TestRunOut(BaseModel):
    __test__ = False
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    execution_id: str | None
    status: str
    source: str
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_ms: int | None
    results: list[TestResultOut] = []


class TaskDetail(TaskOut):
    result: dict | None
    depends_on: list[str]
    attempts: list[AttemptOut]
    events: list[EventOut]
    routing: list[RoutingOut]
    executions: list[ExecutionOut] = []
    test_runs: list[TestRunOut] = []
