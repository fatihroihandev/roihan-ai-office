from datetime import timedelta

import pytest
from sqlalchemy import select

from app.approvals import service as approvals
from app.approvals.service import ApprovalError
from app.db.base import utcnow
from app.db.models import Approval, AuditLog, Task, TaskEvent
from app.tasks import service
from app.tasks.executors import ExecutorError, ExecutorOutcome
from tests.helpers import add_task, build_env, drain, get, make_project, run


class Recorder:
    """Executor uji: mencatat setiap eksekusi sehingga terlihat apakah tindakan berisiko benar-benar dijalankan."""
    idempotent = True

    def __init__(self, error=None):
        self.runs, self.error = [], error

    async def run(self, ctx):
        self.runs.append(ctx.task.id)
        if self.error:
            raise self.error
        return ExecutorOutcome("ok", True, {"method": "uji", "passed": True}, {"output": "ok"})


@pytest.fixture
def env(migrated_db, tmp_path):
    rec = Recorder()
    e = build_env(migrated_db, tmp_path, executors={"analyst": rec})
    e.rec = rec
    return e


def risky(env, pid, **kw):
    """Task berisiko kritis (spend) yang dikerjakan role analyst, sehingga eksekusinya dapat diamati."""
    return add_task(env, pid, title="Bayar vendor", role="analyst", action_type="spend", description="Bayar Rp1 juta", **kw)


def approval_of(env, tid, status=None):
    with env.sf() as s:
        q = select(Approval).where(Approval.task_id == tid).order_by(Approval.created_at)
        rows = list(s.scalars(q))
        return [a for a in rows if status is None or a.status == status]


def decide(env, tid, decision, actor="ceo", reason=None):
    with env.sf() as s:
        ap = s.scalars(select(Approval).where(Approval.task_id == tid, Approval.status == "pending")).first()
        try:
            approvals.decide(s, ap, decision, actor, reason)
        finally:
            s.commit()


def test_risky_task_creates_a_pending_approval_bound_to_its_content(env):
    pid = make_project(env)
    tid = risky(env, pid)
    assert get(env, tid).status == "pending_approval"
    [ap] = approval_of(env, tid)
    assert (ap.status, ap.risk_level, ap.action_type, ap.requested_by, ap.kind) == ("pending", "critical", "spend", "system", "task_execution")
    assert ap.payload["title"] == "Bayar vendor" and ap.payload["description"] == "Bayar Rp1 juta" and len(ap.payload_hash) == 64
    assert timedelta(hours=23) < ap.expires_at.replace(tzinfo=None) - utcnow().replace(tzinfo=None) <= timedelta(hours=24)
    with env.sf() as s:
        ev = s.scalars(select(TaskEvent).where(TaskEvent.task_id == tid, TaskEvent.type == "approval.required")).one()
        assert ev.payload["approval_id"] == ap.id and ev.payload["risk_level"] == "critical"


def test_nothing_runs_while_approval_is_pending(env):
    pid = make_project(env)
    risky(env, pid)
    assert drain(env) == 0 and env.rec.runs == []


def test_ceo_approval_lets_the_task_run_and_is_audited(env):
    pid = make_project(env)
    tid = risky(env, pid)
    decide(env, tid, "approved", reason="vendor sudah diverifikasi")
    [ap] = approval_of(env, tid)
    assert (ap.status, ap.decided_by, ap.decision_reason) == ("approved", "ceo", "vendor sudah diverifikasi") and ap.decided_at
    assert get(env, tid).status == "queued"
    drain(env)
    assert env.rec.runs == [tid] and get(env, tid).status == "completed"
    with env.sf() as s:
        log = s.scalars(select(AuditLog).where(AuditLog.entity_id == ap.id)).one()
        assert (log.actor, log.action, log.details["task_id"], log.details["reason"]) == ("ceo", "approval.approve", tid, "vendor sudah diverifikasi")
        assert s.scalars(select(TaskEvent).where(TaskEvent.task_id == tid, TaskEvent.type == "approval.resolved")).one().payload["status"] == "approved"


def test_approval_is_single_use_and_does_not_stick_to_the_task(env):
    pid = make_project(env)
    tid = risky(env, pid)
    decide(env, tid, "approved")
    drain(env)
    [ap] = approval_of(env, tid)
    assert ap.used_at is not None and get(env, tid).approved is False
    with env.sf() as s:
        assert approvals.valid_for_execution(s, s.get(Task, tid)) is None            # sudah terpakai


