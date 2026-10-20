from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, UniqueConstraint, event
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


class AppendOnlyError(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def _enforce_append_only(session, _ctx, _instances):
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, (AuditLog, ModelUsage)) and (obj in session.deleted or session.is_modified(obj)):
            raise AppendOnlyError(f"{obj.__tablename__} bersifat append-only")
