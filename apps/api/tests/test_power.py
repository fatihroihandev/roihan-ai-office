"""Office Power Control (Phase 13): OFF/ON, checkpoint, pemulihan, crash, operasi eksternal, API."""
import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    ExternalOperation, ModelUsage, PowerCommand, PowerState, RecoveryItem, RecoveryLog, Task, TaskAttempt, TaskCheckpoint, TaskEvent,
)
from app.main import create_app
from app.power import external
from app.power import service as power
from app.power.service import PAUSED, PAUSING, RECOVERY_REQUIRED, RESUMING, RUNNING, PowerController, PowerError
from app.tasks.executors import ExecutorOutcome
from app.workspace import git as workspace_git
from tests.fakes import FakeProvider
from tests.helpers import add_task, build_env, get, make_project


OK = ExecutorOutcome("ok", True, {"method": "test", "passed": True}, {"output": "ok"})


class Gate:
    """Executor yang berhenti sampai dilepas: mensimulasikan task yang sedang berjalan."""

    idempotent = True

    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.runs = 0

    async def run(self, ctx):
        self.runs += 1
        self.started.set()
        await self.release.wait()
        return OK


class Risky(Gate):
    idempotent = False


class Stubborn:
    """Executor yang mengabaikan pembatalan sampai waktunya habis (penghentian tidak terkonfirmasi)."""

    idempotent = True

    def __init__(self):
        self.started = asyncio.Event()
        self.finish = asyncio.Event()

    async def run(self, ctx):
        self.started.set()
        while not self.finish.is_set():
            try:
                await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                pass
        return OK


class Instant:
    idempotent = True

    def __init__(self):
        self.runs = 0

    async def run(self, ctx):
        self.runs += 1
        return OK


def make(migrated_db, tmp_path, executors=None, **kw):
    kw.setdefault("power_pause_grace_s", 0.0)
    kw.setdefault("power_checkpoint_interval_s", 0.0)
    kw.setdefault("power_interrupt_wait_s", 3.0)
    env = build_env(migrated_db, tmp_path, executors=executors, **kw)
    ctl = PowerController(env.settings, env.sf, env.worker.checkpoints, env.worker)
    env.worker.set_gate(ctl.can_schedule)
    return env, ctl


def pstate(env) -> PowerState:
    with env.sf() as s:
        st = s.get(PowerState, 1)
        s.expunge(st)
        return st


def rows(env, model, *where):
    with env.sf() as s:
        return list(s.scalars(select(model).where(*where)))


def statuses(env, *ids):
    return [get(env, i).status for i in ids]


async def pause_with_running(env, ctl, ex, tid=None):
    runner = asyncio.create_task(env.worker.run_once())
    await asyncio.wait_for(ex.started.wait(), 5)
    out = await ctl.request_off()
    await ctl.wait_idle()
    await asyncio.wait_for(runner, 5)
    return out


# ------------------------------------------------------------------ OFF

def test_off_without_active_tasks_reaches_paused_and_stops_scheduler(migrated_db, tmp_path):
    async def go():
        ex = Instant()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        tid = add_task(env, make_project(env))
        out = await ctl.request_off()
        assert out["accepted"] and out["state"] == PAUSING
        await ctl.wait_idle()
        assert pstate(env).state == PAUSED
        assert await env.worker.run_once() is False      # scheduler tidak memulai task baru
        assert get(env, tid).status == "queued" and ex.runs == 0
        cmd = rows(env, PowerCommand)[0]
        assert cmd.action == "off" and cmd.status == "completed" and cmd.finished_at is not None
        assert [p["step"] for p in cmd.progress][:2] == ["scheduler_stopped", "waiting_active_tasks"]
        assert cmd.result["database_ok"] is True
    asyncio.run(go())


def test_off_is_idempotent_even_when_sent_concurrently(migrated_db, tmp_path):
    async def go():
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
        a, b = await asyncio.gather(ctl.request_off(), ctl.request_off())
        await ctl.wait_idle()
        assert sorted([a["accepted"], b["accepted"]]) == [False, True]
        again = await ctl.request_off()
        assert again["already"] and again["state"] == PAUSED
        assert len(rows(env, PowerCommand)) == 1
    asyncio.run(go())


