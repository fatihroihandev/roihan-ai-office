from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, IdMixin, utcnow


class AuditLog(IdMixin, Base):
    """Catatan audit. Append-only: update dan delete ditolak."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    actor: Mapped[str] = mapped_column()
    action: Mapped[str] = mapped_column()
    entity_type: Mapped[str | None] = mapped_column(default=None)
    entity_id: Mapped[str | None] = mapped_column(default=None)
    details: Mapped[dict | None] = mapped_column(JSON, default=None)


class Project(IdMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")  # active | archived
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ProjectFile(IdMixin, Base):
    __tablename__ = "project_files"
    __table_args__ = (Index("ix_project_files_project", "project_id"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column()  # master | requirement | reference | asset
    original_name: Mapped[str] = mapped_column()
    stored_name: Mapped[str] = mapped_column()
    relative_path: Mapped[str] = mapped_column()  # relatif terhadap folder proyek
    content_type: Mapped[str] = mapped_column()
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ModelCapability(IdMixin, Base):
    """Registri kemampuan model. Nilai None berarti belum diketahui (tidak diasumsikan)."""

    __tablename__ = "model_capabilities"
    __table_args__ = (UniqueConstraint("provider", "model_id", name="uq_model_provider_model"),)

    provider: Mapped[str] = mapped_column()
    model_id: Mapped[str] = mapped_column()
    available: Mapped[bool] = mapped_column(default=True)
    is_paid: Mapped[bool] = mapped_column(default=False)
    context_limit: Mapped[int | None] = mapped_column(default=None)
    max_output: Mapped[int | None] = mapped_column(default=None)
    supports_tools: Mapped[bool | None] = mapped_column(default=None)
    supports_structured: Mapped[bool | None] = mapped_column(default=None)
    supports_vision: Mapped[bool | None] = mapped_column(default=None)
    supports_streaming: Mapped[bool | None] = mapped_column(default=None)
    cost_estimate_idr_per_1k: Mapped[float | None] = mapped_column(Float, default=None)
    validation_status: Mapped[str] = mapped_column(default="unvalidated")  # unvalidated | benchmarked
    benchmark: Mapped[dict | None] = mapped_column(JSON, default=None)
    details: Mapped[dict | None] = mapped_column(JSON, default=None)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelUsage(IdMixin, Base):
    """Log pemanggilan model. Append-only. Isi prompt tidak disimpan, hanya hash dan panjangnya."""

    __tablename__ = "model_usage"
    __table_args__ = (Index("ix_model_usage_created", "created_at"),)

    provider: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    purpose: Mapped[str] = mapped_column(default="adhoc")
    status: Mapped[str] = mapped_column()  # ok | error | blocked | cancelled
    error_kind: Mapped[str | None] = mapped_column(default=None)
    request_id: Mapped[str | None] = mapped_column(default=None)
    correlation_id: Mapped[str | None] = mapped_column(default=None)
    prompt_sha256: Mapped[str | None] = mapped_column(default=None)
    prompt_chars: Mapped[int] = mapped_column(default=0)
    prompt_tokens: Mapped[int | None] = mapped_column(default=None)
    completion_tokens: Mapped[int | None] = mapped_column(default=None)
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    is_paid: Mapped[bool] = mapped_column(default=False)
    cost_idr: Mapped[float] = mapped_column(Float, default=0.0)


class Task(IdMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_status", "status"), Index("ix_tasks_project", "project_id"))

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), default=None)
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column()
    action_type: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft")
    priority: Mapped[int] = mapped_column(default=0)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list)
    risk_level: Mapped[str] = mapped_column(default="low")
    requires_approval: Mapped[bool] = mapped_column(default=False)
    approved: Mapped[bool] = mapped_column(default=False)  # diisi oleh Approval Center (Phase 6)
    difficulty_factors: Mapped[dict | None] = mapped_column(JSON, default=None)
    difficulty_score: Mapped[float | None] = mapped_column(Float, default=None)
    difficulty_category: Mapped[str | None] = mapped_column(default=None)
    preferred_model: Mapped[str | None] = mapped_column(default=None)
    requires_tools: Mapped[bool] = mapped_column(default=False)
    attempt_count: Mapped[int] = mapped_column(default=0)
    attempts_baseline: Mapped[int] = mapped_column(default=0)  # retry manual memberi jatah retry otomatis baru
    max_retries: Mapped[int] = mapped_column(default=2)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    blocked_reason: Mapped[str | None] = mapped_column(default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    last_error_kind: Mapped[str | None] = mapped_column(default=None)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    verification: Mapped[dict | None] = mapped_column(JSON, default=None)
    review_status: Mapped[str | None] = mapped_column(default=None)  # approved | changes_requested (diisi Reviewer)
    created_by: Mapped[str] = mapped_column(default="ceo")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"), primary_key=True)


class TaskAttempt(IdMixin, Base):
    __tablename__ = "task_attempts"
    __table_args__ = (Index("ix_task_attempts_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(default="running")  # running|succeeded|failed|interrupted|cancelled|blocked
    error_kind: Mapped[str | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    retryable: Mapped[bool | None] = mapped_column(default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    provider: Mapped[str | None] = mapped_column(default=None)
    model: Mapped[str | None] = mapped_column(default=None)
    usage: Mapped[dict | None] = mapped_column(JSON, default=None)


class TaskEvent(Base):
    """Jejak kejadian task. `seq` monoton naik dan dipakai klien untuk mendeteksi event yang terlewat."""

    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task", "task_id"), {"sqlite_autoincrement": True})

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String)
    project_id: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column()
    from_status: Mapped[str | None] = mapped_column(default=None)
    to_status: Mapped[str | None] = mapped_column(default=None)
    reason: Mapped[str | None] = mapped_column(default=None)
    actor: Mapped[str] = mapped_column(default="system")
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RoutingDecision(IdMixin, Base):
    __tablename__ = "routing_decisions"
    __table_args__ = (Index("ix_routing_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    attempt_id: Mapped[str | None] = mapped_column(default=None)
    difficulty_score: Mapped[float | None] = mapped_column(Float, default=None)
    difficulty_category: Mapped[str | None] = mapped_column(default=None)
    risk_level: Mapped[str] = mapped_column(default="low")
    provider: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column()
    num_ctx: Mapped[int] = mapped_column()
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    reasons: Mapped[list] = mapped_column(JSON, default=list)


class Execution(IdMixin, Base):
    """Log eksekusi perintah di sandbox (Bagian 14.1): perintah, waktu, status, exit code. Append-only."""

    __tablename__ = "executions"
    __table_args__ = (Index("ix_executions_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    attempt_id: Mapped[str | None] = mapped_column(default=None)
    project_id: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column()  # pytest | python_file | compile
    argv: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column()  # ok | failed | timeout | error
    exit_code: Mapped[int | None] = mapped_column(default=None)
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    timed_out: Mapped[bool] = mapped_column(default=False)
    output_truncated: Mapped[bool] = mapped_column(default=False)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    sandbox: Mapped[str] = mapped_column(default="")


class TestRun(IdMixin, Base):
    __test__ = False  # bukan kelas tes pytest
    __tablename__ = "test_runs"
    __table_args__ = (Index("ix_test_runs_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    attempt_id: Mapped[str | None] = mapped_column(default=None)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey("executions.id", ondelete="RESTRICT"), default=None)
    project_id: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column()  # passed | failed | error
    source: Mapped[str] = mapped_column(default="junit")  # junit | stdout | none
    total: Mapped[int] = mapped_column(default=0)
    passed: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    errors: Mapped[int] = mapped_column(default=0)
    skipped: Mapped[int] = mapped_column(default=0)
    duration_ms: Mapped[int | None] = mapped_column(default=None)


class TestResult(IdMixin, Base):
    __test__ = False
    __tablename__ = "test_results"
    __table_args__ = (Index("ix_test_results_run", "test_run_id"),)

    test_run_id: Mapped[str] = mapped_column(ForeignKey("test_runs.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column()
    classname: Mapped[str | None] = mapped_column(default=None)
    outcome: Mapped[str] = mapped_column()  # passed | failed | error | skipped
    message: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int | None] = mapped_column(default=None)


class Approval(IdMixin, Base):
    """Persetujuan manusia untuk satu tindakan spesifik (Bagian 12.5). Terikat pada sidik jari isi task."""

    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_task", "task_id"), Index("ix_approvals_status", "status"))

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))
    project_id: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column(default="task_execution")
    action_type: Mapped[str] = mapped_column()
    risk_level: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="pending")  # pending|approved|rejected|expired|cancelled
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column()
    requested_by: Mapped[str] = mapped_column(default="system")
    decided_by: Mapped[str | None] = mapped_column(default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_reason: Mapped[str | None] = mapped_column(Text, default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CodeReview(IdMixin, Base):
    """Hasil review independen. Append-only."""

    __tablename__ = "code_reviews"
    __table_args__ = (Index("ix_code_reviews_task", "task_id"),)

    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="RESTRICT"))  # task Reviewer
    project_id: Mapped[str] = mapped_column()
    reviewed_task_ids: Mapped[list] = mapped_column(JSON, default=list)
    commit: Mapped[str | None] = mapped_column(default=None)
    verdict: Mapped[str] = mapped_column()  # approved | changes_requested
    summary: Mapped[str] = mapped_column(Text, default="")
    verdict_reasons: Mapped[list] = mapped_column(JSON, default=list)
    criteria: Mapped[list] = mapped_column(JSON, default=list)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    unresolved_risks: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class AppendOnlyError(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def _enforce_append_only(session, _ctx, _instances):
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, (AuditLog, ModelUsage, TaskEvent, RoutingDecision, Execution, TestRun, TestResult, CodeReview)) and (obj in session.deleted or session.is_modified(obj)):
            raise AppendOnlyError(f"{obj.__tablename__} bersifat append-only")
