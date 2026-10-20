import json

import pytest
from sqlalchemy import select

from app.db.models import Task, TaskAttempt, TaskDependency
from app.tasks.executors import ExecutorError, parse_plan
from tests.fakes import FakeProvider
from tests.helpers import add_task, build_env, drain, get, make_project

GOOD = {"tasks": [
    {"key": "t1", "title": "Analisis kebutuhan", "description": "Telaah", "role": "analyst", "action_type": "analysis",
     "acceptance_criteria": ["Ada daftar risiko"], "depends_on": [],
     "factors": {"complexity": 4, "uncertainty": 3, "technical_risk": 2, "scope": 3, "reasoning": 4, "context_requirement": 2}},
    {"key": "t2", "title": "Implementasi", "role": "developer", "action_type": "code_change",
     "acceptance_criteria": ["Tes lolos"], "depends_on": ["t1"]},
    {"key": "t3", "title": "Kirim penawaran", "role": "sales_client_relations", "action_type": "external_outreach",
     "depends_on": ["t2"]},
]}


def plan_json(d=GOOD):
    return "Berikut rencananya:\n```json\n" + json.dumps(d) + "\n```"


def test_parse_plan_accepts_valid_plan_wrapped_in_text():
    plan = parse_plan(plan_json())
    assert [t.key for t in plan.tasks] == ["t1", "t2", "t3"]


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d["tasks"][0].update(role="manager"), "Rencana tidak valid"),
    (lambda d: d["tasks"][0].update(role="tukang"), "Rencana tidak valid"),
    (lambda d: d["tasks"][0].update(action_type="hack"), "Rencana tidak valid"),
    (lambda d: d["tasks"][0].update(title="  "), "Rencana tidak valid"),
    (lambda d: d["tasks"][1].update(key="t1"), "ganda"),
    (lambda d: d["tasks"][0].update(depends_on=["t2"]), "belum didefinisikan"),
    (lambda d: d["tasks"][0].update(depends_on=["t1"]), "belum didefinisikan"),   # dependensi ke diri sendiri
    (lambda d: d.update(tasks=[]), "Rencana tidak valid"),
    (lambda d: d.update(tasks=[GOOD["tasks"][0]] * 13), "Rencana tidak valid"),
])
def test_parse_plan_rejects_invalid(mutate, fragment):
    d = json.loads(json.dumps(GOOD))
    mutate(d)
    with pytest.raises(ExecutorError) as e:
        parse_plan(json.dumps(d))
    assert fragment in e.value.message and e.value.retryable


@pytest.mark.parametrize("text", ["tidak ada json", "{rusak", "[1,2]"])
def test_parse_plan_rejects_non_json(text):
    with pytest.raises(ExecutorError):
        parse_plan(text)


def plan_task(env, pid, goal="Bangun CRM internal"):
    from app.tasks import service
    with env.sf() as s:
        t = service.create_task(s, project_id=pid, title="Rencana", description=goal, role="manager", action_type="planning")
        service.queue_task(s, t)
        s.commit()
        return t.id


def test_manager_creates_draft_tasks_with_dependencies_risk_and_difficulty(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[plan_json()]))
    pid = make_project(env)
    pt = plan_task(env, pid)
    drain(env)
    plan = get(env, pt)
    assert plan.status == "completed" and plan.verification == {"method": "plan_schema_and_dag", "passed": True}
    ids = plan.result["created_task_ids"]
    with env.sf() as s:
        kids = {t.title: t for t in s.scalars(select(Task).where(Task.parent_task_id == pt))}
        assert len(ids) == 3 and all(t.status == "draft" and t.created_by == "manager" for t in kids.values())
        a, b, c = kids["Analisis kebutuhan"], kids["Implementasi"], kids["Kirim penawaran"]
        assert (a.difficulty_score, a.difficulty_category) == (53.75, "medium")
        assert (b.risk_level, b.requires_approval) == ("medium", False)
        assert (c.risk_level, c.requires_approval) == ("critical", True)
        deps = {(d.task_id, d.depends_on_id) for d in s.scalars(select(TaskDependency))}
        assert deps == {(b.id, a.id), (c.id, b.id)}


def test_manager_never_queues_by_itself_and_risky_tasks_wait_for_approval(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[plan_json()]))
    pid = make_project(env)
    pt = plan_task(env, pid)
    drain(env)
    assert drain(env) == 0                                         # draft tidak dijalankan
    from app.tasks import service
    with env.sf() as s:
        service.queue_drafts(s, pid)
        s.commit()
    with env.sf() as s:
        st = {t.role: t.status for t in s.scalars(select(Task).where(Task.parent_task_id == pt))}
    assert st == {"analyst": "queued", "developer": "queued", "sales_client_relations": "pending_approval"}


