from sqlalchemy import JSON, Index, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import Base, IdMixin


class AuditLog(IdMixin, Base):
    """Catatan audit. Append-only: update dan delete ditolak."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    actor: Mapped[str] = mapped_column()
    action: Mapped[str] = mapped_column()
    entity_type: Mapped[str | None] = mapped_column(default=None)
    entity_id: Mapped[str | None] = mapped_column(default=None)
    details: Mapped[dict | None] = mapped_column(JSON, default=None)


class AppendOnlyError(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def _enforce_append_only(session, _ctx, _instances):
    for obj in list(session.dirty) + list(session.deleted):
        if isinstance(obj, AuditLog) and (obj in session.deleted or session.is_modified(obj)):
            raise AppendOnlyError("audit_logs bersifat append-only")
