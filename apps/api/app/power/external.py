"""Operasi eksternal dengan idempotency key (Addendum v2.3, Bagian 29.A.9).

Setiap operasi ke dunia luar dicatat sebelum dan sesudah dijalankan. Setelah pause, resume, atau crash, operasi yang berstatus
`started` atau `unknown` TIDAK pernah diulang otomatis: hasilnya harus diverifikasi manusia (RecoveryItem `external_unknown`).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExternalOperation

UNCERTAIN = {"started", "unknown"}


def begin_operation(session: Session, *, kind: str, key: str, task_id: str | None, payload_sha256: str | None = None) -> tuple[ExternalOperation, bool]:
    """Daftarkan operasi. Kembalikan (operasi, baru). Key yang sama mengembalikan operasi yang sudah ada (tidak membuat ganda)."""
    existing = session.scalar(select(ExternalOperation).where(ExternalOperation.idempotency_key == key))
    if existing is not None:
        return existing, False
    op = ExternalOperation(kind=kind, idempotency_key=key, task_id=task_id, payload_sha256=payload_sha256, status="started")
    session.add(op)
    session.flush()
    return op, True


def finish_operation(op: ExternalOperation, status: str, result: dict | None = None) -> None:
    assert status in {"confirmed", "failed", "unknown"}
    op.status = status
    op.result = result


def uncertain_operations(session: Session) -> list[ExternalOperation]:
    return list(session.scalars(select(ExternalOperation).where(ExternalOperation.status.in_(UNCERTAIN))))
