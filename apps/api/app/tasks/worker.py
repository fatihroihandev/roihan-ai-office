"""Worker task: mengambil task dari antrean berbasis database dan menjalankannya satu per satu.

Antrean = tabel `tasks` (status `queued`). Klaim bersifat atomik (UPDATE bersyarat), sehingga worker dapat
dipindah ke proses terpisah tanpa mengubah antrean. Kejadian ditulis ke `task_events`; WebSocket hanya
mendistribusikannya.
"""
import asyncio
import logging

from sqlalchemy import select

from app.config import Settings
from app.db.base import utcnow
from app.db.models import Task, TaskAttempt, TaskDependency
from app.projects.storage import ProjectStorage
from app.providers.base import GatewayBlocked, ProviderError, ProviderErrorKind
from app.providers.gateway import ModelGateway
from app.routing.router import ModelRouter, RoutingError, TaskSnapshot
from app.tasks.executors import ExecutionContext, Executor, ExecutorError, default_executors
from app.tasks.service import retry_delay
from app.tasks.state import add_event, change_status

logger = logging.getLogger("roihan.worker")
# Dependensi dalam status ini tidak akan selesai dengan sendirinya, sehingga dependen ikut diblokir
UNRESOLVED_DEPS = ("failed", "cancelled", "interrupted", "blocked")


