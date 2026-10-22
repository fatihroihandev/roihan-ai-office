"""Checkpoint persisten keadaan kerja task (Addendum v2.3, Bagian 29.A.5).

Checkpoint menyimpan keadaan yang DAPAT DIVERIFIKASI (status, ringkasan konteks, hash file, status Git, hasil tool, retry, operasi
eksternal, pemakaian model), bukan keadaan internal model. Disimpan di database (transaksi atomik): checkpoint valid terakhir tetap ada
bila penulisan berikutnya gagal. Isi tidak memuat prompt, rahasia, atau kredensial; setiap teks disamarkan.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.base import utcnow
from app.db.models import Execution, ExternalOperation, ModelUsage, Task, TaskAttempt, TaskCheckpoint, TaskDependency, TaskEvent
from app.engineering.recorder import redact
from app.projects.storage import ProjectStorage
from app.workspace import git as workspace_git

logger = logging.getLogger("roihan.power")

SCHEMA_VERSION = 1
MAX_FILES = 200
MAX_HASH_BYTES = 5 * 1024 * 1024
KINDS = {"start", "periodic", "pause", "end"}
REQUIRED_KEYS = {"task", "context", "git", "files", "tool_results", "retry", "external_operations", "usage", "attempt"}


def _sha256_file(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_HASH_BYTES:
            return "too_large"
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def digest(meta: dict, payload: dict) -> str:
    """Hash kanonik isi checkpoint beserta metadata penentu (mendeteksi perubahan atau kerusakan)."""
    blob = json.dumps({"meta": meta, "payload": payload}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _meta(cp: TaskCheckpoint) -> dict:
    return {"task_id": cp.task_id, "project_id": cp.project_id, "attempt_id": cp.attempt_id, "kind": cp.kind,
            "schema_version": cp.schema_version, "task_status": cp.task_status, "last_step": cp.last_step}


class CheckpointManager:
    def __init__(self, settings: Settings, session_factory, storage: ProjectStorage):
        self._settings = settings
        self._sf = session_factory
        self._storage = storage

    # ------------------------------------------------------------------ lokasi

    def workspace_root(self, project_id: str) -> Path:
        return self._storage.project_dir(project_id) / "workspace" / "source-code"

    def _area_path(self, project_id: str, area: str, rel: str) -> Path:
        base = self.workspace_root(project_id) if area == "workspace" else self._storage.project_dir(project_id)
        p = (base / rel).resolve()
        if base.resolve() not in p.parents and p != base.resolve():
            raise ValueError("path di luar area proyek")
        return p

    def _clean(self, text: str, limit: int = 300) -> str:
        return redact(text or "", self._settings.secret_values)[:limit]

    # ------------------------------------------------------------------ isi

    def build_payload(self, s: Session, task: Task, attempt_id: str | None, last_step: str | None) -> dict:
        deps = []
        for dep in s.scalars(select(Task).join(TaskDependency, TaskDependency.depends_on_id == Task.id).where(TaskDependency.task_id == task.id)):
            out = (dep.result or {}).get("output") if isinstance(dep.result, dict) else None
            deps.append({"id": dep.id, "title": self._clean(dep.title, 120), "status": dep.status,
                         "result_chars": len(out) if isinstance(out, str) else 0})
        attempt = s.get(TaskAttempt, attempt_id) if attempt_id else None
        root = self.workspace_root(task.project_id)
        git_info: dict = {"present": False}
        files: list[dict] = []
        if (root / ".git").exists():
            try:
                lines = workspace_git.status(root)
                git_info = {"present": True, "head": workspace_git.head(root), "dirty": bool(lines), "changed": len(lines),
                            "status": [self._clean(ln, 200) for ln in lines[:50]]}
                for ln in lines[:MAX_FILES]:
                    rel = ln[3:].split(" -> ")[-1].strip().strip('"')
                    p = root / rel
                    files.append({"area": "workspace", "path": rel, "sha256": _sha256_file(p) if p.is_file() else None,
                                  "bytes": p.stat().st_size if p.is_file() else None, "state": ln[:2].strip() or "?"})
            except (workspace_git.GitError, OSError) as e:
                git_info = {"present": True, "error": self._clean(str(e))}
        artifact = self._storage.project_dir(task.project_id) / "artifacts" / f"{task.id}.md"
        if artifact.is_file():
            files.append({"area": "project", "path": f"artifacts/{task.id}.md", "sha256": _sha256_file(artifact), "bytes": artifact.stat().st_size, "state": "artifact"})
        tools = [{"kind": e.kind, "status": e.status, "exit_code": e.exit_code, "duration_ms": e.duration_ms}
                 for e in s.scalars(select(Execution).where(Execution.task_id == task.id).order_by(Execution.created_at.desc()).limit(10))]
        attempt_ids = list(s.scalars(select(TaskAttempt.id).where(TaskAttempt.task_id == task.id)))
        usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_idr": 0.0}
        if attempt_ids:
            row = s.execute(select(func.count(), func.coalesce(func.sum(ModelUsage.prompt_tokens), 0), func.coalesce(func.sum(ModelUsage.completion_tokens), 0),
                                   func.coalesce(func.sum(ModelUsage.cost_idr), 0.0)).where(ModelUsage.request_id.in_(attempt_ids))).one()
            usage = {"calls": int(row[0]), "prompt_tokens": int(row[1]), "completion_tokens": int(row[2]), "cost_idr": float(row[3])}
        ext = [{"id": o.id, "kind": o.kind, "status": o.status, "key": self._clean(o.idempotency_key, 120)}
               for o in s.scalars(select(ExternalOperation).where(ExternalOperation.task_id == task.id))]
        tail = [{"to": e.to_status, "reason": e.reason} for e in s.scalars(select(TaskEvent).where(TaskEvent.task_id == task.id).order_by(TaskEvent.seq.desc()).limit(5))]
        return {
            "task": {"id": task.id, "status": task.status, "role": task.role, "action_type": task.action_type, "risk_level": task.risk_level,
                     "requires_approval": task.requires_approval},
            "context": {"title": self._clean(task.title, 160), "criteria": [self._clean(c, 160) for c in (task.acceptance_criteria or [])[:10]],
                        "dependencies": deps, "events_tail": tail},
            "attempt": {"id": attempt_id, "number": attempt.number if attempt else None, "status": attempt.status if attempt else None},
            "git": git_info, "files": files, "tool_results": tools,
            "retry": {"attempt_count": task.attempt_count, "max_retries": task.max_retries, "attempts_baseline": task.attempts_baseline},
            "external_operations": ext, "usage": usage,
        }

    # ------------------------------------------------------------------ tulis

    def create(self, task_id: str, attempt_id: str | None, kind: str, last_step: str | None = None, *, strict: bool = False) -> str | None:
        """Simpan checkpoint baru. Kegagalan menulis tidak menggagalkan task (kecuali `strict`), dan checkpoint lama tetap utuh."""
        assert kind in KINDS
        last_step = self._clean(last_step, 200) if last_step else None  # teks bebas dari pemanggil juga disamarkan
        try:
            with self._sf() as s:
                task = s.get(Task, task_id)
                if task is None:
                    return None
                payload = self.build_payload(s, task, attempt_id, last_step)
                cp = TaskCheckpoint(project_id=task.project_id, task_id=task.id, attempt_id=attempt_id, agent_role=task.role, kind=kind,
                                    schema_version=SCHEMA_VERSION, task_status=task.status, last_step=last_step, payload=payload, payload_sha256="")
                cp.payload_sha256 = digest(_meta(cp), payload)
                s.add(cp)
                s.flush()
                self.prune(s, task_id)
                s.commit()
                return cp.id
        except Exception:
            logger.exception("gagal menulis checkpoint", extra={"task_id": task_id})
            if strict:
                raise
            return None

    def prune(self, s: Session, task_id: str) -> None:
        keep = max(1, self._settings.power_checkpoint_keep)
        rows = list(s.scalars(select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id).order_by(TaskCheckpoint.created_at.desc(), TaskCheckpoint.id.desc())))
        # selalu sisakan minimal satu checkpoint yang lolos validasi sebelumnya
        for cp in rows[keep:]:
            s.delete(cp)

    # ------------------------------------------------------------------ baca dan validasi

    def validate(self, s: Session, cp: TaskCheckpoint) -> dict:
        problems: list[dict] = []
        warnings: list[str] = []
        if cp.schema_version != SCHEMA_VERSION:
            problems.append({"kind": "schema_version", "message": f"versi skema {cp.schema_version} tidak didukung"})
        payload = cp.payload if isinstance(cp.payload, dict) else {}
        if not REQUIRED_KEYS <= set(payload):
            problems.append({"kind": "incomplete", "message": "isi checkpoint tidak lengkap"})
        if digest(_meta(cp), payload) != cp.payload_sha256:
            problems.append({"kind": "hash_mismatch", "message": "hash isi tidak cocok (rusak atau diubah)"})
        if not problems:
            for f in payload.get("files", []):
                try:
                    p = self._area_path(cp.project_id, f["area"], f["path"])
                except (ValueError, KeyError):
                    problems.append({"kind": "bad_path", "message": f"path tidak valid: {f.get('path')}"})
                    continue
                if f.get("sha256") is None:
                    continue  # file memang sudah terhapus saat checkpoint
                if not p.is_file():
                    problems.append({"kind": "files_missing", "message": f"file hilang: {f['path']}"})
                elif f["sha256"] != "too_large" and _sha256_file(p) != f["sha256"]:
                    warnings.append(f"file berubah sejak checkpoint (perubahan dipertahankan): {f['path']}")
            git = payload.get("git", {})
            head = git.get("head")
            root = self.workspace_root(cp.project_id)
            if head:
                cur = workspace_git.head(root) if (root / ".git").exists() else None
                if cur is None:
                    problems.append({"kind": "git_missing", "message": "repositori Git proyek tidak ditemukan"})
                elif cur != head and not workspace_git.is_ancestor(root, head, cur):
                    problems.append({"kind": "git_history_changed", "message": "riwayat Git tidak lagi memuat commit pada checkpoint"})
        result = {"valid": not problems, "problems": problems, "warnings": warnings, "checked_at": utcnow().isoformat()}
        cp.validation = result
        return result

    def latest_valid(self, s: Session, task_id: str) -> tuple[TaskCheckpoint | None, list[tuple[TaskCheckpoint, dict]]]:
        """Checkpoint valid terbaru; kembalikan juga daftar yang gagal validasi (untuk dicatat)."""
        invalid: list[tuple[TaskCheckpoint, dict]] = []
        for cp in s.scalars(select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id).order_by(TaskCheckpoint.created_at.desc(), TaskCheckpoint.id.desc())):
            res = self.validate(s, cp)
            if res["valid"]:
                return cp, invalid
            invalid.append((cp, res))
        return None, invalid

    @staticmethod
    def brief(cp: TaskCheckpoint) -> dict:
        v = cp.validation or {}
        return {"id": cp.id, "task_id": cp.task_id, "attempt_id": cp.attempt_id, "kind": cp.kind, "task_status": cp.task_status,
                "last_step": cp.last_step, "created_at": cp.created_at.isoformat() if isinstance(cp.created_at, datetime) else None,
                "schema_version": cp.schema_version, "valid": v.get("valid"), "problems": v.get("problems", []), "warnings": v.get("warnings", []),
                "git": (cp.payload or {}).get("git", {}), "files": len((cp.payload or {}).get("files", [])), "usage": (cp.payload or {}).get("usage")}