def test_manual_retry_of_a_risky_task_needs_a_fresh_approval(env):
    env.rec.error = ExecutorError("boom", "gagal", retryable=False)
    pid = make_project(env)
    tid = risky(env, pid)
    decide(env, tid, "approved")
    drain(env)
    assert get(env, tid).status == "failed" and len(env.rec.runs) == 1
    with env.sf() as s:
        service.requeue_task(s, s.get(Task, tid))
        s.commit()
    assert get(env, tid).status == "pending_approval"                                # BUKAN queued
    assert drain(env) == 0 and len(env.rec.runs) == 1                                # tidak berjalan lagi
    assert [a.status for a in approval_of(env, tid)] == ["approved", "pending"]
    decide(env, tid, "approved")
    env.rec.error = None
    drain(env)
    assert len(env.rec.runs) == 2 and get(env, tid).status == "completed"


def test_risky_tasks_are_never_retried_automatically(env):
    env.rec.error = ExecutorError("sementara", "gagal sementara", retryable=True)     # biasanya memicu retry otomatis
    pid = make_project(env)
    tid = risky(env, pid)
    decide(env, tid, "approved")
    drain(env)
    t = get(env, tid)
    assert (t.status, t.attempt_count, len(env.rec.runs)) == ("failed", 1, 1)


def test_non_risky_tasks_still_retry_automatically(migrated_db, tmp_path):
    rec = Recorder(ExecutorError("sementara", "gagal sementara", retryable=True))
    env = build_env(migrated_db, tmp_path, executors={"analyst": rec})
    pid = make_project(env)
    tid = add_task(env, pid, role="analyst", action_type="analysis")
    drain(env)
    assert get(env, tid).attempt_count == 3


def test_rejection_cancels_the_task_and_blocks_dependents(env):
    pid = make_project(env)
    tid = risky(env, pid)
    after = add_task(env, pid, title="Lanjutan", role="analyst", action_type="analysis", depends_on=[tid])
    decide(env, tid, "rejected", reason="terlalu mahal")
    [ap] = approval_of(env, tid)
    assert (ap.status, ap.decision_reason) == ("rejected", "terlalu mahal")
    t = get(env, tid)
    assert (t.status, t.finished_at is not None) == ("cancelled", True)
    drain(env)
    assert env.rec.runs == [] and get(env, after).status == "blocked"


@pytest.mark.parametrize("actor", ["manager", "analyst", "developer", "reviewer", "system", "worker", "ai", "agent", "CEO", "", "ceo "])
def test_agents_and_system_can_never_approve_or_reject(env, actor):
    pid = make_project(env)
    tid = risky(env, pid)
    for decision in ("approved", "rejected"):
        with pytest.raises(ApprovalError) as e:
            decide(env, tid, decision, actor=actor)
        assert e.value.code == "agent_cannot_approve"
    assert get(env, tid).status == "pending_approval" and approval_of(env, tid)[0].status == "pending"
    with env.sf() as s:
        assert s.query(AuditLog).filter(AuditLog.action.like("approval.%")).count() == 0


def test_invalid_decision_value(env):
    pid = make_project(env)
    tid = risky(env, pid)
    with pytest.raises(ApprovalError) as e:
        decide(env, tid, "maybe")
    assert e.value.code == "invalid_decision"


def test_an_approval_cannot_be_decided_twice(env):
    pid = make_project(env)
    tid = risky(env, pid)
    ap_id = approval_of(env, tid)[0].id
    decide(env, tid, "approved")
    with env.sf() as s:
        with pytest.raises(ApprovalError) as e:
            approvals.decide(s, s.get(Approval, ap_id), "rejected", "ceo", "berubah pikiran")
        assert e.value.code == "not_pending"
    assert approval_of(env, tid)[0].status == "approved"


def test_unanswered_approvals_expire_and_cancel_the_task(env):
    pid = make_project(env)
    tid = risky(env, pid)
    with env.sf() as s:
        s.scalars(select(Approval)).first().expires_at = utcnow() - timedelta(seconds=1)
        s.commit()
    drain(env)
    [ap] = approval_of(env, tid)
    t = get(env, tid)
    assert ap.status == "expired" and t.status == "cancelled" and env.rec.runs == []
    with env.sf() as s:
        assert s.query(TaskEvent).filter_by(task_id=tid, type="approval.resolved").count() == 1


def test_deciding_an_expired_approval_is_refused_and_recorded(env):
    pid = make_project(env)
    tid = risky(env, pid)
    with env.sf() as s:
        s.scalars(select(Approval)).first().expires_at = utcnow() - timedelta(minutes=5)
        s.commit()
    with pytest.raises(ApprovalError) as e:
        decide(env, tid, "approved")
    assert e.value.code == "expired"
    assert approval_of(env, tid)[0].status == "expired" and get(env, tid).status == "cancelled"


