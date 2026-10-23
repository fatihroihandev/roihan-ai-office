"""CLI cadangan: python -m app.backup {create|list|verify|restore|prune} (jalankan dari apps/api)."""
import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

from app.backup import service as svc
from app.config import get_settings
from app.api.health import APP_VERSION


def _paths():
    s = get_settings()
    url = make_url(s.database_url)
    if url.get_backend_name() == "sqlite" and url.database:
        database = Path(url.database)
    elif url.get_backend_name() == "postgresql":
        database = s.database_url
    else:
        raise svc.BackupError("Jenis database ini belum didukung untuk cadangan.")
    return s, database, s.data_dir / "backups"


def _resolve(backups: Path, name: str) -> Path:
    p = Path(name)
    return p if p.is_dir() else backups / name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.backup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("create")
    sub.add_parser("list")
    v = sub.add_parser("verify"); v.add_argument("name")
    r = sub.add_parser("restore"); r.add_argument("name"); r.add_argument("--force", action="store_true")
    p = sub.add_parser("prune"); p.add_argument("--keep", type=int)
    a = ap.parse_args(argv)
    try:
        s, db, backups = _paths()
        if a.cmd == "create":
            d = svc.create_backup(db, backups, s.projects_dir, include_projects=s.backup_include_projects,
                                  max_project_bytes=s.backup_max_project_mb * 1024 * 1024, app_version=APP_VERSION)
            print(f"Cadangan dibuat: {d}")
        elif a.cmd == "list":
            print(json.dumps(svc.list_backups(backups), indent=2, ensure_ascii=False))
        elif a.cmd == "verify":
            res = svc.verify_backup(_resolve(backups, a.name))
            print("VALID" if res.ok else "TIDAK VALID: " + "; ".join(res.problems))
            return 0 if res.ok else 1
        elif a.cmd == "restore":
            out = svc.restore_backup(_resolve(backups, a.name), db, backups, s.projects_dir, force=a.force, app_version=APP_VERSION)
            print(json.dumps(out, indent=2, ensure_ascii=False))
        elif a.cmd == "prune":
            print("Dihapus:", svc.prune_backups(backups, a.keep or s.backup_keep))
    except svc.BackupError as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
