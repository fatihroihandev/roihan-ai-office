import pytest
from sqlalchemy import text

from app.db.models import AppendOnlyError, AuditLog
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture
def session(migrated_db):
    engine = create_db_engine(migrated_db)
    with create_session_factory(engine)() as s:
        yield s
    engine.dispose()


def test_sqlite_pragmas(migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert c.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()


def test_audit_log_insert_and_read(session):
    session.add(AuditLog(actor="ceo", action="project.create", entity_type="project", entity_id="p1", details={"a": 1}))
    session.commit()
    row = session.query(AuditLog).one()
    assert row.id and row.created_at and row.details == {"a": 1}


def test_audit_log_is_append_only(session):
    log = AuditLog(actor="ceo", action="x")
    session.add(log)
    session.commit()
    log.action = "diubah"
    with pytest.raises(AppendOnlyError):
        session.commit()
    session.rollback()
    session.delete(log)
    with pytest.raises(AppendOnlyError):
        session.commit()
