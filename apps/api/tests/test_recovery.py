"""Uji ketahanan Fase 11: proses mati di tengah kerja, restart berulang, dan pemulihan dari cadangan."""
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.backup import service as svc
from app.db.models import Task, TaskAttempt
from app.main import create_app
from tests.helpers import add_task, build_env, drain, get, make_project


def _crash(env, tid):
    """Simulasi proses mati di tengah eksekusi: task `running` dengan percobaan yang belum selesai."""
    with env.sf() as s:
        t = s.get(Task, tid)
        t.attempt_count, t.status = 1, "running"
        s.add(TaskAttempt(task_id=tid, number=1))
        s.commit()


def test_repeated_restarts_are_idempotent(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = add_task(env, make_project(env))
    _crash(env, tid)
    assert env.worker.recover() == 1
    assert env.worker.recover() == 0          # restart kedua tidak mengubah apa pun
    assert get(env, tid).status == "queued"
    drain(env)
    assert get(env, tid).status == "completed"
    assert env.worker.recover() == 0          # task selesai tidak pernah dijalankan ulang
    assert drain(env) == 0


def test_chain_resumes_in_order_after_crash(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    a = add_task(env, pid, title="A")
    b = add_task(env, pid, title="B", role="reporter", action_type="documentation", depends_on=[a])
    _crash(env, a)
    env.worker.recover()
    assert drain(env) == 2
    assert [get(env, x).status for x in (a, b)] == ["completed", "completed"]


def test_completed_work_is_never_repeated_after_restart(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    done = add_task(env, pid, title="Selesai")
    drain(env)
    calls = len(env.provider.calls)
    restarted = build_env(migrated_db, tmp_path)   # proses baru, database yang sama
    assert restarted.worker.recover() == 0 and drain(restarted) == 0
    assert len(env.provider.calls) == calls and get(restarted, done).status == "completed"


def test_risky_task_interrupted_by_crash_is_not_rerun_and_blocks_dependents(migrated_db, tmp_path):
    class Risky:
        idempotent = False

        async def run(self, ctx):
            raise AssertionError("tidak boleh dijalankan ulang otomatis")

    env = build_env(migrated_db, tmp_path, executors={"analyst": Risky(), "reporter": Risky()})
    pid = make_project(env)
    a = add_task(env, pid, title="A")
    b = add_task(env, pid, title="B", role="reporter", action_type="documentation", depends_on=[a])
    _crash(env, a)
    env.worker.recover()
    assert drain(env) == 0
    assert get(env, a).status == "interrupted"
    assert get(env, b).status in {"queued", "blocked"}   # tidak berjalan selama A belum selesai
    assert [x.status for x in env.sf().scalars(select(TaskAttempt).where(TaskAttempt.task_id == a))] == ["interrupted"]


def test_backup_taken_mid_task_restores_and_recovers(migrated_db, tmp_path):
    """Skenario bencana: cadangan diambil saat task berjalan, disk dipulihkan, worker menyelesaikan task."""
    env = build_env(migrated_db, tmp_path)
    tid = add_task(env, make_project(env))
    _crash(env, tid)
    db = Path(make_url(migrated_db).database)
    backups = tmp_path / "data" / "backups"
    b = svc.create_backup(db, backups, None)

    fresh_url = f"sqlite:///{(tmp_path / 'baru' / 'roihan.db').as_posix()}"
    fresh = Path(make_url(fresh_url).database)
    svc.restore_backup(b, fresh, backups, None)
    env2 = build_env(fresh_url, tmp_path / "w2")
    assert get(env2, tid).status == "running"
    assert env2.worker.recover() == 1
    drain(env2)
    assert get(env2, tid).status == "completed"


def test_data_survives_app_restart(settings, auth):
    c1 = TestClient(create_app(settings))
    pid = c1.post("/api/projects", json={"name": "Tahan restart"}, headers=auth).json()["id"]
    c2 = TestClient(create_app(settings))          # proses baru
    assert c2.get(f"/api/projects/{pid}", headers=auth).json()["name"] == "Tahan restart"


def test_database_copy_with_corrupted_header_is_not_silently_used(settings, tmp_path):
    db = Path(make_url(settings.database_url).database)
    b = svc.create_backup(db, tmp_path / "b", None)
    victim = tmp_path / "korup.db"
    shutil.copyfile(b / "roihan.db", victim)
    victim.write_bytes(b"BUKAN SQLITE" + victim.read_bytes()[12:])
    assert svc.integrity_ok(victim) is False