def test_off_with_full_queue_keeps_queue_and_dependencies_intact(migrated_db, tmp_path):
    async def go():
        ex = Instant()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex, "reporter": ex})
        pid = make_project(env)
        a = add_task(env, pid, title="A")
        b = add_task(env, pid, title="B", role="reporter", action_type="documentation", depends_on=[a])
        c = add_task(env, pid, title="C")
        await ctl.request_off()
        await ctl.wait_idle()
        assert statuses(env, a, b, c) == ["queued", "queued", "queued"]
        assert ex.runs == 0
        with env.sf() as s:
            from app.tasks import service
            assert service.dependency_ids(s, b) == [a]
    asyncio.run(go())


def test_off_while_task_running_saves_valid_checkpoint_and_interrupts_without_killing_worker(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        tid = add_task(env, make_project(env))
        await pause_with_running(env, ctl, ex)
        t = get(env, tid)
        assert t.status == "interrupted" and pstate(env).state == PAUSED
        ev = [(e.to_status, e.reason) for e in rows(env, TaskEvent, TaskEvent.task_id == tid)]
        assert ("interrupted", "paused") in ev
        assert [a.status for a in rows(env, TaskAttempt, TaskAttempt.task_id == tid)] == ["interrupted"]
        pause_cps = rows(env, TaskCheckpoint, TaskCheckpoint.task_id == tid, TaskCheckpoint.kind == "pause")
        assert len(pause_cps) == 1 and pause_cps[0].validation["valid"] is True
        assert pause_cps[0].payload["task"]["status"] == "running"   # keadaan saat checkpoint, sebelum dihentikan
        assert env.worker.current_task_id is None
    asyncio.run(go())


def test_slow_provider_is_cancelled_on_off(migrated_db, tmp_path):
    async def go():
        provider = FakeProvider(delay=30)
        env, ctl = make(migrated_db, tmp_path, provider=provider)
        tid = add_task(env, make_project(env))
        runner = asyncio.create_task(env.worker.run_once())
        for _ in range(100):
            if provider.active:
                break
            await asyncio.sleep(0.05)
        t0 = time.monotonic()
        await ctl.request_off()
        await ctl.wait_idle()
        await asyncio.wait_for(runner, 5)
        assert time.monotonic() - t0 < 10                       # tidak menunggu provider 30 detik
        assert get(env, tid).status == "interrupted" and pstate(env).state == PAUSED
    asyncio.run(go())


def test_off_waits_for_grace_period_so_a_finishing_task_completes_normally(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex}, power_pause_grace_s=5.0)
        tid = add_task(env, make_project(env))
        runner = asyncio.create_task(env.worker.run_once())
        await asyncio.wait_for(ex.started.wait(), 5)
        await ctl.request_off()
        await asyncio.sleep(0.5)
        assert pstate(env).state == PAUSING                     # masih menunggu langkah aman
        ex.release.set()
        await ctl.wait_idle()
        await asyncio.wait_for(runner, 5)
        assert get(env, tid).status == "completed" and pstate(env).state == PAUSED
    asyncio.run(go())


def test_unconfirmed_stop_is_reported_honestly_not_as_paused(migrated_db, tmp_path):
    async def go():
        ex = Stubborn()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex}, power_interrupt_wait_s=0.3)
        tid = add_task(env, make_project(env))
        runner = asyncio.create_task(env.worker.run_once())
        await asyncio.wait_for(ex.started.wait(), 5)
        await ctl.request_off()
        await ctl.wait_idle()
        st = pstate(env)
        assert st.state == RECOVERY_REQUIRED and not power.scheduling_allowed(st)
        assert [i.kind for i in rows(env, RecoveryItem, RecoveryItem.status == "open")] == ["stop_unconfirmed"]
        assert rows(env, PowerCommand)[0].status == "failed"
        ex.finish.set()
        await asyncio.wait_for(runner, 5)
    asyncio.run(go())


# ------------------------------------------------------------------ ON / resume

