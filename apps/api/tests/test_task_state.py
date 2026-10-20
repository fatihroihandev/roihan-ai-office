import pytest

from app.db.models import AppendOnlyError, Project, Task, TaskEvent
from app.db.session import create_db_engine, create_session_factory
from app.tasks.state import ALLOWED, STATUSES, TERMINAL, InvalidTransition, change_status


@pytest.fixture
def session(migrated_db):
    engine = create_db_engine(migrated_db)
    with create_session_factory(engine)() as s:
        yield s
    engine.dispose()


def new_task(session, status="draft"):
    p = Project(name="P")
    session.add(p)
    session.flush()
    t = Task(project_id=p.id, title="T", role="analyst", action_type="analysis", status=status)
    session.add(t)
    session.flush()
    return t


def test_transition_table_matches_spec():
    assert set(ALLOWED) == set(STATUSES)
    assert ALLOWED["draft"] == {"pending_approval", "queued", "cancelled"}
    assert ALLOWED["running"] == {"completed", "failed", "blocked", "interrupted", "cancelled"}
    # Tambahan Phase 6: tindakan berisiko yang approval-nya habis atau terpakai harus kembali meminta approval baru
    assert ALLOWED["failed"] == {"queued", "cancelled", "pending_approval"}
    assert ALLOWED["interrupted"] == {"queued", "failed", "cancelled", "pending_approval"}
    assert ALLOWED["queued"] == {"running", "blocked", "cancelled", "pending_approval"}
    assert ALLOWED["blocked"] == {"queued", "cancelled", "pending_approval"}
    assert ALLOWED["pending_approval"] == {"queued", "cancelled"}
    assert all(ALLOWED[s] == set() for s in TERMINAL)


@pytest.mark.parametrize("frm,to", [(f, t) for f in STATUSES for t in STATUSES if t not in ALLOWED[f]])
def test_every_disallowed_transition_is_rejected(session, frm, to):
    t = new_task(session, frm)
    with pytest.raises(InvalidTransition):
        change_status(session, t, to)
    assert t.status == frm


def test_allowed_transition_records_event_and_timestamps(session):
    t = new_task(session, "queued")
    change_status(session, t, "running", payload={"attempt": 1})
    assert t.started_at is not None and t.finished_at is None
    change_status(session, t, "completed")
    assert t.finished_at is not None
    session.flush()
    evs = session.query(TaskEvent).order_by(TaskEvent.seq).all()
    assert [(e.type, e.from_status, e.to_status) for e in evs] == [
        ("task.started", "queued", "running"), ("task.completed", "running", "completed")]
    assert evs[0].seq < evs[1].seq and evs[0].payload == {"attempt": 1}


def test_blocked_reason_set_and_cleared(session):
    t = new_task(session, "queued")
    change_status(session, t, "blocked", reason="dependency_failed")
    assert t.blocked_reason == "dependency_failed"
    change_status(session, t, "queued")
    assert t.blocked_reason is None


def test_task_events_are_append_only(session):
    t = new_task(session, "queued")
    change_status(session, t, "running")
    session.commit()
    ev = session.query(TaskEvent).first()
    ev.reason = "diubah"
    with pytest.raises(AppendOnlyError):
        session.commit()
