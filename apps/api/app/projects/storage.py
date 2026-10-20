"""Struktur penyimpanan proyek (Bagian 13.2). Folder input tidak boleh dimodifikasi agent."""
import hashlib
import json
import os
import re
from pathlib import Path

from app.projects.uploads import KIND_DIRS, FileKind

PROJECT_SUBDIRS = [
    "input/requirements", "input/references", "input/assets",
    "workspace/source-code", "artifacts", "reports", "metadata",
]


class StorageError(RuntimeError):
    pass


class ProjectStorage:
    def __init__(self, projects_dir: Path):
        self.root = projects_dir.resolve()

    def project_dir(self, project_id: str) -> Path:
        path = (self.root / project_id).resolve()
        if path.parent != self.root:
            raise StorageError("ID proyek tidak valid")
        return path

    def create_layout(self, project_id: str) -> Path:
        base = self.project_dir(project_id)
        for sub in PROJECT_SUBDIRS:
            (base / sub).mkdir(parents=True, exist_ok=True)
        return base

    def write_metadata(self, project_id: str, data: dict) -> None:
        path = self.project_dir(project_id) / "metadata" / "project.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)

    def save_file(self, project_id: str, kind: FileKind, name: str, data: bytes) -> tuple[str, str, str]:
        """Simpan file secara atomik tanpa menimpa file lain. Kembalikan (stored_name, relative_path, sha256)."""
        base = self.project_dir(project_id)
        target_dir = (base / KIND_DIRS[kind]).resolve()
        if base not in target_dir.parents and target_dir != base:
            raise StorageError("Lokasi tujuan di luar folder proyek")
        target_dir.mkdir(parents=True, exist_ok=True)

        stem, dot, ext = name.rpartition(".")
        stem = stem if dot else name
        candidate, n = name, 1
        while True:
            dest = target_dir / candidate
            try:
                # mode "xb": gagal jika sudah ada, sehingga file lama tidak pernah tertimpa
                with open(dest, "xb") as fh:
                    fh.write(data)
                break
            except FileExistsError:
                n += 1
                candidate = f"{stem}-{n}{dot}{ext}"
        rel = dest.relative_to(base).as_posix()
        return candidate, rel, hashlib.sha256(data).hexdigest()

    def write_artifact(self, project_id: str, task_id: str, text: str) -> str:
        """Simpan hasil task ke artifacts/<task_id>.md. Nama dibatasi ke UUID agar tidak bisa keluar folder."""
        if not re.fullmatch(r"[0-9a-f-]{36}", task_id):
            raise StorageError("ID task tidak valid")
        path = self.project_dir(project_id) / "artifacts" / f"{task_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        return path.relative_to(self.project_dir(project_id)).as_posix()

    def resolve_file(self, project_id: str, relative_path: str) -> Path:
        base = self.project_dir(project_id)
        path = (base / relative_path).resolve()
        if base not in path.parents:
            raise StorageError("Path file di luar folder proyek")
        return path
