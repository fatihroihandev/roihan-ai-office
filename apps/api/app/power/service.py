"""Office Power Control (Addendum v2.3, Bagian 29.A): status global, pause (OFF), resume (ON), dan pemulihan.

Backend/database adalah sumber kebenaran. `PAUSED` hanya diberikan setelah penghentian dan penyimpanan checkpoint TERVERIFIKASI.
OFF dan ON idempoten. Task `completed` tidak pernah dijalankan ulang; tindakan berisiko atau operasi eksternal yang hasilnya tidak
diketahui tidak pernah diulang otomatis (menjadi RecoveryItem untuk keputusan manusia).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.base import utcnow
from app.db.models import (
    AuditLog, ExternalOperation, PowerCommand, PowerState, RecoveryItem, RecoveryLog, Task, TaskAttempt, TaskCheckpoint, TaskEvent,
)
from app.power import external
from app.power.checkpoints import CheckpointManager
from app.tasks import service as task_service
from app.tasks.state import change_status

logger = logging.getLogger("roihan.power")

RUNNING, PAUSING, PAUSED, RESUMING, RECOVERY_REQUIRED, ERROR = "RUNNING", "PAUSING", "PAUSED", "RESUMING", "RECOVERY_REQUIRED", "ERROR"
STATES = [RUNNING, PAUSING, PAUSED, RESUMING, RECOVERY_REQUIRED, ERROR]
ALLOWED: dict[str, set[str]] = {
    RUNNING: {PAUSING, RECOVERY_REQUIRED, ERROR},
    PAUSING: {PAUSED, RECOVERY_REQUIRED, ERROR},
    PAUSED: {RESUMING, ERROR},
    RESUMING: {RUNNING, RECOVERY_REQUIRED, ERROR},
    RECOVERY_REQUIRED: {RUNNING, PAUSING, RESUMING, ERROR},
    ERROR: {PAUSING, RESUMING, RUNNING},
}
SYSTEM_ENTITY = "power"  # kanal event sistem pada tabel task_events (id task/proyek diisi "power")
LIVE_TASK_STATUSES = ["queued", "running", "blocked", "pending_approval", "interrupted"]


class PowerError(Exception):
    """Kesalahan operasi power yang pesannya aman ditampilkan; `code` dipetakan ke status HTTP oleh API."""

    def __init__(self, message: str, code: str = "conflict"):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------- status global

def get_state(s: Session) -> PowerState:
    st = s.get(PowerState, 1)
    if st is None:
        st = PowerState(id=1, state=RUNNING, shutdown_clean=True, changed_at=utcnow(), detail={})
        s.add(st)
        s.flush()
    return st


def scheduling_allowed(st: PowerState | None) -> bool:
    if st is None or st.state == RUNNING:
        return True
    return st.state == RECOVERY_REQUIRED and bool((st.detail or {}).get("scheduling"))


def emit(s: Session, type_: str, payload: dict, actor: str = "system") -> None:
    s.add(TaskEvent(task_id=SYSTEM_ENTITY, project_id=SYSTEM_ENTITY, type=type_, actor=actor, payload=payload))


def set_state(s: Session, new: str, *, reason: str, detail: dict | None = None, command_id: str | None = None, actor: str = "system",
              force: bool = False) -> PowerState:
    st = get_state(s)
    old = st.state
    if new != old and not force and new not in ALLOWED[old]:
        raise PowerError(f"Transisi status {old} -> {new} tidak diizinkan")
    st.state, st.reason = new, reason
    st.detail = dict(detail or {})
    if command_id is not None:
        st.active_command_id = command_id
    if new != old:
        st.changed_at = utcnow()
    payload = {"from": old, "to": new, "reason": reason, "command_id": st.active_command_id, "scheduling": scheduling_allowed(st)}
    emit(s, "power.state_changed", payload, actor)
    s.add(AuditLog(actor=actor, action="power.state_changed", entity_type="power", entity_id="1", details=payload))
    return st


def open_items(s: Session) -> list[RecoveryItem]:
    return list(s.scalars(select(RecoveryItem).where(RecoveryItem.status == "open").order_by(RecoveryItem.created_at)))


def snapshot(s: Session) -> dict:
    """Satu potret konsisten untuk UI: status, hitungan task, checkpoint, dan item yang butuh tindakan."""
    st = s.get(PowerState, 1)  # hanya membaca: potret tidak boleh menulis (belum ada baris = RUNNING bawaan)
    default = st is None
    counts = {k: v for k, v in s.execute(select(Task.status, func.count()).group_by(Task.status)).all()}
    live_projects = s.scalar(select(func.count(func.distinct(Task.project_id))).where(Task.status.in_(LIVE_TASK_STATUSES))) or 0
    items = open_items(s)
    last_cp = s.scalar(select(func.max(TaskCheckpoint.created_at)))
    cmd = s.get(PowerCommand, st.active_command_id) if (st and st.active_command_id) else None
    return {
        "state": RUNNING if default else st.state, "reason": None if default else st.reason,
        "changed_at": None if default else st.changed_at.isoformat(), "scheduling": scheduling_allowed(st),
        "detail": {} if default else (st.detail or {}), "active_command": _command_view(cmd) if cmd else None,
        "counts": {"projects_active": live_projects, "running": counts.get("running", 0), "queued": counts.get("queued", 0),
                   "completed": counts.get("completed", 0), "failed_or_blocked": counts.get("failed", 0) + counts.get("blocked", 0),
                   "interrupted": counts.get("interrupted", 0), "pending_approval": counts.get("pending_approval", 0)},
        "checkpoints_saved": s.scalar(select(func.count()).select_from(TaskCheckpoint)) or 0,
        "last_checkpoint_at": last_cp.isoformat() if last_cp else None,
        "recovery_required": len(items), "recovery_items": [item_view(i) for i in items[:20]],
    }


def _command_view(c: PowerCommand) -> dict:
    return {"id": c.id, "action": c.action, "status": c.status, "requested_by": c.requested_by, "created_at": c.created_at.isoformat(),
            "finished_at": c.finished_at.isoformat() if c.finished_at else None, "progress": c.progress, "result": c.result, "error": c.error}


def item_view(i: RecoveryItem) -> dict:
    return {"id": i.id, "task_id": i.task_id, "project_id": i.project_id, "kind": i.kind, "reason": i.reason, "detail": i.detail,
            "status": i.status, "created_at": i.created_at.isoformat(), "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
            "resolution": i.resolution}


# ---------------------------------------------------------------------- pemulihan

class RecoveryManager:
    def __init__(self, settings: Settings, session_factory, checkpoints: CheckpointManager, executors_fn: Callable[[], dict]):
        self._settings = settings
        self._sf = session_factory
        self._cp = checkpoints
        self._executors = executors_fn

    def _log(self, s: Session, command_id, source, action, task: Task | None = None, checkpoint_id=None, detail=None) -> None:
        s.add(RecoveryLog(command_id=command_id, source=source, task_id=task.id if task else None, project_id=task.project_id if task else None,
                          action=action, checkpoint_id=checkpoint_id, detail=detail))

    def _item(self, s: Session, task: Task | None, kind: str, reason: str, detail: dict | None = None) -> RecoveryItem | None:
        if task is not None:
            dup = s.scalar(select(RecoveryItem).where(RecoveryItem.task_id == task.id, RecoveryItem.kind == kind, RecoveryItem.status == "open"))
            if dup is not None:
                return dup
        it = RecoveryItem(task_id=task.id if task else None, project_id=task.project_id if task else None, kind=kind, reason=reason, detail=detail)
        s.add(it)
        s.flush()
        emit(s, "power.recovery_item", {"item_id": it.id, "kind": kind, "task_id": it.task_id})
        return it

    def interrupt_orphans(self, s: Session, reason: str, held: set[str] | None = None) -> int:
        """Task `running` di database yang tidak dipegang worker hidup: percobaan ditutup `interrupted`, task menjadi `interrupted`."""
        n = 0
        for t in s.scalars(select(Task).where(Task.status == "running")).all():
            if held and t.id in held:
                continue
            for a in s.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.status == "running")):
                a.status, a.finished_at, a.error_kind, a.retryable = "interrupted", utcnow(), "interrupted", True
            change_status(s, t, "interrupted", reason=reason)
            n += 1
        return n

    def _interrupt_reason(self, s: Session, t: Task) -> str | None:
        ev = s.scalar(select(TaskEvent).where(TaskEvent.task_id == t.id, TaskEvent.to_status == "interrupted").order_by(TaskEvent.seq.desc()).limit(1))
        return ev.reason if ev else None

    def check_external(self, s: Session, command_id, source) -> int:
        """Operasi eksternal yang hasilnya tidak pasti tidak diulang: tandai `unknown`, buat item, dan hentikan task terkait."""
        n = 0
        for op in external.uncertain_operations(s):
            op.status = "unknown"
            t = s.get(Task, op.task_id) if op.task_id else None
            self._item(s, t, "external_unknown", f"Operasi eksternal '{op.kind}' tidak diketahui hasilnya; verifikasi manual diperlukan sebelum diulang.",
                       {"operation_id": op.id, "kind": op.kind, "key": op.idempotency_key})
            if t is not None and t.status in {"queued", "running"}:
                if t.status == "running":
                    self.interrupt_orphans(s, "external_unknown", held=None)
                else:
                    change_status(s, t, "blocked", reason="external_unknown")
            self._log(s, command_id, source, "manual_required", t, detail={"operation_id": op.id, "reason": "external_unknown"})
            n += 1
        return n

    def recover_tasks(self, s: Session, command_id: str | None, source: str) -> dict:
        executors = self._executors()
        out = {"requeued": 0, "manual_required": 0, "checkpoint_invalid": 0}
        for t in s.scalars(select(Task).where(Task.status == "interrupted").order_by(Task.created_at, Task.id)).all():
            reason = self._interrupt_reason(s, t)
            cp, invalid = self._cp.latest_valid(s, t.id)
            for bad, res in invalid:
                out["checkpoint_invalid"] += 1
                self._log(s, command_id, source, "checkpoint_invalid", t, bad.id, {"problems": res["problems"]})
            ex = executors.get(t.role)
            if reason in {"paused"}:
                t.attempts_baseline += 1  # percobaan yang dihentikan karena OFF tidak mengurangi jatah retry
            retries_left = t.max_retries - (t.attempt_count - t.attempts_baseline - 1)
            if ex is None or not getattr(ex, "idempotent", False) or t.requires_approval:
                self._item(s, t, "risky_task_interrupted",
                           "Task berisiko/non-idempoten terputus; tidak diulang otomatis. Putuskan: ajukan approval baru (requeue), batalkan, atau konfirmasi hasil.",
                           {"role": t.role, "interrupt_reason": reason, "checkpoint_id": cp.id if cp else None})
                self._log(s, command_id, source, "manual_required", t, cp.id if cp else None, {"reason": "risky"})
                out["manual_required"] += 1
            elif cp is None and any(p["kind"] in {"files_missing", "git_missing", "git_history_changed"} for _, r in invalid for p in r["problems"]):
                kinds = sorted({p["kind"] for _, r in invalid for p in r["problems"]})
                self._item(s, t, "files_missing", "File atau riwayat Git proyek tidak sesuai checkpoint; periksa workspace sebelum melanjutkan.", {"problems": kinds})
                self._log(s, command_id, source, "manual_required", t, None, {"reason": "files_missing", "problems": kinds})
                out["manual_required"] += 1
            elif retries_left <= 0:
                self._item(s, t, "retries_exhausted", "Jatah retry otomatis habis; putuskan requeue atau batalkan.", {"interrupt_reason": reason})
                self._log(s, command_id, source, "manual_required", t, cp.id if cp else None, {"reason": "retries_exhausted"})
                out["manual_required"] += 1
            else:
                action = "resumed_from_checkpoint" if cp else ("retry_without_valid_checkpoint" if invalid else "retry_no_checkpoint")
                t.available_at = utcnow()
                change_status(s, t, "queued", reason="resumed", payload={"checkpoint_id": cp.id if cp else None, "source": source, "action": action})
                self._log(s, command_id, source, action, t, cp.id if cp else None,
                          {"warnings": (cp.validation or {}).get("warnings", []) if cp else [], "interrupt_reason": reason})
                out["requeued"] += 1
        counts = {k: v for k, v in s.execute(select(Task.status, func.count()).group_by(Task.status)).all()}
        if counts.get("completed"):
            self._log(s, command_id, source, "kept_completed", None, None, {"count": counts["completed"]})
        waiting = sum(counts.get(k, 0) for k in ("queued", "blocked", "pending_approval"))
        if waiting:
            self._log(s, command_id, source, "kept_waiting", None, None, {"count": waiting})
        return out

    def resolve_item(self, s: Session, item_id: str, resolution: str, actor: str = "ceo") -> RecoveryItem:
        it = s.get(RecoveryItem, item_id)
        if it is None:
            raise PowerError("Item pemulihan tidak ditemukan", "not_found")
        if it.status != "open":
            raise PowerError("Item pemulihan sudah diselesaikan")
        if resolution not in {"requeue", "cancel", "confirmed_done", "confirmed_not_done", "acknowledged"}:
            raise PowerError("Resolusi tidak dikenal", "invalid")
        t = s.get(Task, it.task_id) if it.task_id else None
        ops = list(s.scalars(select(ExternalOperation).where(ExternalOperation.task_id == it.task_id))) if it.task_id else []
        try:
            if resolution in {"requeue", "confirmed_not_done"} and t is not None:
                if resolution == "confirmed_not_done":
                    for op in ops:
                        if op.status in external.UNCERTAIN | {"unknown"}:
                            external.finish_operation(op, "failed", {"resolved_by": actor, "note": "dikonfirmasi tidak terjadi"})
                if t.status in {"failed", "blocked", "interrupted"}:
                    task_service.requeue_task(s, t, actor=actor, ttl_hours=self._settings.approval_ttl_hours)
            elif resolution in {"cancel", "confirmed_done"} and t is not None:
                if resolution == "confirmed_done":
                    for op in ops:
                        if op.status in external.UNCERTAIN | {"unknown"}:
                            external.finish_operation(op, "confirmed", {"resolved_by": actor, "note": "dikonfirmasi terjadi"})
                if t.status not in {"completed", "cancelled", "running"}:
                    task_service.cancel_task(s, t, actor=actor)
        except task_service.TaskError as e:
            raise PowerError(str(e)) from e
        it.status, it.resolved_at, it.resolved_by, it.resolution = "resolved", utcnow(), actor, resolution
        s.add(AuditLog(actor=actor, action="power.recovery_resolved", entity_type="recovery_item", entity_id=it.id, details={"resolution": resolution, "task_id": it.task_id}))
        self._log(s, None, "manual", f"resolved_{resolution}", t, None, {"item_id": it.id})
        emit(s, "power.recovery_item_resolved", {"item_id": it.id, "resolution": resolution}, actor)
        s.flush()
        st = get_state(s)
        if st.state == RECOVERY_REQUIRED and scheduling_allowed(st) and not open_items(s):
            set_state(s, RUNNING, reason="recovery_items_resolved", actor=actor)
        return it


# ---------------------------------------------------------------------- pengendali

class PowerController:
    def __init__(self, settings: Settings, session_factory, checkpoints: CheckpointManager, worker=None):
        self._settings = settings
        self._sf = session_factory
        self.checkpoints = checkpoints
        self.worker = worker
        self.recovery = RecoveryManager(settings, session_factory, checkpoints, self._executors)
        self._lock = asyncio.Lock()
        self._flows: set[asyncio.Task] = set()

    def attach_worker(self, worker) -> None:
        self.worker = worker

    def _executors(self) -> dict:
        if self.worker is not None:
            return self.worker.executors
        from app.tasks.executors import default_executors
        return default_executors()

    def can_schedule(self) -> bool:
        with self._sf() as s:
            return scheduling_allowed(s.get(PowerState, 1))

    # ------------------------------------------------------------------ permintaan

    async def request_off(self, actor: str = "ceo") -> dict:
        async with self._lock:
            with self._sf() as s:
                st = get_state(s)
                if st.state in (PAUSING, PAUSED):
                    return {"accepted": False, "already": True, "state": st.state, "command_id": st.active_command_id}
                if st.state == RESUMING:
                    raise PowerError("Sistem sedang melanjutkan pekerjaan; tunggu selesai sebelum OFF.")
                cmd = PowerCommand(action="off", requested_by=actor, status="running", progress=[])
                s.add(cmd)
                s.flush()
                s.add(AuditLog(actor=actor, action="power.off_requested", entity_type="power_command", entity_id=cmd.id))
                set_state(s, PAUSING, reason="off_requested", detail={"command_id": cmd.id, "step": "accepted"}, command_id=cmd.id, actor=actor)
                s.commit()
                cid = cmd.id
            self._spawn(self._pause_flow(cid))
            return {"accepted": True, "already": False, "state": PAUSING, "command_id": cid}

    async def request_on(self, actor: str = "ceo") -> dict:
        async with self._lock:
            with self._sf() as s:
                st = get_state(s)
                if st.state in (RUNNING, RESUMING) or (st.state == RECOVERY_REQUIRED and scheduling_allowed(st)):
                    return {"accepted": False, "already": True, "state": st.state, "command_id": st.active_command_id}
                if st.state == PAUSING:
                    raise PowerError("Sistem sedang menjeda pekerjaan; tunggu hingga PAUSED sebelum ON.")
                cmd = PowerCommand(action="on", requested_by=actor, status="running", progress=[])
                s.add(cmd)
                s.flush()
                s.add(AuditLog(actor=actor, action="power.on_requested", entity_type="power_command", entity_id=cmd.id))
                set_state(s, RESUMING, reason="on_requested", detail={"command_id": cmd.id, "step": "accepted"}, command_id=cmd.id, actor=actor)
                s.commit()
                cid = cmd.id
            self._spawn(self._resume_flow(cid))
            return {"accepted": True, "already": False, "state": RESUMING, "command_id": cid}

    def _spawn(self, coro) -> None:
        t = asyncio.ensure_future(coro)
        self._flows.add(t)
        t.add_done_callback(self._flows.discard)

    async def wait_idle(self, timeout: float = 60.0) -> None:
        if self._flows:
            await asyncio.wait(list(self._flows), timeout=timeout)

    async def shutdown(self) -> None:
        for t in list(self._flows):
            t.cancel()
        if self._flows:
            await asyncio.gather(*self._flows, return_exceptions=True)

    # ------------------------------------------------------------------ progres

    def _step(self, command_id: str, step: str, status: str = "done", detail: dict | None = None) -> None:
        with self._sf() as s:
            cmd = s.get(PowerCommand, command_id)
            entry = {"at": utcnow().isoformat(), "step": step, "status": status, **({"detail": detail} if detail else {})}
            cmd.progress = [*cmd.progress, entry]
            st = get_state(s)
            st.detail = {"command_id": command_id, "step": step, "status": status, **(detail or {})}
            emit(s, "power.progress", {"command_id": command_id, "step": step, "status": status, "detail": detail or {}})
            s.commit()

    def _finish(self, command_id: str, new_state: str, reason: str, *, result: dict | None, ok: bool, error: str | None = None,
                scheduling: bool | None = None) -> None:
        with self._sf() as s:
            cmd = s.get(PowerCommand, command_id)
            cmd.status, cmd.result, cmd.error, cmd.finished_at = ("completed" if ok else "failed"), result, error, utcnow()
            detail = {"command_id": command_id}
            if scheduling is not None:
                detail["scheduling"] = scheduling
            set_state(s, new_state, reason=reason, detail=detail, command_id=command_id)
            s.commit()

    def _db_ok(self) -> bool:
        try:
            with self._sf() as s:
                if s.get_bind().dialect.name == "sqlite":
                    return s.execute(text("PRAGMA quick_check")).scalar() == "ok"
                s.execute(text("SELECT 1"))
                return True
        except Exception:
            logger.exception("pemeriksaan database gagal")
            return False

    def _running_ids(self) -> list[str]:
        with self._sf() as s:
            return list(s.scalars(select(Task.id).where(Task.status == "running")))

    # ------------------------------------------------------------------ OFF

    async def _pause_flow(self, cid: str) -> None:
        try:
            await self._pause(cid)
        except asyncio.CancelledError:
            raise  # shutdown di tengah jeda: startup_recovery menuntaskan
        except Exception as e:
            logger.exception("proses OFF gagal")
            self._finish(cid, ERROR, "pause_failed", result=None, ok=False, error=f"{type(e).__name__}: {e}")

    async def _pause(self, cid: str) -> None:
        self._step(cid, "scheduler_stopped")
        running = self._running_ids()
        self._step(cid, "waiting_active_tasks", "running", {"tasks": len(running)})
        deadline = time.monotonic() + self._settings.power_pause_grace_s
        while running and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
            running = self._running_ids()
        checkpoints: list[str] = []
        unconfirmed: list[str] = []
        if running:
            self._step(cid, "saving_checkpoints", "running", {"tasks": len(running)})
            for tid in running:
                with self._sf() as s:
                    t = s.get(Task, tid)
                    attempt = s.scalar(select(TaskAttempt.id).where(TaskAttempt.task_id == tid, TaskAttempt.status == "running"))
                cp = await asyncio.to_thread(self.checkpoints.create, tid, attempt, "pause", "pause_requested")
                if cp:
                    checkpoints.append(cp)
                held = self.worker is not None and await self.worker.interrupt_running(tid, "paused")
                if not held:
                    continue  # tanpa pemegang di worker: ditangani sebagai yatim di bawah
            end = time.monotonic() + self._settings.power_interrupt_wait_s
            while time.monotonic() < end and self.worker is not None and self.worker.current_task_id:
                await asyncio.sleep(0.1)
            with self._sf() as s:
                self.recovery.interrupt_orphans(s, "paused", held={self.worker.current_task_id} if self.worker and self.worker.current_task_id else None)
                s.commit()
            unconfirmed = [t for t in self._running_ids()]
        self._step(cid, "tasks_stopped", "done" if not unconfirmed else "failed", {"unconfirmed": unconfirmed})
        # simpan checkpoint untuk task terputus yang belum punya checkpoint pause, lalu verifikasi semuanya dibaca ulang
        problems: list[dict] = []
        with self._sf() as s:
            interrupted = list(s.scalars(select(Task).where(Task.status == "interrupted")))
        for t in interrupted:
            with self._sf() as s:
                have = s.scalar(select(TaskCheckpoint.id).where(TaskCheckpoint.task_id == t.id, TaskCheckpoint.kind == "pause").limit(1))
            if not have:
                cp = await asyncio.to_thread(self.checkpoints.create, t.id, None, "pause", "paused_without_checkpoint")
                if cp:
                    checkpoints.append(cp)
        with self._sf() as s:
            for cpid in checkpoints:
                cp = s.get(TaskCheckpoint, cpid)
                res = self.checkpoints.validate(s, cp)
                if not res["valid"]:
                    problems.append({"checkpoint_id": cpid, "task_id": cp.task_id, "problems": res["problems"]})
            s.commit()
        self._step(cid, "checkpoints_verified", "done" if not problems else "failed", {"saved": len(checkpoints), "invalid": len(problems)})
        db_ok = await asyncio.to_thread(self._db_ok)
        self._step(cid, "database_verified", "done" if db_ok else "failed")
        counts = self._counts()
        result = {"checkpoints": len(checkpoints), "invalid_checkpoints": problems, "unconfirmed_running": unconfirmed, "database_ok": db_ok, "counts": counts}
        if unconfirmed or problems or not db_ok:
            with self._sf() as s:
                for t_id in unconfirmed:
                    t = s.get(Task, t_id)
                    self.recovery._item(s, t, "stop_unconfirmed", "Task tidak terkonfirmasi berhenti saat OFF; status sebenarnya tidak pasti.", {"task_id": t_id})
                for pr in problems:
                    t = s.get(Task, pr["task_id"])
                    self.recovery._item(s, t, "checkpoint_invalid", "Checkpoint pause gagal verifikasi; pulihkan dengan hati-hati.", pr)
                s.commit()
            self._finish(cid, RECOVERY_REQUIRED, "pause_not_verified", result=result, ok=False, error="penghentian atau penyimpanan tidak terverifikasi", scheduling=False)
            return
        self._finish(cid, PAUSED, "paused", result=result, ok=True)

    def _counts(self) -> dict:
        with self._sf() as s:
            return snapshot(s)["counts"]

    # ------------------------------------------------------------------ ON

    async def _resume_flow(self, cid: str) -> None:
        try:
            await self._resume(cid)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("proses ON gagal")
            self._finish(cid, ERROR, "resume_failed", result=None, ok=False, error=f"{type(e).__name__}: {e}")

    async def _resume(self, cid: str) -> None:
        db_ok = await asyncio.to_thread(self._db_ok)
        self._step(cid, "database_validated", "done" if db_ok else "failed")
        if not db_ok:
            self._finish(cid, ERROR, "database_check_failed", result={"database_ok": False}, ok=False, error="pemeriksaan database gagal")
            return
        ws_problems = await asyncio.to_thread(self._validate_workspaces)
        self._step(cid, "workspaces_validated", "done" if not ws_problems else "warning", {"problems": len(ws_problems)})
        if self.worker is not None:
            await asyncio.to_thread(self.worker.sync_dependencies)
        self._step(cid, "dependencies_validated")

        def work() -> dict:
            with self._sf() as s:
                self.recovery.interrupt_orphans(s, "resume_orphan")
                ext = self.recovery.check_external(s, cid, "resume")
                for t_id, msg in ws_problems:
                    t = s.get(Task, t_id)
                    if t is not None and t.status in {"queued", "interrupted", "blocked"}:
                        self.recovery._item(s, t, "files_missing", msg, {"source": "workspace_validation"})
                        self.recovery._log(s, cid, "resume", "manual_required", t, None, {"reason": "workspace_missing"})
                        if t.status == "queued":
                            change_status(s, t, "blocked", reason="files_missing")
                rec = self.recovery.recover_tasks(s, cid, "resume")
                rec["external_unknown"] = ext
                s.commit()
                return rec

        rec = await asyncio.to_thread(work)
        if self.worker is not None:
            await asyncio.to_thread(self.worker.sync_dependencies)  # dependen task yang dipulihkan dibuka kembali
        self._step(cid, "tasks_recovered", "done", rec)
        with self._sf() as s:
            n_open = len(open_items(s))
        counts = self._counts()
        result = {**rec, "open_items": n_open, "counts": counts, "workspace_problems": len(ws_problems)}
        if n_open:
            self._finish(cid, RECOVERY_REQUIRED, "resumed_with_open_items", result=result, ok=True, scheduling=True)
        else:
            self._finish(cid, RUNNING, "resumed", result=result, ok=True)

    def _validate_workspaces(self) -> list[tuple[str, str]]:
        """Task yang sudah pernah berjalan tetapi workspace/Git proyeknya hilang."""
        out: list[tuple[str, str]] = []
        with self._sf() as s:
            for t in s.scalars(select(Task).where(Task.status.in_(["queued", "interrupted", "blocked"]), Task.attempt_count > 0)):
                root = self.checkpoints.workspace_root(t.project_id)
                last = s.scalar(select(TaskCheckpoint).where(TaskCheckpoint.task_id == t.id).order_by(TaskCheckpoint.created_at.desc()).limit(1))
                had_repo = bool(last and ((last.payload or {}).get("git") or {}).get("present"))   # workspace memang sudah ada saat checkpoint
                if had_repo and not (root / ".git").exists():
                    out.append((t.id, "Workspace atau repositori Git proyek hilang; periksa sebelum melanjutkan."))
        return out

    # ------------------------------------------------------------------ startup / shutdown

    def startup_recovery(self) -> dict:
        """Dipanggil saat aplikasi mulai (sebelum worker). Mendeteksi proses sebelumnya yang berhenti tidak normal dan memulihkannya."""
        with self._sf() as s:
            st = get_state(s)
            prev = st.state
            unclean = not st.shutdown_clean
            incomplete = prev in (PAUSING, RESUMING)
            summary: dict = {"previous_state": prev, "unclean_shutdown": unclean, "incomplete_command": incomplete}
            if unclean or incomplete:
                held_reason = "crash_recovery" if unclean else "shutdown"
                cmd = PowerCommand(action="startup_recovery", requested_by="system", status="running", progress=[])
                s.add(cmd)
                s.flush()
                n = self.recovery.interrupt_orphans(s, held_reason)
                ext = self.recovery.check_external(s, cmd.id, "startup_crash")
                rec = self.recovery.recover_tasks(s, cmd.id, "startup_crash")
                n_open = len(open_items(s))
                if prev in (PAUSING, PAUSED):
                    target, scheduling = PAUSED, None
                elif n_open:
                    target, scheduling = RECOVERY_REQUIRED, True
                else:
                    target, scheduling = RUNNING, None
                summary.update({"orphans_interrupted": n, "external_unknown": ext, **rec, "open_items": n_open, "state": target})
                cmd.status, cmd.result, cmd.finished_at = "completed", summary, utcnow()
                set_state(s, target, reason="startup_recovery", detail={"command_id": cmd.id, **({"scheduling": scheduling} if scheduling is not None else {})},
                          command_id=cmd.id, force=True)
            elif prev == RUNNING:
                rec = self.recovery.recover_tasks(s, None, "startup")  # task yang dihentikan oleh shutdown bersih
                n_open = len(open_items(s))
                summary.update({**rec, "open_items": n_open, "state": RUNNING})
                if n_open:
                    set_state(s, RECOVERY_REQUIRED, reason="startup_open_items", detail={"scheduling": True}, force=True)
            st.shutdown_clean = False  # proses ini hidup; menjadi True hanya pada shutdown bersih
            s.commit()
            return summary

    def mark_shutdown_clean(self) -> None:
        with self._sf() as s:
            get_state(s).shutdown_clean = True
            s.commit()