def test_manager_retries_once_with_error_feedback(migrated_db, tmp_path):
    p = FakeProvider(reply=["bukan json sama sekali", plan_json()])
    env = build_env(migrated_db, tmp_path, provider=p)
    pid = make_project(env)
    pt = plan_task(env, pid)
    drain(env)
    assert get(env, pt).status == "completed" and len(p.calls) == 2
    assert "Jawaban sebelumnya ditolak" in p.calls[1][1].prompt
    with env.sf() as s:
        assert s.query(TaskAttempt).filter_by(task_id=pt).one().usage["calls"] == 2


def test_invalid_plan_fails_without_creating_partial_tasks_and_is_retried(migrated_db, tmp_path):
    bad = json.dumps({"tasks": [{"key": "a", "title": "X", "role": "analyst", "action_type": "analysis", "depends_on": ["zzz"]}]})
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=lambda p: bad))
    pid = make_project(env)
    pt = plan_task(env, pid)
    drain(env)
    t = get(env, pt)
    assert (t.status, t.attempt_count, t.last_error_kind) == ("failed", 3, "invalid_plan")
    with env.sf() as s:
        assert s.query(Task).filter(Task.parent_task_id == pt).count() == 0


def test_truncated_plan_is_rejected(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=lambda p: plan_json(), truncated=True))
    pid = make_project(env)
    pt = plan_task(env, pid)
    drain(env)
    assert get(env, pt).last_error_kind == "invalid_plan"


def test_planner_prompt_lists_allowed_roles_and_actions_and_goal(migrated_db, tmp_path):
    p = FakeProvider(reply=[plan_json()])
    env = build_env(migrated_db, tmp_path, provider=p)
    pid = make_project(env)
    plan_task(env, pid, goal="Bangun CRM internal")
    drain(env)
    prompt = p.calls[0][1].prompt
    assert "Bangun CRM internal" in prompt and "external_outreach" in prompt and "sales_client_relations" in prompt
    assert "role yang diizinkan" in prompt and "manager," not in prompt.split("role yang diizinkan:")[1].split("\n")[0]


def test_manager_rejects_non_planning_actions(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid, role="manager", action_type="analysis")
    drain(env)
    assert (get(env, tid).status, get(env, tid).last_error_kind) == ("failed", "unsupported_action")


def test_compact_factor_list_is_accepted_and_scored(migrated_db, tmp_path):
    d = json.loads(json.dumps(GOOD))
    d["tasks"][0]["factors"] = [4, 3, 2, 3, 4, 2]       # format ringkas: hemat token pada model lokal
    d["tasks"][1]["factors"] = [9, 9]                  # panjang salah: diabaikan, jatuh ke default (3 semua)
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[json.dumps(d)]))
    pid = make_project(env)
    pt = plan_task(env, pid)
    drain(env)
    with env.sf() as s:
        kids = {t.title: t for t in s.scalars(select(Task).where(Task.parent_task_id == pt))}
    assert kids["Analisis kebutuhan"].difficulty_score == 53.75
    assert kids["Implementasi"].difficulty_score == 50.0


def test_planner_requests_schema_constrained_output(migrated_db, tmp_path):
    from app.tasks.catalog import ACTIONS, PLANNABLE_ROLES
    from app.tasks.executors import PLAN_SCHEMA
    p = FakeProvider(reply=[plan_json()])
    env = build_env(migrated_db, tmp_path, provider=p)
    pid = make_project(env)
    plan_task(env, pid)
    drain(env)
    sent = p.calls[0][1].json_schema
    item = sent["properties"]["tasks"]["items"]["properties"]
    assert sent is PLAN_SCHEMA and item["role"]["enum"] == PLANNABLE_ROLES and item["action_type"]["enum"] == ACTIONS
    assert "manager" not in item["role"]["enum"]


def test_validation_feedback_is_concise_and_points_to_the_field():
    d = json.loads(json.dumps(GOOD))
    d["tasks"][0]["role"] = "designer"
    with pytest.raises(ExecutorError) as e:
        parse_plan(json.dumps(d))
    assert e.value.message.startswith("Rencana tidak valid: tasks.0.role:") and len(e.value.message) <= 400
    assert "pydantic" not in e.value.message and "For further information" not in e.value.message
