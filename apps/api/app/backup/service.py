"""Backup dan pemulihan data (Fase 11).

Cadangan = satu folder berisi snapshot database, opsional `projects.tar.gz`, dan `manifest.json`.
SQLite memakai `roihan.db`; PostgreSQL memakai stream JSON terkompresi agar tidak memerlukan executable pg_dump lokal.
Rahasia (`.env`, token) tidak pernah ikut. Pemulihan hanya lewat CLI saat backend berhenti.
"""
from __future__ import annotations

import hashlib
import gzip
import json
import os
import shutil
import sqlite3
import tarfile
import time
import base64
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as datetime_time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.types import Date, DateTime, JSON, LargeBinary, Numeric, Time, Uuid

MANIFEST = "manifest.json"
DB_FILE = "roihan.db"
PG_DB_FILE = "database.jsonl.gz"
PROJECTS_FILE = "projects.tar.gz"
MANIFEST_FORMAT = 1
API_ROOT = Path(__file__).resolve().parents[2]


class BackupError(Exception):
    """Kegagalan backup/restore yang pesannya aman ditampilkan kepada pengguna."""


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    problems: list[str]
    manifest: dict | None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return [r[0] for r in rows]


def table_counts(db: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in _tables(conn)}
    finally:
        conn.close()


def db_revision(db: Path) -> str | None:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        if "alembic_version" not in _tables(conn):
            return None
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def integrity_ok(db: Path) -> bool:
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def known_revisions() -> tuple[set[str], str | None]:
    """Semua revisi migrasi yang dikenal kode ini beserta head-nya."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    return {r.revision for r in script.walk_revisions()}, script.get_current_head()


def _archive_projects(projects_dir: Path, target: Path) -> None:
    with tarfile.open(target, "w:gz") as tar:
        for path in sorted(projects_dir.rglob("*")):
            if path.is_symlink():
                continue  # tautan simbolik tidak dicadangkan (hindari keluar dari folder proyek)
            tar.add(path, arcname=path.relative_to(projects_dir).as_posix(), recursive=False)


def _dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def create_backup(db_path: Path | str | URL, backups_dir: Path, projects_dir: Path | None = None, *, include_projects: bool = True,
                  max_project_bytes: int = 500 * 1024 * 1024, label: str = "manual", app_version: str = "") -> Path:
    """Buat cadangan SQLite atau PostgreSQL secara atomik."""
    if isinstance(db_path, (str, URL)):
        url = make_url(db_path)
        if url.get_backend_name() == "postgresql":
            return create_postgres_backup(url, backups_dir, projects_dir, include_projects=include_projects,
                                          max_project_bytes=max_project_bytes, label=label, app_version=app_version)
        if url.get_backend_name() != "sqlite" or not url.database:
            raise BackupError("URL database cadangan tidak didukung.")
        db_path = Path(url.database)
    if not db_path.exists():
        raise BackupError(f"Database tidak ditemukan: {db_path}")
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utcnow().strftime("%Y%m%dT%H%M%S")
    name = f"{stamp}-{label}"
    final = backups_dir / name
    n = 1
    while final.exists():
        n += 1
        final = backups_dir / f"{name}-{n}"
    tmp = backups_dir / f".tmp-{final.name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        # salinan konsisten lewat API backup SQLite (aman walau ada penulisan bersamaan)
        src = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=30)
        dst = sqlite3.connect(tmp / DB_FILE)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        if not integrity_ok(tmp / DB_FILE):
            raise BackupError("Salinan database gagal uji integritas; cadangan dibatalkan.")

        files = {DB_FILE: {"sha256": _sha256(tmp / DB_FILE), "bytes": (tmp / DB_FILE).stat().st_size}}
        warnings: list[str] = []
        if include_projects and projects_dir is not None and projects_dir.exists():
            size = _dir_size(projects_dir)
            if size > max_project_bytes:
                warnings.append(f"folder proyek ({size // (1024 * 1024)} MB) melebihi batas {max_project_bytes // (1024 * 1024)} MB; tidak dicadangkan")
            else:
                _archive_projects(projects_dir, tmp / PROJECTS_FILE)
                files[PROJECTS_FILE] = {"sha256": _sha256(tmp / PROJECTS_FILE), "bytes": (tmp / PROJECTS_FILE).stat().st_size}
        manifest = {
            "format": MANIFEST_FORMAT, "created_at": _utcnow().isoformat(), "label": label, "app_version": app_version,
            "alembic_revision": db_revision(tmp / DB_FILE), "tables": table_counts(tmp / DB_FILE), "files": files, "warnings": warnings,
        }
        (tmp / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


def _models_metadata():
    from app.db import models  # noqa: F401
    from app.db.base import Base

    return Base.metadata


def _pg_engine(url):
    from app.db.session import create_db_engine

    return create_db_engine(url.render_as_string(hide_password=False))


def _pg_revision(conn) -> str | None:
    try:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except Exception:
        return None


def _pg_counts(conn, tables) -> dict[str, int]:
    return {table.name: conn.scalar(select(func.count()).select_from(table)) for table in tables}


def _encode_cell(value, column):
    if value is None:
        return None
    kind = column.type
    if isinstance(kind, DateTime):
        return {"$type": "datetime", "value": value.isoformat()}
    if isinstance(kind, Date) and not isinstance(kind, DateTime):
        return {"$type": "date", "value": value.isoformat()}
    if isinstance(kind, Time):
        return {"$type": "time", "value": value.isoformat()}
    if isinstance(kind, Numeric):
        return {"$type": "decimal", "value": str(value)}
    if isinstance(kind, Uuid) or isinstance(value, UUID):
        return {"$type": "uuid", "value": str(value)}
    if isinstance(kind, LargeBinary):
        return {"$type": "bytes", "value": base64.b64encode(value).decode("ascii")}
    return value


def _decode_cell(value, column):
    if not isinstance(value, dict) or "$type" not in value:
        return value
    if isinstance(column.type, JSON):
        return value
    kind = value["$type"]
    raw = value["value"]
    if kind == "datetime" and isinstance(column.type, DateTime):
        return datetime.fromisoformat(raw)
    if kind == "date" and isinstance(column.type, Date) and not isinstance(column.type, DateTime):
        return date.fromisoformat(raw)
    if kind == "time" and isinstance(column.type, Time):
        return datetime_time.fromisoformat(raw)
    if kind == "decimal" and isinstance(column.type, Numeric):
        return Decimal(raw)
    if kind == "uuid" and isinstance(column.type, Uuid):
        return UUID(raw)
    if kind == "bytes" and isinstance(column.type, LargeBinary):
        return base64.b64decode(raw, validate=True)
    raise BackupError(f"Tipe nilai backup tidak dikenal: {kind}")


def create_postgres_backup(database_url: URL, backups_dir: Path, projects_dir: Path | None = None, *, include_projects: bool = True,
                           max_project_bytes: int = 500 * 1024 * 1024, label: str = "manual", app_version: str = "") -> Path:
    from sqlalchemy import Engine

    metadata = _models_metadata()
    tables = list(metadata.sorted_tables)
    engine: Engine = _pg_engine(database_url)
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utcnow().strftime("%Y%m%dT%H%M%S")
    name = f"{stamp}-{label}"
    final = backups_dir / name
    n = 1
    while final.exists():
        n += 1
        final = backups_dir / f"{name}-{n}"
    tmp = backups_dir / f".tmp-{final.name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    try:
        db_file = tmp / PG_DB_FILE
        with engine.connect() as connection:
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                revision = _pg_revision(connection)
                counts = _pg_counts(connection, tables)
                with gzip.open(db_file, "wt", encoding="utf-8", newline="\n") as stream:
                    for table in tables:
                        rows = connection.execute(select(table).execution_options(yield_per=1000)).mappings()
                        for row in rows:
                            payload = {column.name: _encode_cell(row[column.name], column) for column in table.columns}
                            stream.write(json.dumps({"table": table.name, "row": payload}, ensure_ascii=False, separators=(",", ":")) + "\n")

        files = {PG_DB_FILE: {"sha256": _sha256(db_file), "bytes": db_file.stat().st_size}}
        warnings: list[str] = []
        if include_projects and projects_dir is not None and projects_dir.exists():
            size = _dir_size(projects_dir)
            if size > max_project_bytes:
                warnings.append(f"folder proyek ({size // (1024 * 1024)} MB) melebihi batas {max_project_bytes // (1024 * 1024)} MB; tidak dicadangkan")
            else:
                _archive_projects(projects_dir, tmp / PROJECTS_FILE)
                files[PROJECTS_FILE] = {"sha256": _sha256(tmp / PROJECTS_FILE), "bytes": (tmp / PROJECTS_FILE).stat().st_size}
        manifest = {
            "format": 2, "database_kind": "postgresql", "created_at": _utcnow().isoformat(), "label": label,
            "app_version": app_version, "alembic_revision": revision, "tables": counts, "files": files, "warnings": warnings,
        }
        (tmp / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, final)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    finally:
        engine.dispose()
    return final


def read_manifest(backup: Path) -> dict:
    try:
        data = json.loads((backup / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BackupError(f"Manifest cadangan tidak terbaca: {e}") from e
    if not isinstance(data, dict) or data.get("format") not in {MANIFEST_FORMAT, 2} or "files" not in data:
        raise BackupError("Format manifest cadangan tidak dikenal.")
    return data


def verify_backup(backup: Path) -> VerifyResult:
    """Periksa hash, integritas snapshot database, jumlah baris, dan revisi migrasi."""
    problems: list[str] = []
    try:
        manifest = read_manifest(backup)
    except BackupError as e:
        return VerifyResult(False, [str(e)], None)
    for fname, meta in manifest["files"].items():
        if Path(fname).name != fname:
            problems.append(f"nama berkas tidak valid di manifest: {fname}")
            continue
        path = backup / fname
        if not path.is_file():
            problems.append(f"berkas hilang: {fname}")
        elif _sha256(path) != meta.get("sha256"):
            problems.append(f"hash tidak cocok (berkas berubah atau rusak): {fname}")
    if manifest.get("format") == 2:
        archive = backup / PG_DB_FILE
        if not archive.is_file() and not problems:
            problems.append(f"berkas database hilang: {PG_DB_FILE}")
        elif archive.is_file() and not problems:
            try:
                metadata = _models_metadata()
                known_tables = set(metadata.tables)
                counts: dict[str, int] = {table_name: 0 for table_name in known_tables}
                with gzip.open(archive, "rt", encoding="utf-8") as stream:
                    for line_no, line in enumerate(stream, 1):
                        record = json.loads(line)
                        table_name = record["table"]
                        if table_name not in known_tables or not isinstance(record.get("row"), dict):
                            raise ValueError(f"record tidak dikenal pada baris {line_no}")
                        counts[table_name] = counts.get(table_name, 0) + 1
                if counts != manifest.get("tables"):
                    problems.append("jumlah baris PostgreSQL tidak sesuai manifest")
            except (OSError, EOFError, ValueError, KeyError, gzip.BadGzipFile) as e:
                problems.append(f"snapshot PostgreSQL tidak terbaca: {e}")
    else:
        db = backup / DB_FILE
        if db.is_file() and not problems:
            if not integrity_ok(db):
                problems.append("uji integritas SQLite gagal")
            else:
                try:
                    if table_counts(db) != manifest.get("tables"):
                        problems.append("jumlah baris tabel tidak sesuai manifest")
                except sqlite3.DatabaseError as e:
                    problems.append(f"database tidak terbaca: {e}")
    return VerifyResult(not problems, problems, manifest)


def list_backups(backups_dir: Path) -> list[dict]:
    out: list[dict] = []
    if not backups_dir.exists():
        return out
    for d in sorted((p for p in backups_dir.iterdir() if p.is_dir() and not p.name.startswith(".")), reverse=True):
        try:
            m = read_manifest(d)
        except BackupError:
            out.append({"name": d.name, "valid": False})
            continue
        out.append({
            "name": d.name, "valid": True, "created_at": m.get("created_at"), "label": m.get("label"),
            "alembic_revision": m.get("alembic_revision"), "bytes": sum(f.get("bytes", 0) for f in m["files"].values()),
            "has_projects": PROJECTS_FILE in m["files"], "database_kind": m.get("database_kind", "sqlite"),
            "warnings": m.get("warnings", []),
        })
    return out


def prune_backups(backups_dir: Path, keep: int) -> list[str]:
    """Hapus cadangan lama, sisakan `keep` terbaru. Cadangan pre-restore tidak pernah dihapus otomatis."""
    if keep < 1:
        raise BackupError("keep harus minimal 1")
    dirs = sorted((p for p in backups_dir.iterdir() if p.is_dir() and not p.name.startswith(".") and not p.name.endswith("-pre-restore")),
                  reverse=True) if backups_dir.exists() else []
    removed = []
    for d in dirs[keep:]:
        shutil.rmtree(d)
        removed.append(d.name)
    return removed


def _live_db_locked(db: Path) -> bool:
    """True bila ada proses lain (mis. backend) yang sedang memakai database."""
    conn = sqlite3.connect(db, timeout=0.2)
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.rollback()
        return False
    except sqlite3.OperationalError:
        return True
    finally:
        conn.close()


def _safe_extract(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        for m in tar.getmembers():
            p = Path(m.name)
            if p.is_absolute() or ".." in p.parts or not (m.isfile() or m.isdir()):
                raise BackupError(f"arsip proyek berisi entri tidak aman: {m.name}")
        tar.extractall(dest, filter="data")


def _restore_project_archive(backup: Path, projects_dir: Path | None) -> bool:
    if projects_dir is None or not (backup / PROJECTS_FILE).exists():
        return False
    staging = projects_dir.with_name(projects_dir.name + ".restore-tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        _safe_extract(backup / PROJECTS_FILE, staging)
        if projects_dir.exists():
            shutil.move(projects_dir, projects_dir.with_name(f"{projects_dir.name}.replaced-{int(time.time())}"))
        os.replace(staging, projects_dir)
        return True
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _reset_postgres_sequences(conn, tables) -> None:
    from sqlalchemy import Integer

    preparer = conn.dialect.identifier_preparer
    for table in tables:
        for column in table.columns:
            if not (column.primary_key and column.autoincrement is True and isinstance(column.type, Integer)):
                continue
            sequence = conn.scalar(text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                                  {"table_name": table.name, "column_name": column.name})
            if sequence:
                table_sql = preparer.quote(table.name)
                column_sql = preparer.quote(column.name)
                conn.execute(text(f"SELECT setval(CAST(:sequence AS regclass), COALESCE(MAX({column_sql}), 1), COUNT(*) > 0) FROM {table_sql}"),
                             {"sequence": sequence})


def _restore_postgres(backup: Path, database_url: URL, backups_dir: Path, projects_dir: Path | None, *, force: bool,
                      app_version: str) -> dict:
    result = verify_backup(backup)
    if not result.ok:
        raise BackupError("Cadangan tidak valid: " + "; ".join(result.problems))
    manifest = result.manifest or {}
    revs, head = known_revisions()
    revision = manifest.get("alembic_revision")
    if revision not in revs:
        raise BackupError(f"Cadangan berasal dari revisi migrasi yang tidak dikenal: {revision}")
    if revision != head:
        raise BackupError("Cadangan harus dibuat dari revisi aplikasi saat ini sebelum dipulihkan.")

    metadata = _models_metadata()
    tables = list(metadata.sorted_tables)
    engine = _pg_engine(database_url)
    pre: Path | None = None
    try:
        with engine.connect() as connection:
            current_revision = _pg_revision(connection)
            if current_revision != head:
                raise BackupError("Jalankan alembic upgrade head sebelum memulihkan cadangan PostgreSQL.")
            current_counts = _pg_counts(connection, tables)
        has_data = any(current_counts.values())
        if has_data and not force:
            raise BackupError("Database tujuan berisi data. Gunakan --force untuk menimpa (cadangan pre-restore dibuat otomatis).")
        if force and has_data:
            pre = create_postgres_backup(database_url, backups_dir, projects_dir,
                                         include_projects=projects_dir is not None and projects_dir.exists(),
                                         label="pre-restore", app_version=app_version)

        with engine.begin() as connection:
            for table in reversed(tables):
                connection.execute(delete(table))

            buffers: dict[str, list[dict]] = {}
            with gzip.open(backup / PG_DB_FILE, "rt", encoding="utf-8") as stream:
                for line_no, line in enumerate(stream, 1):
                    record = json.loads(line)
                    table_name = record.get("table")
                    table = metadata.tables.get(table_name)
                    if table is None or not isinstance(record.get("row"), dict):
                        raise BackupError(f"Record PostgreSQL tidak valid pada baris {line_no}.")
                    values = record["row"]
                    if set(values) != set(table.columns.keys()):
                        raise BackupError(f"Kolom snapshot tidak cocok untuk tabel {table_name}.")
                    buffers.setdefault(table_name, []).append({
                        column.name: _decode_cell(values[column.name], column) for column in table.columns
                    })
                    if len(buffers[table_name]) >= 1000:
                        connection.execute(insert(table), buffers[table_name])
                        buffers[table_name] = []
            for table_name, rows in buffers.items():
                if rows:
                    connection.execute(insert(metadata.tables[table_name]), rows)
            _reset_postgres_sequences(connection, tables)
            restored_counts = _pg_counts(connection, tables)
            if restored_counts != manifest.get("tables"):
                raise BackupError("Jumlah baris setelah pemulihan tidak sesuai manifest; transaksi dibatalkan.")

        restored_projects = _restore_project_archive(backup, projects_dir)
        return {"restored_from": backup.name, "pre_restore": pre.name if pre else None, "projects": restored_projects,
                "alembic_revision": revision, "tables": restored_counts}
    finally:
        engine.dispose()


def restore_backup(backup: Path, db_path: Path | str | URL, backups_dir: Path, projects_dir: Path | None = None, *, force: bool = False,
                   app_version: str = "") -> dict:
    """Pulihkan database (dan folder proyek) dari cadangan. Backend harus berhenti.

    Menolak menimpa data yang ada tanpa `force`; dengan `force` selalu membuat cadangan `pre-restore` terlebih dahulu.
    """
    if isinstance(db_path, (str, URL)):
        url = make_url(db_path)
        if url.get_backend_name() == "postgresql":
            return _restore_postgres(backup, url, backups_dir, projects_dir, force=force, app_version=app_version)
        if url.get_backend_name() != "sqlite" or not url.database:
            raise BackupError("URL database pemulihan tidak didukung.")
        db_path = Path(url.database)
    result = verify_backup(backup)
    if not result.ok:
        raise BackupError("Cadangan tidak valid: " + "; ".join(result.problems))
    manifest = result.manifest or {}
    revs, _ = known_revisions()
    rev = manifest.get("alembic_revision")
    if rev is not None and rev not in revs:
        raise BackupError(f"Cadangan berasal dari versi aplikasi yang lebih baru (revisi {rev}); perbarui aplikasi dahulu.")

    pre: Path | None = None
    if db_path.exists():
        if not force:
            raise BackupError("Database tujuan sudah ada. Gunakan --force untuk menimpa (cadangan pre-restore dibuat otomatis).")
        if _live_db_locked(db_path):
            raise BackupError("Database sedang dipakai proses lain. Hentikan backend sebelum memulihkan.")
        pre = create_backup(db_path, backups_dir, projects_dir, include_projects=projects_dir is not None and projects_dir.exists(),
                            label="pre-restore", app_version=app_version)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = db_path.with_name(db_path.name + ".restore-tmp")
    shutil.copyfile(backup / DB_FILE, tmp_db)
    try:
        if not integrity_ok(tmp_db):
            raise BackupError("Salinan pemulihan gagal uji integritas.")
        for suffix in ("-wal", "-shm"):  # sisa jurnal lama tidak boleh dipasangkan dengan database hasil pulih
            Path(str(db_path) + suffix).unlink(missing_ok=True)
        os.replace(tmp_db, db_path)
    finally:
        tmp_db.unlink(missing_ok=True)

    restored_projects = False
    if projects_dir is not None and (backup / PROJECTS_FILE).exists():
        staging = projects_dir.with_name(projects_dir.name + ".restore-tmp")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        try:
            _safe_extract(backup / PROJECTS_FILE, staging)
            if projects_dir.exists():
                shutil.move(projects_dir, projects_dir.with_name(f"{projects_dir.name}.replaced-{int(time.time())}"))
            os.replace(staging, projects_dir)
            restored_projects = True
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    return {"restored_from": backup.name, "pre_restore": pre.name if pre else None, "projects": restored_projects,
            "alembic_revision": db_revision(db_path), "tables": table_counts(db_path)}
