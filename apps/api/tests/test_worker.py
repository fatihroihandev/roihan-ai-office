import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db.base import utcnow
from app.db.models import ModelUsage, ProjectFile, RoutingDecision, Task, TaskAttempt
from app.projects.uploads import FileKind
from app.providers.base import ProviderError, ProviderErrorKind as K
from app.tasks.executors import default_executors
from tests.fakes import FakeProvider
from tests.helpers import add_task, build_env, drain, events_of, get, make_project, run, set_available_now


def attempts(env, tid):
    with env.sf() as s:
        return list(s.scalars(select(TaskAttempt).where(TaskAttempt.task_id == tid).order_by(TaskAttempt.number)))


def test_task_runs_to_completion_with_evidence(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid, title="Analisis kebutuhan", acceptance_criteria=["Ada risiko"])
    assert run(env.worker.run_once()) is True
    t = get(env, tid)
    assert t.status == "completed" and t.attempt_count == 1 and t.last_error is None
    assert t.result["output"].startswith("jawaban:") and t.result["artifact"] == f"artifacts/{tid}.md"
    assert t.verification == {"method": "output_complete", "passed": True, "criteria_checked": False}
    assert (env.settings.projects_dir / pid / t.result["artifact"]).read_text(encoding="utf-8") == t.result["output"]
    [a] = attempts(env, tid)
    assert (a.status, a.provider, a.model) == ("succeeded", "ollama", "fake-model:1b") and a.usage["calls"] == 1
    with env.sf() as s:
        assert s.query(RoutingDecision).filter_by(task_id=tid, attempt_id=a.id).count() == 1
        u = s.scalars(select(ModelUsage)).one()
        assert u.purpose == "task:analyst" and u.request_id == a.id and u.status == "ok"
    assert [e[1] for e in events_of(env, tid)] == ["draft", "queued", "running", "completed"]
    assert run(env.worker.run_once()) is False  # antrean kosong


def test_prompt_contains_task_criteria_and_master_excerpt(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    from app.db.models import ProjectFile
    name, rel, digest = env.storage.save_file(pid, __import__("app.projects.uploads", fromlist=["FileKind"]).FileKind.master,
                                              "MASTER.md", b"# Visi\nPlatform software house lokal")
    with env.sf() as s:
        s.add(ProjectFile(project_id=pid, kind="master", original_name=name, stored_name=name, relative_path=rel,
                          content_type="text/markdown", size_bytes=5, sha256=digest))
        s.commit()
    add_task(env, pid, title="Analisis", description="Telaah dokumen", acceptance_criteria=["Sebut risiko utama"])
    drain(env)
    prompt = env.provider.calls[0][1].prompt
    assert "Sebut risiko utama" in prompt and "Platform software house lokal" in prompt and "Telaah dokumen" in prompt


def test_dependencies_run_in_order_and_feed_output_forward(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=lambda p: "HASIL-A" if "TUGAS-A" in p else "selesai"))
    pid = make_project(env)
    a = add_task(env, pid, title="TUGAS-A", role="analyst")
    b = add_task(env, pid, title="TUGAS-B", role="reporter", action_type="documentation", depends_on=[a], priority=100)
    assert drain(env) == 2
    assert [get(env, x).status for x in (a, b)] == ["completed", "completed"]
    assert "TUGAS-A" in env.provider.calls[0][1].prompt              # A jalan dulu walau B berprioritas lebih tinggi
    assert "HASIL-A" in env.provider.calls[1][1].prompt              # keluaran A masuk konteks B