class TaskWorker:
    def __init__(self, settings: Settings, session_factory, gateway: ModelGateway, router: ModelRouter,
                 storage: ProjectStorage, executors: dict[str, Executor] | None = None):
        self._settings = settings
        self._sf = session_factory
        self._gateway = gateway
        self._router = router
        self._storage = storage
        self.executors = executors if executors is not None else default_executors()
        self._current: dict[str, tuple[asyncio.Future, str]] = {}   # task_id -> (future executor, attempt_id)
        self._cancel_requested: set[str] = set()
        self._stop = asyncio.Event()
        self.current_task_id: str | None = None

    # ------------------------------------------------------------------ recovery

    def recover(self) -> int:
        """Dipanggil saat start: task `running` tanpa worker hidup ditandai interrupted, lalu dipulihkan jika aman."""
        recovered = 0
        with self._sf() as s:
            for t in s.scalars(select(Task).where(Task.status == "running")).all():
                for a in s.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.status == "running")):
                    a.status, a.finished_at, a.error_kind = "interrupted", utcnow(), "interrupted"
                change_status(s, t, "interrupted", reason="worker_restart")
                ex = self.executors.get(t.role)
                if ex is not None and ex.idempotent and self._retries_left(t) > 0:
                    t.available_at = utcnow()
                    change_status(s, t, "queued", reason="recovered")
                recovered += 1
            s.commit()
        return recovered

    # ------------------------------------------------------------------ antrean

    def _retries_left(self, t: Task) -> int:
        return t.max_retries - (t.attempt_count - t.attempts_baseline - 1)

    def _propagate(self) -> None:
        """Sinkronkan status dependen: blokir yang dependensinya tidak dapat selesai, buka kembali yang sudah pulih.

        Diulang sampai stabil agar rantai dependensi (A <- B <- C) ikut terblokir/terbuka dalam satu siklus.
        """
        for _ in range(20):
            if not self._propagate_once():
                return

    def _propagate_once(self) -> bool:
        changed = False
        with self._sf() as s:
            def dep_statuses(task_id: str) -> list[str]:
                return list(s.scalars(select(Task.status).join(TaskDependency, TaskDependency.depends_on_id == Task.id)
                                      .where(TaskDependency.task_id == task_id)))
            for t in s.scalars(select(Task).where(Task.status == "queued")).all():
                if any(d in UNRESOLVED_DEPS for d in dep_statuses(t.id)):
                    change_status(s, t, "blocked", reason="dependency_failed")
                    changed = True
            for t in s.scalars(select(Task).where(Task.status == "blocked", Task.blocked_reason == "dependency_failed")).all():
                if all(d == "completed" for d in dep_statuses(t.id)):
                    change_status(s, t, "queued", reason="dependencies_recovered")
                    changed = True
            s.commit()
        return changed

    def _claim(self) -> tuple[str, str] | None:
        """Ambil task siap-jalan berprioritas tertinggi; kembalikan (task_id, attempt_id)."""
        with self._sf() as s:
            ready = s.scalars(select(Task).where(Task.status == "queued", Task.available_at <= utcnow())
                              .order_by(Task.priority.desc(), Task.created_at, Task.id)).all()
            for t in ready:
                dep_status = list(s.scalars(select(Task.status).join(TaskDependency, TaskDependency.depends_on_id == Task.id)
                                            .where(TaskDependency.task_id == t.id)))
                if any(d != "completed" for d in dep_status):
                    continue
                if t.role not in self.executors:
                    # Fitur yang belum dibangun ditandai jujur sebagai belum tersedia (Bagian 23)
                    change_status(s, t, "blocked", reason="executor_not_available")
                    t.last_error = f"Belum ada agent untuk role '{t.role}'"
                    t.last_error_kind = "executor_not_available"
                    s.commit()
                    continue
                # penjaga: task bisa dibatalkan dari API di antara pembacaan dan klaim
                s.refresh(t)
                if t.status != "queued":
                    continue
                t.attempt_count += 1
                attempt = TaskAttempt(task_id=t.id, number=t.attempt_count)
                s.add(attempt)
                s.flush()
                change_status(s, t, "running", payload={"attempt": t.attempt_count, "attempt_id": attempt.id})
                s.commit()
                return t.id, attempt.id
        return None

    # ------------------------------------------------------------------ eksekusi

    async def run_once(self) -> bool:
        self._propagate()
        claimed = self._claim()
        if claimed is None:
            return False
        await self._run_attempt(*claimed)
        return True

    async def _run_attempt(self, task_id: str, attempt_id: str) -> None:
        with self._sf() as s:
            task = s.get(Task, task_id)
            snapshot, role = TaskSnapshot.from_task(task), task.role
        ctx = ExecutionContext(snapshot, attempt_id, self._sf, self._gateway, self._router, self._settings, self._storage)
        fut = asyncio.ensure_future(self.executors[role].run(ctx))
        self._current[task_id] = (fut, attempt_id)
        self.current_task_id = task_id
        try:
            outcome = await fut
        except asyncio.CancelledError:
            if task_id in self._cancel_requested:
                self._finish_cancelled(task_id, attempt_id, ctx)
            else:  # server berhenti saat task berjalan
                self._finish_interrupted(task_id, attempt_id, ctx)
                raise
        except ProviderError as e:
            if e.kind == ProviderErrorKind.cancelled and task_id in self._cancel_requested:
                self._finish_cancelled(task_id, attempt_id, ctx)
            else:
                self._finish_failed(task_id, attempt_id, ctx, e.kind.value, e.message, e.retryable)
        except ExecutorError as e:
            self._finish_failed(task_id, attempt_id, ctx, e.kind, e.message, e.retryable)
        except (GatewayBlocked, RoutingError) as e:
            self._finish_blocked(task_id, attempt_id, ctx, e.reason, e.message)
        except Exception as e:  # kegagalan tak terduga: jangan diulang otomatis
            logger.exception("task gagal tak terduga", extra={"task_id": task_id})
            self._finish_failed(task_id, attempt_id, ctx, "unexpected_error", f"{type(e).__name__}: {e}", False)
        else:
            self._finish_ok(task_id, attempt_id, ctx, outcome)
        finally:
            self._current.pop(task_id, None)
            self._cancel_requested.discard(task_id)
            self.current_task_id = None

    def _close_attempt(self, s, attempt_id: str, ctx: ExecutionContext, status: str, *, kind=None, message=None, retryable=None):
        a = s.get(TaskAttempt, attempt_id)
        a.status, a.finished_at, a.error_kind, a.error_message, a.retryable = status, utcnow(), kind, message, retryable
        a.provider, a.model, a.usage = ctx.provider, ctx.model, dict(ctx.usage)

    def _finish_ok(self, task_id, attempt_id, ctx, outcome) -> None:
        with self._sf() as s:
            t = s.get(Task, task_id)
            if not outcome.verified:
                self._close_attempt(s, attempt_id, ctx, "failed", kind="unverified", message="Hasil tidak lolos verifikasi", retryable=False)
                t.last_error, t.last_error_kind = "Hasil tidak lolos verifikasi", "unverified"
                change_status(s, t, "failed", reason="unverified")
            else:
                self._close_attempt(s, attempt_id, ctx, "succeeded")
                t.result, t.verification, t.last_error, t.last_error_kind = outcome.result, outcome.verification, None, None
                change_status(s, t, "completed", payload={"attempt": t.attempt_count})
            s.commit()

    def _finish_failed(self, task_id, attempt_id, ctx, kind: str, message: str, retryable: bool) -> None:
        with self._sf() as s:
            t = s.get(Task, task_id)
            self._close_attempt(s, attempt_id, ctx, "failed", kind=kind, message=message, retryable=retryable)
            t.last_error, t.last_error_kind = message, kind
            change_status(s, t, "failed", reason=kind, payload={"attempt": t.attempt_count, "retryable": retryable})
            if retryable and self._retries_left(t) > 0:
                used = t.attempt_count - t.attempts_baseline - 1
                delay = retry_delay(self._settings.retry_backoff_base_s, used)
                t.available_at = utcnow() + delay
                change_status(s, t, "queued", reason="auto_retry",
                              payload={"retry_in_s": delay.total_seconds(), "attempt_next": t.attempt_count + 1})
            s.commit()

    def _finish_blocked(self, task_id, attempt_id, ctx, reason: str, message: str) -> None:
        with self._sf() as s:
            t = s.get(Task, task_id)
            self._close_attempt(s, attempt_id, ctx, "blocked", kind=reason, message=message, retryable=False)
            t.last_error, t.last_error_kind = message, reason
            change_status(s, t, "blocked", reason=reason)
            s.commit()

    def _finish_cancelled(self, task_id, attempt_id, ctx) -> None:
        with self._sf() as s:
            t = s.get(Task, task_id)
            self._close_attempt(s, attempt_id, ctx, "cancelled", kind="cancelled", retryable=False)
            change_status(s, t, "cancelled", reason="cancelled_by_user")
            s.commit()

    def _finish_interrupted(self, task_id, attempt_id, ctx) -> None:
        with self._sf() as s:
            t = s.get(Task, task_id)
            self._close_attempt(s, attempt_id, ctx, "interrupted", kind="interrupted", retryable=True)
            change_status(s, t, "interrupted", reason="shutdown")
            s.commit()

    # ------------------------------------------------------------------ kontrol

    async def cancel_running(self, task_id: str) -> bool:
        entry = self._current.get(task_id)
        if entry is None:
            return False
        fut, attempt_id = entry
        self._cancel_requested.add(task_id)
        await self._gateway.cancel(attempt_id)   # menutup koneksi ke provider bila ada panggilan berjalan
        if not fut.done():
            fut.cancel()
        return True

    async def run_forever(self) -> None:
        logger.info("worker mulai", extra={"recovered": self.recover()})
        while not self._stop.is_set():
            try:
                worked = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("siklus worker gagal")
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._settings.worker_poll_interval_s)
                except asyncio.TimeoutError:
                    pass

    def stop(self) -> None:
        self._stop.set()