def test_approval_is_void_if_the_task_content_changes_before_deciding(env):
    pid = make_project(env)
    tid = risky(env, pid)
    with env.sf() as s:
        s.get(Task, tid).description = "Bayar Rp100 juta"            # isi tindakan diubah setelah approval diminta
        s.commit()
    with pytest.raises(ApprovalError) as e:
        decide(env, tid, "approved")
    assert e.value.code == "payload_changed"
    assert approval_of(env, tid)[0].status == "cancelled" and get(env, tid).status == "pending_approval"
    drain(env)                                                          # worker meminta approval baru untuk isi yang baru
    assert [a.status for a in approval_of(env, tid)] == ["cancelled", "pending"]
    assert approval_of(env, tid)[1].payload["description"] == "Bayar Rp100 juta" and env.rec.runs == []


def test_approved_but_modified_task_does_not_run(env):
    pid = make_project(env)
    tid = risky(env, pid)
    decide(env, tid, "approved")
    with env.sf() as s:
        s.get(Task, tid).description = "Bayar Rp100 juta"             # diubah SETELAH disetujui
        s.commit()
    drain(env)
    assert env.rec.runs == [] and get(env, tid).status == "pending_approval"
    assert [a.status for a in approval_of(env, tid)] == ["approved", "pending"]   # persetujuan lama tidak berlaku


def test_approved_but_expired_before_start_asks_again(env):
    pid = make_project(env)
    tid = risky(env, pid)
    decide(env, tid, "approved")
    with env.sf() as s:
        s.scalars(select(Approval)).first().expires_at = utcnow() - timedelta(seconds=1)
        s.commit()
    drain(env)
    assert env.rec.runs == [] and get(env, tid).status == "pending_approval"
    assert approval_of(env, tid)[-1].status == "pending"


def test_approval_cannot_be_reused_for_a_different_task(env):
    pid = make_project(env)
    a, b = risky(env, pid), risky(env, pid)
    decide(env, a, "approved")
    with env.sf() as s:
        ap_a = s.scalars(select(Approval).where(Approval.task_id == a)).one()
        t_b = s.get(Task, b)
        assert approvals.valid_for_execution(s, t_b) is None
        t_b.status = "queued"                                           # memaksa b ke antrean tanpa approval miliknya
        s.commit()
        assert ap_a.task_id == a
    drain(env)
    assert b not in env.rec.runs and get(env, b).status == "pending_approval"


def test_recovery_never_requeues_risky_interrupted_tasks(env):
    pid = make_project(env)
    tid = risky(env, pid)
    decide(env, tid, "approved")
    with env.sf() as s:                                                 # proses mati ketika tindakan berisiko sedang berjalan
        t = s.get(Task, tid)
        t.attempt_count, t.status = 1, "running"
        s.commit()
    env.worker.recover()
    assert get(env, tid).status == "interrupted"
    assert drain(env) == 0 and env.rec.runs == []


def test_cancelling_a_task_cancels_its_open_approval(env):
    pid = make_project(env)
    tid = risky(env, pid)
    with env.sf() as s:
        service.cancel_task(s, s.get(Task, tid))
        s.commit()
    assert [a.status for a in approval_of(env, tid)] == ["cancelled"] and get(env, tid).status == "cancelled"


def test_open_approval_is_idempotent_and_legacy_tasks_get_one(env):
    pid = make_project(env)
    tid = risky(env, pid)
    with env.sf() as s:
        t = s.get(Task, tid)
        assert approvals.open_approval(s, t).id == approvals.open_approval(s, t).id
        s.commit()
    assert len(approval_of(env, tid)) == 1
    legacy = add_task(env, pid, title="Lama", role="analyst", action_type="spend", queue=False)
    with env.sf() as s:                                                 # task pending_approval dari fase sebelumnya (tanpa approval)
        s.get(Task, legacy).status = "pending_approval"
        s.commit()
    drain(env)
    assert [a.status for a in approval_of(env, legacy)] == ["pending"]


def test_every_risk_level_follows_the_policy(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, executors={"analyst": Recorder()})
    pid = make_project(env)
    expected = {"analysis": "queued", "documentation": "queued", "code_change": "queued", "run_tests": "queued",
                "install_dependency": "pending_approval", "delete_data": "pending_approval", "security_config": "pending_approval",
                "network_access": "pending_approval", "external_outreach": "pending_approval", "publish": "pending_approval",
                "paid_api": "pending_approval", "spend": "pending_approval", "change_pricing": "pending_approval",
                "use_credentials": "pending_approval"}
    for action, status in expected.items():
        tid = add_task(env, pid, title=action, role="analyst", action_type=action)
        assert get(env, tid).status == status, action
        assert bool(approval_of(env, tid)) == (status == "pending_approval"), action
