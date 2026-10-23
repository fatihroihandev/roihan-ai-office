import hashlib
import io
import json
import sqlite3
import tarfile
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.backup import service as svc
from app.backup.__main__ import main as cli_main
from app.main import create_app

INSERT = ("INSERT INTO projects (id, name, description, status, created_at, updated_at) "
          "VALUES (?,?,?,?,datetime('now'),datetime('now'))")


def _db(settings) -> Path:
    return Path(make_url(settings.database_url).database)


def _seed(db: Path, n: int = 3) -> None:
    conn = sqlite3.connect(db)
    for i in range(n):
        conn.execute(INSERT, (f"p{i}", f"Proyek {i}", "uji", "active"))
    conn.commit()
    conn.close()


def _count(db: Path, table: str = "projects") -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def env(settings):
    db = _db(settings)
    settings.projects_dir.mkdir(parents=True)
    (settings.projects_dir / "p0").mkdir()
    (settings.projects_dir / "p0" / "readme.txt").write_text("isi proyek", encoding="utf-8")
    _seed(db)
    return db, settings.data_dir / "backups", settings.projects_dir


def test_roundtrip_restore_to_fresh_database(env, tmp_path):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    assert svc.verify_backup(b).ok
    m = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    assert m["tables"]["projects"] == 3 and m["alembic_revision"]

    target = tmp_path / "pulih" / "roihan.db"
    out = svc.restore_backup(b, target, backups, tmp_path / "pulih" / "projects")
    assert _count(target) == 3 and svc.integrity_ok(target)
    assert out["projects"]
    assert (tmp_path / "pulih" / "projects" / "p0" / "readme.txt").read_text(encoding="utf-8") == "isi proyek"
    assert svc.table_counts(target) == svc.table_counts(db)


def test_restore_refuses_to_overwrite_without_force(env):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    with pytest.raises(svc.BackupError, match="--force"):
        svc.restore_backup(b, db, backups, projects)


def test_force_restore_makes_pre_restore_copy_and_rolls_back_data(env):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM projects WHERE id='p0'")
    conn.commit()
    conn.close()
    assert _count(db) == 2
    out = svc.restore_backup(b, db, backups, projects, force=True)
    assert _count(db) == 3
    pre = backups / out["pre_restore"]
    assert pre.name.endswith("-pre-restore") and _count(pre / "roihan.db") == 2  # keadaan sebelum pemulihan terselamatkan


def test_tampered_database_is_detected_and_refused(env, tmp_path):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    with (b / "roihan.db").open("r+b") as f:
        f.seek(2000)
        f.write(b"\x00\xffRUSAK")
    res = svc.verify_backup(b)
    assert not res.ok and any("hash" in p for p in res.problems)
    target = tmp_path / "x.db"
    with pytest.raises(svc.BackupError, match="tidak valid"):
        svc.restore_backup(b, target, backups, None)
    assert not target.exists()


def test_missing_file_and_bad_manifest(env):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    (b / "projects.tar.gz").unlink()
    assert any("hilang" in p for p in svc.verify_backup(b).problems)
    (b / "manifest.json").write_text("bukan json", encoding="utf-8")
    assert not svc.verify_backup(b).ok