def test_priority_then_age_decides_order(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    low = add_task(env, pid, title="rendah", priority=0)
    first = add_task(env, pid, title="pertama", priority=5)
    second = add_task(env, pid, title="kedua", priority=5)
    drain(env)
    order = [c[1].prompt.split("\n")[0] for c in env.provider.calls]
    assert order == ["TASK: pertama", "TASK: kedua", "TASK: rendah"]
    assert all(get(env, t).status == "completed" for t in (low, first, second))


def test_only_one_task_runs_at_a_time(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(delay=0.02))
    pid = make_project(env)
    for i in range(3):
        add_task(env, pid, title=f"t{i}")
    drain(env)
    assert env.provider.max_active == 1


def test_role_without_executor_is_blocked_honestly(migrated_db, tmp_path):
    execs = {k: v for k, v in default_executors().items() if k != "content_promotion"}      # semua role kini punya agent; lepas satu
    env = build_env(migrated_db, tmp_path, executors=execs)
    pid = make_project(env)
    tid = add_task(env, pid, role="content_promotion", action_type="analysis")   # role tanpa executor terdaftar
    assert run(env.worker.run_once()) is False
    t = get(env, tid)
    assert (t.status, t.blocked_reason, t.last_error_kind, t.attempt_count) == ("blocked", "executor_not_available", "executor_not_available", 0)
    assert env.provider.calls == []


def test_tasks_needing_approval_never_run(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid, role="analyst", action_type="spend")
    assert drain(env) == 0 and get(env, tid).status == "pending_approval" and env.provider.calls == []


def test_retryable_error_schedules_backoff_then_succeeds(migrated_db, tmp_path):
    p = FakeProvider()
    p.errors = [ProviderError(K.unavailable, "mati")]
    env = build_env(migrated_db, tmp_path, provider=p, retry_backoff_base_s=60)
    pid = make_project(env)
    tid = add_task(env, pid)
    assert run(env.worker.run_once()) is True
    t = get(env, tid)
    assert (t.status, t.attempt_count, t.last_error_kind) == ("queued", 1, "unavailable")
    assert t.available_at.replace(tzinfo=None) > (utcnow() + timedelta(seconds=30)).replace(tzinfo=None)
    assert run(env.worker.run_once()) is False                    # belum waktunya (backoff)
    assert [e[1:] for e in events_of(env, tid)[-2:]] == [("failed", "unavailable"), ("queued", "auto_retry")]

    set_available_now(env, tid)
    assert run(env.worker.run_once()) is True
    t = get(env, tid)
    assert (t.status, t.attempt_count, t.last_error) == ("completed", 2, None)
    assert [a.status for a in attempts(env, tid)] == ["failed", "succeeded"]


def test_retries_are_bounded_by_max_retries(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(error=ProviderError(K.upstream_error, "500")))
    pid = make_project(env)
    tid = add_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.attempt_count) == ("failed", 3)            # 1 percobaan + 2 retry (Bagian 12.3)
    assert [a.status for a in attempts(env, tid)] == ["failed"] * 3


def test_non_retryable_error_fails_without_retry(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(error=ProviderError(K.invalid_request, "salah")))
    pid = make_project(env)
    tid = add_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.attempt_count, t.last_error_kind) == ("failed", 1, "invalid_request")
    assert attempts(env, tid)[0].retryable is False


def test_truncated_output_fails_and_is_not_marked_complete(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(truncated=True))
    pid = make_project(env)
    tid = add_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.last_error_kind, t.attempt_count, t.result) == ("failed", "output_truncated", 1, None)
    assert len(env.provider.calls) == 4  # satu jawaban utama dan tiga kelanjutan; tidak ditandai selesai
    assert "perkecil lingkup task" not in t.last_error


def test_truncated_text_output_continues_and_completes(migrated_db, tmp_path):
    provider = FakeProvider(reply=["awal jawaban yang terpotong", "lanjutan lengkap"], truncated=[True, False])
    env = build_env(migrated_db, tmp_path, provider=provider)
    pid = make_project(env)
    tid = add_task(env, pid, title="Tulis analisis", description="Analisis singkat")

    drain(env)

    task = get(env, tid)
    assert task.status == "completed"
    assert task.result["output"] == "awal jawaban yang terpotong\n\nlanjutan lengkap"
    assert len(provider.calls) == 2
    assert all(call[1].max_tokens == env.settings.ai_max_tokens_cap for call in provider.calls)


def test_empty_output_is_not_complete(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply="   "), max_retries_per_task=0)
    pid = make_project(env)
    tid = add_task(env, pid, max_retries=0)
    drain(env)
    assert (get(env, tid).status, get(env, tid).last_error_kind) == ("failed", "empty_output")


def test_failed_dependency_blocks_dependents_and_recovery_unblocks(migrated_db, tmp_path):
    p = FakeProvider(error=ProviderError(K.invalid_request, "salah"))
    env = build_env(migrated_db, tmp_path, provider=p)
    pid = make_project(env)
    a = add_task(env, pid, title="A")
    b = add_task(env, pid, title="B", depends_on=[a])
    drain(env)
    assert get(env, a).status == "failed"
    assert (get(env, b).status, get(env, b).blocked_reason) == ("blocked", "dependency_failed")
    assert get(env, b).attempt_count == 0

    p.error = None
    from app.tasks import service
    with env.sf() as s:
        service.requeue_task(s, s.get(Task, a))
        s.commit()
    drain(env)
    assert [get(env, x).status for x in (a, b)] == ["completed", "completed"]


def test_cancelled_dependency_blocks_dependent(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    a = add_task(env, pid, title="A")
    b = add_task(env, pid, title="B", depends_on=[a])
    from app.tasks import service
    with env.sf() as s:
        service.cancel_task(s, s.get(Task, a))
        s.commit()
    drain(env)
    assert get(env, b).status == "blocked" and env.provider.calls == []


def test_task_needing_approval_never_reaches_the_router_or_model_without_it(migrated_db, tmp_path):
    """Gerbang approval di titik klaim adalah lapisan pertama; router (test_routing) adalah lapisan kedua."""
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid)
    with env.sf() as s:
        s.get(Task, tid).requires_approval = True       # task berisiko yang sudah terlanjur antre tanpa approval
        s.commit()
    drain(env)
    t = get(env, tid)
    assert (t.status, t.attempt_count) == ("pending_approval", 0)
    assert attempts(env, tid) == [] and env.provider.calls == []
    from app.db.models import Approval
    with env.sf() as s:
        [ap] = s.query(Approval).filter_by(task_id=tid).all()
        assert ap.status == "pending"