def test_resume_requeues_interrupted_task_from_checkpoint_and_completes(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        tid = add_task(env, make_project(env))
        await pause_with_running(env, ctl, ex)
        before = get(env, tid)
        ex.release.set()
        out = await ctl.request_on()
        assert out["accepted"] and out["state"] == RESUMING
        await ctl.wait_idle()
        assert pstate(env).state == RUNNING
        t = get(env, tid)
        assert t.status == "queued"
        assert t.attempts_baseline == before.attempts_baseline + 1   # percobaan yang dijeda tidak memakai jatah retry
        log = rows(env, RecoveryLog, RecoveryLog.task_id == tid)
        assert [r.action for r in log] == ["resumed_from_checkpoint"] and log[0].checkpoint_id
        assert await env.worker.run_once() is True
        assert get(env, tid).status == "completed" and ex.runs == 2
        # percobaan kedua mendapat ringkasan checkpoint sebelumnya
        ev = [e for e in rows(env, TaskEvent, TaskEvent.task_id == tid) if e.reason == "resumed"]
        assert ev and ev[0].payload["checkpoint_id"] == log[0].checkpoint_id
    asyncio.run(go())


def test_completed_tasks_are_never_rerun_after_pause_and_resume(migrated_db, tmp_path):
    async def go():
        ex = Instant()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        done = add_task(env, make_project(env))
        assert await env.worker.run_once() is True
        await ctl.request_off(); await ctl.wait_idle()
        await ctl.request_on(); await ctl.wait_idle()
        assert await env.worker.run_once() is False
        assert get(env, done).status == "completed" and ex.runs == 1
        assert [r.action for r in rows(env, RecoveryLog)].count("kept_completed") == 1
    asyncio.run(go())


def test_dependency_chain_resumes_in_order(migrated_db, tmp_path):
    async def go():
        gate, after = Gate(), Instant()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": gate, "reporter": after})
        pid = make_project(env)
        a = add_task(env, pid, title="A")
        b = add_task(env, pid, title="B", role="reporter", action_type="documentation", depends_on=[a])
        await pause_with_running(env, ctl, gate)
        gate.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        for _ in range(4):
            await env.worker.run_once()
        assert statuses(env, a, b) == ["completed", "completed"]
        order = [e.task_id for e in rows(env, TaskEvent, TaskEvent.to_status == "completed") if e.task_id in (a, b)]
        assert order == [a, b]
    asyncio.run(go())


def test_on_is_idempotent_and_refused_while_pausing(migrated_db, tmp_path):
    async def go():
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
        first = await ctl.request_on()
        assert first["already"] and first["state"] == RUNNING
        await ctl.request_off(); await ctl.wait_idle()
        a, b = await asyncio.gather(ctl.request_on(), ctl.request_on())
        await ctl.wait_idle()
        assert sorted([a["accepted"], b["accepted"]]) == [False, True] and pstate(env).state == RUNNING
        with env.sf() as s:                                      # ON saat PAUSING ditolak
            power.set_state(s, PAUSING, reason="uji", force=True)
            s.commit()
        with pytest.raises(PowerError):
            await ctl.request_on()
    asyncio.run(go())


def test_repeated_off_on_cycles_are_safe(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        tid = add_task(env, make_project(env))
        await pause_with_running(env, ctl, ex)
        ex.release.set()
        for _ in range(3):
            await ctl.request_on(); await ctl.wait_idle()
            await ctl.request_off(); await ctl.wait_idle()
            assert pstate(env).state == PAUSED
        await ctl.request_on(); await ctl.wait_idle()
        assert await env.worker.run_once() is True
        assert get(env, tid).status == "completed"
        assert len(rows(env, TaskAttempt, TaskAttempt.task_id == tid, TaskAttempt.status == "succeeded")) == 1
    asyncio.run(go())


def test_risky_task_is_not_rerun_and_needs_human_decision(migrated_db, tmp_path):
    async def go():
        risky, ok = Risky(), Instant()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": risky, "reporter": ok})
        pid = make_project(env)
        r = add_task(env, pid, title="Berisiko")
        await pause_with_running(env, ctl, risky)
        other = add_task(env, pid, title="Lain", role="reporter", action_type="documentation")
        risky.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        st = pstate(env)
        assert st.state == RECOVERY_REQUIRED and power.scheduling_allowed(st)   # tugas lain boleh jalan
        assert get(env, r).status == "interrupted" and risky.runs == 1
        items = rows(env, RecoveryItem, RecoveryItem.status == "open")
        assert [i.kind for i in items] == ["risky_task_interrupted"]
        assert await env.worker.run_once() is True and get(env, other).status == "completed"
        assert await env.worker.run_once() is False and risky.runs == 1
        with env.sf() as s:                                      # CEO memutuskan: requeue -> sistem kembali RUNNING penuh
            ctl.recovery.resolve_item(s, items[0].id, "requeue")
            s.commit()
        assert pstate(env).state == RUNNING and get(env, r).status == "queued"
    asyncio.run(go())


def test_resolve_cancel_and_unknown_resolution(migrated_db, tmp_path):
    async def go():
        risky = Risky()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": risky})
        r = add_task(env, make_project(env))
        await pause_with_running(env, ctl, risky)
        risky.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        item = rows(env, RecoveryItem)[0]
        with env.sf() as s:
            with pytest.raises(PowerError):
                ctl.recovery.resolve_item(s, item.id, "ngawur")
            ctl.recovery.resolve_item(s, item.id, "cancel")
            s.commit()
            with pytest.raises(PowerError):
                ctl.recovery.resolve_item(s, item.id, "cancel")
        assert get(env, r).status == "cancelled" and pstate(env).state == RUNNING
    asyncio.run(go())


# ------------------------------------------------------------------ checkpoint

def test_checkpoint_roundtrip_integrity_and_tamper_detection(migrated_db, tmp_path):
    env, ctl = make(migrated_db, tmp_path)
    tid = add_task(env, make_project(env))
    cid = env.worker.checkpoints.create(tid, None, "pause", "uji", strict=True)
    with env.sf() as s:
        cp = s.get(TaskCheckpoint, cid)
        assert env.worker.checkpoints.validate(s, cp)["valid"] is True
        assert cp.payload["task"]["id"] == tid and cp.schema_version == 1 and len(cp.payload_sha256) == 64
        cp.payload = {**cp.payload, "retry": {"attempt_count": 99, "max_retries": 2, "attempts_baseline": 0}}
        res = env.worker.checkpoints.validate(s, cp)
        assert res["valid"] is False and res["problems"][0]["kind"] == "hash_mismatch"


def test_resume_prefers_older_valid_checkpoint_when_latest_is_corrupt(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        tid = add_task(env, make_project(env))
        good = env.worker.checkpoints.create(tid, None, "periodic", "bagus", strict=True)
        await pause_with_running(env, ctl, ex)
        with env.sf() as s:                                      # rusakkan semua checkpoint kecuali yang bagus
            for cp in s.scalars(select(TaskCheckpoint).where(TaskCheckpoint.task_id == tid, TaskCheckpoint.id != good)):
                cp.payload_sha256 = "0" * 64
            s.commit()
        ex.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        log = rows(env, RecoveryLog, RecoveryLog.task_id == tid)
        assert "checkpoint_invalid" in [r.action for r in log]
        assert [r.checkpoint_id for r in log if r.action == "resumed_from_checkpoint"] == [good]
    asyncio.run(go())


def test_all_checkpoints_invalid_falls_back_to_retry_and_is_logged(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        tid = add_task(env, make_project(env))
        await pause_with_running(env, ctl, ex)
        with env.sf() as s:
            for cp in s.scalars(select(TaskCheckpoint).where(TaskCheckpoint.task_id == tid)):
                cp.payload_sha256 = "0" * 64
            s.commit()
        ex.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        actions = [r.action for r in rows(env, RecoveryLog, RecoveryLog.task_id == tid)]
        assert "checkpoint_invalid" in actions and "retry_without_valid_checkpoint" in actions
        assert get(env, tid).status == "queued"
    asyncio.run(go())


def test_uncommitted_git_changes_survive_pause_and_resume_and_are_recorded(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        pid = make_project(env)
        tid = add_task(env, pid)
        root = env.worker.checkpoints.workspace_root(pid)
        workspace_git.ensure_repo(root)
        (root / "app.py").write_text("print('v1')\n", encoding="utf-8")
        workspace_git.commit_all(root, "awal")
        (root / "app.py").write_text("print('belum di-commit')\n", encoding="utf-8")   # perubahan pengguna
        (root / "baru.py").write_text("x = 1\n", encoding="utf-8")                      # berkas baru tak terlacak
        head = workspace_git.head(root)
        await pause_with_running(env, ctl, ex)
        cp = rows(env, TaskCheckpoint, TaskCheckpoint.task_id == tid, TaskCheckpoint.kind == "pause")[0]
        assert cp.payload["git"]["dirty"] is True and cp.payload["git"]["head"] == head
        assert {f["path"] for f in cp.payload["files"]} >= {"app.py", "baru.py"}
        ex.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        assert (root / "app.py").read_text(encoding="utf-8") == "print('belum di-commit')\n"   # tidak di-reset
        assert (root / "baru.py").exists() and workspace_git.head(root) == head                # tidak ada commit otomatis
        assert workspace_git.status(root)
    asyncio.run(go())


def test_changed_file_is_a_warning_but_missing_file_is_a_problem(migrated_db, tmp_path):
    env, ctl = make(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid)
    root = env.worker.checkpoints.workspace_root(pid)
    workspace_git.ensure_repo(root)
    (root / "a.py").write_text("1\n", encoding="utf-8")
    cid = env.worker.checkpoints.create(tid, None, "pause", "uji", strict=True)
    (root / "a.py").write_text("2\n", encoding="utf-8")
    with env.sf() as s:
        res = env.worker.checkpoints.validate(s, s.get(TaskCheckpoint, cid))
        assert res["valid"] is True and any("a.py" in w for w in res["warnings"])
    (root / "a.py").unlink()
    with env.sf() as s:
        res = env.worker.checkpoints.validate(s, s.get(TaskCheckpoint, cid))
        assert res["valid"] is False and res["problems"][0]["kind"] == "files_missing"


def test_missing_files_at_resume_require_manual_decision(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        pid = make_project(env)
        tid = add_task(env, pid)
        root = env.worker.checkpoints.workspace_root(pid)
        workspace_git.ensure_repo(root)
        (root / "penting.py").write_text("x\n", encoding="utf-8")
        await pause_with_running(env, ctl, ex)
        (root / "penting.py").unlink()
        ex.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        assert get(env, tid).status == "interrupted"
        assert [i.kind for i in rows(env, RecoveryItem, RecoveryItem.status == "open")] == ["files_missing"]
        assert pstate(env).state == RECOVERY_REQUIRED
    asyncio.run(go())


def test_checkpoint_contains_no_secrets(migrated_db, tmp_path):
    env, ctl = make(migrated_db, tmp_path)
    secret = env.settings.app_local_token
    tid = add_task(env, make_project(env), title=f"Gunakan {secret} untuk akses")
    cid = env.worker.checkpoints.create(tid, None, "pause", f"langkah {secret}", strict=True)
    with env.sf() as s:
        cp = s.get(TaskCheckpoint, cid)
        blob = json.dumps(cp.payload) + (cp.last_step or "")
    assert secret not in blob and "[REDACTED]" in blob


def test_usage_and_cost_in_checkpoint_match_ledger_and_ledger_is_untouched(migrated_db, tmp_path):
    async def go():
        ex = Gate()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        tid = add_task(env, make_project(env))
        runner = asyncio.create_task(env.worker.run_once())
        await asyncio.wait_for(ex.started.wait(), 5)
        with env.sf() as s:
            att = s.scalar(select(TaskAttempt.id).where(TaskAttempt.task_id == tid))
            s.add(ModelUsage(provider="ollama", model="m", status="ok", request_id=att, prompt_tokens=11, completion_tokens=7, cost_idr=0.0))
            s.commit()
        await ctl.request_off(); await ctl.wait_idle(); await asyncio.wait_for(runner, 5)
        cp = rows(env, TaskCheckpoint, TaskCheckpoint.task_id == tid, TaskCheckpoint.kind == "pause")[0]
        assert cp.payload["usage"] == {"calls": 1, "prompt_tokens": 11, "completion_tokens": 7, "cost_idr": 0.0}
        before = len(rows(env, ModelUsage))
        ex.release.set()
        await ctl.request_on(); await ctl.wait_idle()
        assert len(rows(env, ModelUsage)) == before                # pause/resume tidak menambah atau mengubah catatan
        assert env.settings.budget_allow_paid_calls is False       # resume tidak pernah mengubah kebijakan budget
    asyncio.run(go())


def test_periodic_and_end_checkpoints_are_written_during_a_run_and_pruned(migrated_db, tmp_path):
    async def go():
        provider = FakeProvider(delay=0.6)
        env, ctl = make(migrated_db, tmp_path, provider=provider, power_checkpoint_interval_s=0.1, power_checkpoint_keep=3)
        tid = add_task(env, make_project(env))
        await env.worker.run_once()
        cps = rows(env, TaskCheckpoint, TaskCheckpoint.task_id == tid)
        assert len(cps) <= 3                                        # pemangkasan
        assert "end" in {c.kind for c in cps}
        assert {c.kind for c in cps} <= {"start", "periodic", "end"}
    asyncio.run(go())


# ------------------------------------------------------------------ crash dan startup

def test_startup_recovery_after_crash_requeues_from_last_valid_checkpoint(migrated_db, tmp_path):
    env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
    tid = add_task(env, make_project(env))
    with env.sf() as s:                                          # simulasi proses mati di tengah eksekusi
        t = s.get(Task, tid)
        t.attempt_count, t.status = 1, "running"
        s.add(TaskAttempt(task_id=tid, number=1))
        st = power.get_state(s)
        st.shutdown_clean = False
        s.commit()
    cid = env.worker.checkpoints.create(tid, None, "periodic", "sebelum_crash", strict=True)
    out = ctl.startup_recovery()
    assert out["unclean_shutdown"] and out["orphans_interrupted"] == 1 and out["requeued"] == 1 and out["state"] == RUNNING
    t = get(env, tid)
    assert t.status == "queued"
    assert [a.status for a in rows(env, TaskAttempt, TaskAttempt.task_id == tid)] == ["interrupted"]
    log = rows(env, RecoveryLog, RecoveryLog.task_id == tid)
    assert log[0].action == "resumed_from_checkpoint" and log[0].checkpoint_id == cid and log[0].source == "startup_crash"
    assert pstate(env).state == RUNNING and pstate(env).shutdown_clean is False
    ctl.mark_shutdown_clean()
    assert pstate(env).shutdown_clean is True
    assert ctl.startup_recovery()["unclean_shutdown"] is False       # restart bersih tidak memicu pemulihan


def test_crash_while_pausing_ends_up_paused(migrated_db, tmp_path):
    env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
    tid = add_task(env, make_project(env))
    with env.sf() as s:
        t = s.get(Task, tid)
        t.attempt_count, t.status = 1, "running"
        s.add(TaskAttempt(task_id=tid, number=1))
        power.set_state(s, PAUSING, reason="uji", force=True)
        s.commit()
    out = ctl.startup_recovery()
    assert out["incomplete_command"] and pstate(env).state == PAUSED
    assert get(env, tid).status == "queued"                          # dipulihkan tetapi tidak berjalan (scheduler mati)
    assert not ctl.can_schedule()


def test_crash_while_resuming_ends_up_running(migrated_db, tmp_path):
    env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
    with env.sf() as s:
        power.set_state(s, RESUMING, reason="uji", force=True)
        s.commit()
    assert ctl.startup_recovery()["state"] == RUNNING and ctl.can_schedule()


def test_paused_state_survives_restart_and_scheduler_stays_off(migrated_db, tmp_path):
    async def go():
        ex = Instant()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        add_task(env, make_project(env))
        await ctl.request_off(); await ctl.wait_idle()
        ctl.mark_shutdown_clean()
        env2, ctl2 = make(migrated_db, tmp_path, executors={"analyst": ex})   # proses baru, database sama
        assert ctl2.startup_recovery()["previous_state"] == PAUSED
        assert pstate(env2).state == PAUSED and await env2.worker.run_once() is False and ex.runs == 0
        await ctl2.request_on(); await ctl2.wait_idle()
        assert await env2.worker.run_once() is True and ex.runs == 1
    asyncio.run(go())


def test_clean_restart_requeues_tasks_interrupted_by_shutdown(migrated_db, tmp_path):
    env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
    tid = add_task(env, make_project(env))
    with env.sf() as s:
        from app.tasks.state import change_status
        t = s.get(Task, tid)
        t.attempt_count = 1
        change_status(s, t, "running")
        change_status(s, t, "interrupted", reason="shutdown")
        s.commit()
    out = ctl.startup_recovery()
    assert out["requeued"] == 1 and get(env, tid).status == "queued"


# ------------------------------------------------------------------ operasi eksternal

def test_external_operation_is_idempotent_and_uncertain_ones_block_the_task(migrated_db, tmp_path):
    async def go():
        ex = Instant()
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": ex})
        pid = make_project(env)
        blocked = add_task(env, pid, title="Kirim")
        other = add_task(env, pid, title="Lain")
        with env.sf() as s:
            op, created = external.begin_operation(s, kind="outreach", key="outreach:x:1", task_id=blocked, payload_sha256="abc")
            again, created2 = external.begin_operation(s, kind="outreach", key="outreach:x:1", task_id=blocked)
            assert created and not created2 and again.id == op.id and op.status == "started"
            power.set_state(s, PAUSED, reason="uji", force=True)
            s.commit()
        await ctl.request_on(); await ctl.wait_idle()
        assert get(env, blocked).status == "blocked" and get(env, blocked).blocked_reason == "external_unknown"
        assert [i.kind for i in rows(env, RecoveryItem, RecoveryItem.status == "open")] == ["external_unknown"]
        assert rows(env, ExternalOperation)[0].status == "unknown"
        assert pstate(env).state == RECOVERY_REQUIRED
        assert await env.worker.run_once() is True and get(env, other).status == "completed"   # task lain tetap jalan
        assert await env.worker.run_once() is False and ex.runs == 1                          # task terblokir tidak diulang
    asyncio.run(go())


def test_confirmed_external_operations_are_not_flagged(migrated_db, tmp_path):
    async def go():
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
        tid = add_task(env, make_project(env))
        with env.sf() as s:
            op, _ = external.begin_operation(s, kind="publish", key="publish:x:1", task_id=tid)
            external.finish_operation(op, "confirmed", {"outbound_message_id": "m1"})
            s.commit()
        await ctl.request_off(); await ctl.wait_idle()
        await ctl.request_on(); await ctl.wait_idle()
        assert pstate(env).state == RUNNING and not rows(env, RecoveryItem)
    asyncio.run(go())


def test_marketing_enqueue_records_operation_and_repeat_returns_same_message(migrated_db, tmp_path):
    from app.marketing import external as mk_ext
    env, _ = make(migrated_db, tmp_path)
    with env.sf() as s:
        op, msg = mk_ext._begin_external(s, "outreach", "t1", "h1")
        assert msg is None and op.status == "started"
        external.finish_operation(op, "confirmed", {"outbound_message_id": "tidak-ada"})
        s.flush()
        op2, msg2 = mk_ext._begin_external(s, "outreach", "t1", "h1")     # pesan tidak ditemukan -> boleh lanjut, tetap satu operasi
        assert op2.id == op.id
        op.status = "unknown"
        with pytest.raises(mk_ext.MarketingError):
            mk_ext._begin_external(s, "outreach", "t1", "h1")


# ------------------------------------------------------------------ status global

def test_scheduling_matrix_and_transitions():
    class S:
        def __init__(self, state, detail=None):
            self.state, self.detail = state, detail
    assert power.scheduling_allowed(None) and power.scheduling_allowed(S(RUNNING))
    assert not any(power.scheduling_allowed(S(x)) for x in (PAUSING, PAUSED, RESUMING, power.ERROR))
    assert power.scheduling_allowed(S(RECOVERY_REQUIRED, {"scheduling": True}))
    assert not power.scheduling_allowed(S(RECOVERY_REQUIRED, {"scheduling": False}))
    assert not power.scheduling_allowed(S(RECOVERY_REQUIRED))


def test_invalid_transition_is_rejected(migrated_db, tmp_path):
    env, _ = make(migrated_db, tmp_path)
    with env.sf() as s:
        power.get_state(s)
        with pytest.raises(PowerError):
            power.set_state(s, PAUSED, reason="langsung")          # RUNNING -> PAUSED tidak boleh


def test_state_changes_emit_events_and_audit(migrated_db, tmp_path):
    async def go():
        env, ctl = make(migrated_db, tmp_path, executors={"analyst": Instant()})
        await ctl.request_off(); await ctl.wait_idle()
        evs = rows(env, TaskEvent, TaskEvent.task_id == power.SYSTEM_ENTITY)
        types = [e.type for e in evs]
        assert "power.state_changed" in types and "power.progress" in types
        tos = [e.payload["to"] for e in evs if e.type == "power.state_changed"]
        assert tos == [PAUSING, PAUSED]
        from app.db.models import AuditLog
        acts = [a.action for a in rows(env, AuditLog, AuditLog.entity_type.in_(["power", "power_command"]))]
        assert "power.off_requested" in acts and "power.state_changed" in acts
    asyncio.run(go())


# ------------------------------------------------------------------ API

def _wait_state(c, auth, want, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        st = c.get("/api/power", headers=auth).json()
        if st["state"] == want:
            return st
        time.sleep(0.1)
    raise AssertionError(f"status tidak menjadi {want}: {st['state']}")


def test_api_off_on_flow_with_progress_commands_and_events(settings, auth):
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/power", headers=auth).json()["state"] == "RUNNING"
        r = c.post("/api/power/off", headers=auth)
        assert r.status_code == 202 and r.json()["accepted"] and r.json()["state"] == "PAUSING"
        st = _wait_state(c, auth, "PAUSED")
        assert st["scheduling"] is False and st["active_command"]["status"] == "completed"
        assert [p["step"] for p in st["active_command"]["progress"]][0] == "scheduler_stopped"
        again = c.post("/api/power/off", headers=auth)
        assert again.status_code == 200 and again.json()["already"] is True
        on = c.post("/api/power/on", headers=auth)
        assert on.status_code == 202
        st = _wait_state(c, auth, "RUNNING")
        assert st["counts"]["running"] == 0 and st["recovery_required"] == 0
        cmds = c.get("/api/power/commands", headers=auth).json()
        assert [x["action"] for x in cmds][:2] == ["on", "off"]
        assert c.get(f"/api/power/commands/{cmds[0]['id']}", headers=auth).json()["status"] == "completed"
        assert c.get("/api/power/commands/tidak-ada", headers=auth).status_code == 404
        events = c.get("/api/events?since=0&limit=200", headers=auth).json()
        assert any(e["type"] == "power.state_changed" for e in events)


def test_api_conflicts_and_recovery_endpoints(settings, auth):
    with TestClient(create_app(settings)) as c:
        sf = c.app.state.session_factory
        with sf() as s:
            power.set_state(s, PAUSING, reason="uji", force=True)
            s.commit()
        assert c.post("/api/power/on", headers=auth).status_code == 409
        with sf() as s:
            power.set_state(s, RESUMING, reason="uji", force=True)
            s.commit()
        assert c.post("/api/power/off", headers=auth).status_code == 409
        with sf() as s:
            power.set_state(s, RUNNING, reason="uji", force=True)
            it = RecoveryItem(kind="risky_task_interrupted", reason="uji")
            s.add(it)
            s.commit()
            iid = it.id
        assert [i["id"] for i in c.get("/api/power/recovery", headers=auth).json()] == [iid]
        assert c.post(f"/api/power/recovery/{iid}/resolve", json={"resolution": "ngawur"}, headers=auth).status_code == 422
        ok = c.post(f"/api/power/recovery/{iid}/resolve", json={"resolution": "acknowledged"}, headers=auth)
        assert ok.status_code == 200 and ok.json()["status"] == "resolved"
        assert c.post(f"/api/power/recovery/{iid}/resolve", json={"resolution": "acknowledged"}, headers=auth).status_code == 409
        assert c.post("/api/power/recovery/tidak-ada/resolve", json={"resolution": "cancel"}, headers=auth).status_code == 404
        assert c.get("/api/power/recovery?scope=all", headers=auth).json()[0]["resolution"] == "acknowledged"
        assert c.get("/api/power/recovery/log", headers=auth).status_code == 200


def test_api_checkpoints_listing_and_dashboard_includes_power(settings, auth):
    with TestClient(create_app(settings)) as c:
        pid = c.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]
        tid = c.post("/api/tasks", headers=auth, json={"project_id": pid, "title": "T", "role": "analyst", "action_type": "analysis"}).json()["id"]
        cid = c.app.state.power.checkpoints.create(tid, None, "pause", "uji", strict=True)
        rows_ = c.get(f"/api/power/tasks/{tid}/checkpoints", headers=auth).json()
        assert [r["id"] for r in rows_] == [cid] and rows_[0]["kind"] == "pause"
        assert c.get(f"/api/power/checkpoints?task_id={tid}", headers=auth).json()[0]["id"] == cid
        dash = c.get("/api/dashboard", headers=auth).json()
        assert dash["power"]["state"] == "RUNNING" and dash["power"]["checkpoints_saved"] == 1


def test_api_paused_state_persists_across_app_restart(settings, auth):
    with TestClient(create_app(settings)) as c:
        c.post("/api/power/off", headers=auth)
        _wait_state(c, auth, "PAUSED")
    with TestClient(create_app(settings)) as c2:                       # proses baru, database sama
        st = c2.get("/api/power", headers=auth).json()
        assert st["state"] == "PAUSED" and st["scheduling"] is False
        assert c2.app.state.power_startup["previous_state"] == "PAUSED"
        c2.post("/api/power/on", headers=auth)
        _wait_state(c2, auth, "RUNNING")


def test_api_unclean_shutdown_is_detected_on_next_start(settings, auth):
    with TestClient(create_app(settings)) as c:
        pid = c.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]
        tid = c.post("/api/tasks", headers=auth, json={"project_id": pid, "title": "T", "role": "analyst", "action_type": "analysis"}).json()["id"]
        cid = c.app.state.power.checkpoints.create(tid, None, "periodic", "sebelum_crash", strict=True)
        sf = c.app.state.session_factory
    with sf() as s:                                                  # setelah shutdown bersih: seolah proses lain mati saat task berjalan
        t = s.get(Task, tid)
        t.attempt_count, t.status = 1, "running"
        s.add(TaskAttempt(task_id=tid, number=1))
        power.get_state(s).shutdown_clean = False
        s.commit()
    with TestClient(create_app(settings)) as c2:
        start = c2.app.state.power_startup
        assert start["unclean_shutdown"] is True and start["requeued"] == 1
        assert c2.get(f"/api/tasks/{tid}", headers=auth).json()["status"] == "queued"
        log = c2.get("/api/power/recovery/log", headers=auth).json()
        assert [r["checkpoint_id"] for r in log if r["action"] == "resumed_from_checkpoint"] == [cid]