def test_manifest_path_traversal_is_rejected(env):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    m = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    m["files"]["../../etc/passwd"] = {"sha256": "x", "bytes": 1}
    (b / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    assert any("tidak valid" in p for p in svc.verify_backup(b).problems)


def test_backup_from_newer_schema_is_refused(env, tmp_path):
    db, backups, projects = env
    conn = sqlite3.connect(db)
    conn.execute("UPDATE alembic_version SET version_num='9999_masa_depan'")
    conn.commit()
    conn.close()
    b = svc.create_backup(db, backups, projects)
    with pytest.raises(svc.BackupError, match="lebih baru"):
        svc.restore_backup(b, tmp_path / "y.db", backups, None)


def test_restore_refuses_while_database_is_in_use(env):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    holder = sqlite3.connect(db)
    holder.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(svc.BackupError, match="dipakai"):
            svc.restore_backup(b, db, backups, projects, force=True)
    finally:
        holder.rollback()
        holder.close()


def test_restore_discards_stale_wal(env):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    wal = Path(str(db) + "-wal")
    wal.write_bytes(b"sisa-jurnal-lama")
    svc.restore_backup(b, db, backups, projects, force=True)
    assert not wal.exists() or wal.read_bytes() != b"sisa-jurnal-lama"
    assert svc.integrity_ok(db) and _count(db) == 3


def test_unsafe_project_archive_is_rejected(env, tmp_path):
    db, backups, projects = env
    b = svc.create_backup(db, backups, projects)
    evil = b / "projects.tar.gz"
    with tarfile.open(evil, "w:gz") as tar:
        info = tarfile.TarInfo("../keluar.txt")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    m = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    m["files"]["projects.tar.gz"] = {"sha256": hashlib.sha256(evil.read_bytes()).hexdigest(), "bytes": evil.stat().st_size}
    (b / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(svc.BackupError, match="tidak aman"):
        svc.restore_backup(b, tmp_path / "z.db", backups, tmp_path / "zp")
    assert not (tmp_path / "keluar.txt").exists()


def test_symlinks_not_archived_and_size_cap_warns(env, tmp_path):
    db, backups, projects = env
    outside = tmp_path / "rahasia.txt"
    outside.write_text("rahasia", encoding="utf-8")
    try:
        (projects / "tautan").symlink_to(outside)
    except OSError:
        pytest.skip("symlink tidak diizinkan")
    b = svc.create_backup(db, backups, projects)
    with tarfile.open(b / "projects.tar.gz") as tar:
        assert "tautan" not in tar.getnames()
    capped = svc.create_backup(db, backups, projects, max_project_bytes=1)
    m = svc.read_manifest(capped)
    assert "projects.tar.gz" not in m["files"] and m["warnings"]


def test_backup_during_concurrent_writes_is_consistent(env):
    db, backups, _ = env
    stop = threading.Event()

    def writer():
        conn = sqlite3.connect(db, timeout=10)
        i = 100
        while not stop.is_set():
            conn.execute(INSERT, (f"w{i}", "tulis", "x", "active"))
            conn.commit()
            i += 1
        conn.close()

    t = threading.Thread(target=writer)
    t.start()
    try:
        made = [svc.create_backup(db, backups, None, label=f"c{n}") for n in range(5)]
    finally:
        stop.set()
        t.join()
    for b in made:
        assert svc.verify_backup(b).ok


def test_prune_keeps_newest_and_never_deletes_pre_restore(env):
    db, backups, _ = env
    names = [svc.create_backup(db, backups, None, label=f"auto{n}").name for n in range(4)]
    pre = svc.create_backup(db, backups, None, label="pre-restore")
    removed = svc.prune_backups(backups, 2)
    left = {p.name for p in backups.iterdir()}
    assert len(removed) == 2 and pre.name in left and names[-1] in left
    with pytest.raises(svc.BackupError):
        svc.prune_backups(backups, 0)


def test_list_marks_invalid_backups(env):
    db, backups, _ = env
    svc.create_backup(db, backups, None)
    (backups / "20200101T000000-rusak").mkdir()
    assert {i["valid"] for i in svc.list_backups(backups)} == {True, False}


def test_api_requires_token_and_roundtrip(settings, auth):
    c = TestClient(create_app(settings))
    assert c.get("/api/backups").status_code == 401
    assert c.post("/api/backups").status_code == 401
    r = c.post("/api/backups", headers=auth)
    assert r.status_code == 201
    name = r.json()["name"]
    assert [i["name"] for i in c.get("/api/backups", headers=auth).json()["items"]] == [name]
    assert c.post(f"/api/backups/{name}/verify", headers=auth).json()["ok"] is True
    assert c.post("/api/backups/..%2F..%2Fx/verify", headers=auth).status_code == 404
    assert c.post("/api/backups/20200101T000000-nihil/verify", headers=auth).status_code == 404


def test_cli_create_verify_restore(settings, monkeypatch, capsys):
    _seed(_db(settings))
    monkeypatch.setattr("app.backup.__main__.get_settings", lambda: settings)
    assert cli_main(["create"]) == 0
    name = next((settings.data_dir / "backups").iterdir()).name
    assert cli_main(["verify", name]) == 0
    assert cli_main(["restore", name]) == 1  # menolak menimpa tanpa --force
    assert "--force" in capsys.readouterr().err
    assert cli_main(["restore", name, "--force"]) == 0
    assert cli_main(["verify", "tidak-ada"]) == 1


def test_security_headers_on_api(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store" and r.headers["referrer-policy"] == "no-referrer"
