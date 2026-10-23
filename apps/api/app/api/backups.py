"""Cadangan data (Fase 11): daftar, buat, dan verifikasi. Pemulihan sengaja hanya lewat CLI saat backend berhenti."""
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.engine import make_url

from app.api.health import APP_VERSION
from app.backup import service as svc
from app.security import require_token

router = APIRouter(prefix="/api/backups", tags=["backups"], dependencies=[Depends(require_token)])
_NAME = re.compile(r"^[0-9]{8}T[0-9]{6}-[a-z-]+(-[0-9]+)?$")


def backup_paths(settings) -> tuple[Path | str, Path]:
    url = make_url(settings.database_url)
    if url.get_backend_name() == "sqlite" and url.database:
        return Path(url.database), settings.data_dir / "backups"
    if url.get_backend_name() == "postgresql":
        return settings.database_url, settings.data_dir / "backups"
    raise svc.BackupError("Jenis database ini belum didukung untuk cadangan.")


def run_backup(settings, label: str) -> Path:
    """Dipakai endpoint manual: buat cadangan lalu pangkas yang lama."""
    db, backups = backup_paths(settings)
    d = svc.create_backup(db, backups, settings.projects_dir, include_projects=settings.backup_include_projects,
                          max_project_bytes=settings.backup_max_project_mb * 1024 * 1024, label=label, app_version=APP_VERSION)
    svc.prune_backups(backups, settings.backup_keep)
    return d


@router.get("")
def list_all(request: Request):
    _, backups = backup_paths(request.app.state.settings)
    return {"items": svc.list_backups(backups)}


@router.post("", status_code=201)
def create(request: Request):
    try:
        d = run_backup(request.app.state.settings, "manual")
    except svc.BackupError as e:
        raise HTTPException(500, str(e)) from e
    return {"name": d.name}


@router.post("/{name}/verify")
def verify(name: str, request: Request):
    if not _NAME.match(name):
        raise HTTPException(404, "Cadangan tidak ditemukan")
    _, backups = backup_paths(request.app.state.settings)
    d = backups / name
    if not d.is_dir():
        raise HTTPException(404, "Cadangan tidak ditemukan")
    r = svc.verify_backup(d)
    return {"name": name, "ok": r.ok, "problems": r.problems}
