import pytest
from sqlalchemy import select

from app.db.models import Task, TaskDependency
from app.tasks import service
from app.tasks.service import TaskError
from app.tasks.state import InvalidTransition, change_status
from tests.helpers import add_task, build_env, events_of, get, make_project


@pytest.fixture
def env(migrated_db, tmp_path):
    return build_env(migrated_db, tmp_path)


def test_create_task_computes_risk_and_difficulty(env):
    pid = make_project(env)
    tid = add_task(env, pid, action_type="code_change", role="developer", queue=False,
                   factors={"complexity": 5, "uncertainty": 5, "technical_risk": 5, "scope": 5, "reasoning": 5, "context_requirement": 5})
    t = get(env, tid)
    assert (t.status, t.risk_level, t.requires_approval) == ("draft", "medium", False)
    assert (t.difficulty_score, t.difficulty_category) == (100.0, "critical")
    assert events_of(env, tid) == [(None, "draft", None)]


def test_create_task_validation(env):
    pid, other = make_project(env), make_project(env, "Lain")
    dep_other = add_task(env, other, queue=False)
    with env.sf() as s:
        for kw in ({"role": "tukang"}, {"action_type": "hack"}, {"depends_on": ["tidak-ada"]}, {"depends_on": [dep_other]}):
            args = {"project_id": pid, "title": "T", "role": "analyst", "action_type": "analysis", **kw}
            with pytest.raises(TaskError):
                service.create_task(s, **args)


def test_dependencies_are_stored_and_deduplicated(env):
    pid = make_project(env)
    a = add_task(env, pid, queue=False)
    b = add_task(env, pid, queue=False, depends_on=[a, a])
    with env.sf() as s:
        assert list(s.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == b))) == [a]


def test_high_risk_task_goes_to_pending_approval_not_queue(env):
    pid = make_project(env)
    tid = add_task(env, pid, role="sales_client_relations", action_type="external_outreach")
    t = get(env, tid)
    assert (t.status, t.risk_level, t.requires_approval, t.approved) == ("pending_approval", "critical", True, False)
    assert events_of(env, tid)[-1] == ("draft", "pending_approval", "risk_critical")


def test_queue_only_from_draft(env):
    pid = make_project(env)
    tid = add_task(env, pid)
    with env.sf() as s:
        with pytest.raises(TaskError):
            service.queue_task(s, s.get(Task, tid))


def test_queue_drafts_queues_all_drafts_of_project_only(env):
    pid, other = make_project(env), make_project(env, "Lain")
    a, b = add_task(env, pid, queue=False), add_task(env, pid, queue=False)
    c = add_task(env, other, queue=False)
    with env.sf() as s:
        assert len(service.queue_drafts(s, pid)) == 2
        s.commit()
    assert (get(env, a).status, get(env, b).status, get(env, c).status) == ("queued", "queued", "draft")


def test_cancel_from_non_running_states(env):
    pid = make_project(env)
    for setup in ("draft", "queued", "blocked", "failed", "interrupted", "pending_approval"):
        tid = add_task(env, pid, queue=False)
        with env.sf() as s:
            t = s.get(Task, tid)
            t.status = setup
            service.cancel_task(s, t)
            s.commit()
        assert get(env, tid).status == "cancelled"


def test_cancel_refuses_running_and_terminal(env):
    pid = make_project(env)
    tid = add_task(env, pid, queue=False)
    with env.sf() as s:
        t = s.get(Task, tid)
        t.status = "running"
        with pytest.raises(TaskError):
            service.cancel_task(s, t)
        t.status = "completed"
        with pytest.raises(InvalidTransition):
            service.cancel_task(s, t)


def test_manual_requeue_grants_fresh_retry_allowance(env):
    pid = make_project(env)
    tid = add_task(env, pid, queue=False)
    with env.sf() as s:
        t = s.get(Task, tid)
        t.status, t.attempt_count = "failed", 3
        service.requeue_task(s, t)
        assert (t.status, t.attempts_baseline) == ("queued", 3)
        t.status = "completed"
        with pytest.raises(TaskError):
            service.requeue_task(s, t)
        s.commit()