def test_policy_block_from_gateway_blocks_task(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, ollama_enabled=True)
    pid = make_project(env)
    tid = add_task(env, pid)
    env.gateway._registry.get("ollama").enabled = False     # dimatikan setelah routing memeriksa registri
    env.router._registry = build_registry_enabled(env)
    drain(env)
    assert get(env, tid).status == "blocked"


def build_registry_enabled(env):
    from app.providers.registry import build_registry
    return build_registry(env.settings, {"ollama": env.provider})


def test_cancel_running_task(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(delay=5))
    pid = make_project(env)
    tid = add_task(env, pid)

    async def scenario():
        runner = asyncio.create_task(env.worker.run_once())
        for _ in range(100):
            if env.worker.current_task_id == tid:
                break
            await asyncio.sleep(0.02)
        assert await env.worker.cancel_running(tid) is True
        await asyncio.wait_for(runner, 5)
    run(scenario())
    t = get(env, tid)
    assert t.status == "cancelled" and attempts(env, tid)[0].status == "cancelled"
    assert run(env.worker.cancel_running(tid)) is False


def test_recovery_requeues_interrupted_idempotent_tasks(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid)
    with env.sf() as s:     # simulasi proses mati di tengah eksekusi
        t = s.get(Task, tid)
        t.attempt_count, t.status = 1, "running"
        s.add(TaskAttempt(task_id=tid, number=1))
        s.commit()
    assert env.worker.recover() == 1
    t = get(env, tid)
    assert t.status == "queued" and [a.status for a in attempts(env, tid)] == ["interrupted"]
    assert [e[1:] for e in events_of(env, tid)[-2:]] == [("interrupted", "worker_restart"), ("queued", "recovered")]
    drain(env)
    assert get(env, tid).status == "completed"


def test_recovery_leaves_non_idempotent_tasks_interrupted(migrated_db, tmp_path):
    class Risky:
        idempotent = False

        async def run(self, ctx):
            raise AssertionError("tidak boleh dijalankan")
    env = build_env(migrated_db, tmp_path, executors={"analyst": Risky()})
    pid = make_project(env)
    tid = add_task(env, pid)
    with env.sf() as s:
        t = s.get(Task, tid)
        t.attempt_count, t.status = 1, "running"
        s.commit()
    env.worker.recover()
    assert get(env, tid).status == "interrupted"
    assert drain(env) == 0


def test_recovery_does_not_requeue_when_retry_budget_is_spent(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid)
    with env.sf() as s:
        t = s.get(Task, tid)
        t.attempt_count, t.status = 3, "running"
        s.commit()
    env.worker.recover()
    assert get(env, tid).status == "interrupted"


def test_unexpected_executor_exception_fails_without_retry(migrated_db, tmp_path):
    class Boom:
        idempotent = True

        async def run(self, ctx):
            raise KeyError("bug")
    env = build_env(migrated_db, tmp_path, executors={"analyst": Boom()})
    pid = make_project(env)
    tid = add_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.attempt_count, t.last_error_kind) == ("failed", 1, "unexpected_error")


def test_default_executors_cover_only_roles_that_can_really_work():
    assert set(default_executors()) == {"manager", "analyst", "reporter", "developer", "qa", "reviewer", "market_research", "lead_generation",
                                           "sales_client_relations", "content_promotion", "seo_specialist", "marketing_analytics"}


def test_blocked_dependency_cascades_down_the_chain_and_recovers(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    a = add_task(env, pid, title="A", queue=False)
    b = add_task(env, pid, title="B", depends_on=[a], queue=False)
    c = add_task(env, pid, title="C", depends_on=[b], queue=False)
    from app.tasks import service
    with env.sf() as s:
        s.get(Task, a).status = "blocked"            # A terblokir (mis. kebijakan atau executor belum ada)
        s.get(Task, a).blocked_reason = "policy"
        for x in (b, c):
            service.queue_task(s, s.get(Task, x))
        s.commit()
    assert drain(env) == 0
    assert [(get(env, x).status, get(env, x).blocked_reason) for x in (b, c)] == [("blocked", "dependency_failed")] * 2
    assert env.provider.calls == []

    with env.sf() as s:
        service.requeue_task(s, s.get(Task, a))      # A dibuka kembali
        s.commit()
    drain(env)
    assert [get(env, x).status for x in (a, b, c)] == ["completed"] * 3
    assert [c[1].prompt.split("\n")[0] for c in env.provider.calls] == ["TASK: A", "TASK: B", "TASK: C"]
