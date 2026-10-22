"""Evaluasi basis data (Phase 12): ukur SQLite (WAL) dan, bila diberi URL, PostgreSQL pada beban tulis/baca bersamaan.

Jalankan dari apps/api dengan venv proyek (SQLite) atau venv ber-psycopg (PostgreSQL):
    python ../../scripts/evaluate_db.py [--postgres postgresql+psycopg://user:pw@127.0.0.1:55432/roihan] [--seconds 6]
Setiap skenario: N penulis (maks. 8 agar tidak mengukur antrean pool koneksi 15) (transaksi pendek: satu task_event / proyek) + 2 pembaca (hitungan dan daftar) selama beberapa detik.
Mengukur throughput tulis, latensi p50/p95/p99, jumlah error "database terkunci", dan latensi kueri dashboard pada volume data besar.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

API = Path.cwd()
sys.path.insert(0, str(API))

import subprocess  # noqa: E402

from sqlalchemy import func, select  # noqa: E402

from app.db.models import Project, TaskEvent  # noqa: E402
from app.db.session import create_db_engine, create_session_factory  # noqa: E402


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * p))]


def scenario(url: str, writers: int, seconds: float) -> dict:
    engine = create_db_engine(url)
    sf = create_session_factory(engine)
    with sf() as s:
        pid = Project(name="evaluasi")
        s.add(pid)
        s.commit()
        project_id = pid.id
    stop = threading.Event()
    lat_w: list[float] = []
    lat_r: list[float] = []
    errors: list[str] = []
    lock = threading.Lock()

    def writer():
        while not stop.is_set():
            t0 = time.perf_counter()
            try:
                with sf() as s:
                    s.add(Project(name="w", description="x" * 200))
                    s.commit()
                dt = (time.perf_counter() - t0) * 1000
                with lock:
                    lat_w.append(dt)
            except Exception as e:  # noqa: BLE001
                with lock:
                    errors.append(type(e).__name__ + ": " + str(e).splitlines()[0][:60])

    def reader():
        while not stop.is_set():
            t0 = time.perf_counter()
            try:
                with sf() as s:
                    s.scalar(select(func.count()).select_from(Project))
                    s.execute(select(Project.id).order_by(Project.created_at.desc()).limit(20)).all()
                dt = (time.perf_counter() - t0) * 1000
                with lock:
                    lat_r.append(dt)
            except Exception as e:  # noqa: BLE001
                with lock:
                    errors.append(type(e).__name__ + ": " + str(e).splitlines()[0][:60])
            time.sleep(0.005)

    ts = [threading.Thread(target=writer) for _ in range(writers)] + [threading.Thread(target=reader) for _ in range(2)]
    t_start = time.perf_counter()
    for t in ts:
        t.start()
    time.sleep(seconds)
    stop.set()
    for t in ts:
        t.join()
    elapsed = time.perf_counter() - t_start
    engine.dispose()
    return {"writers": writers, "writes_per_s": round(len(lat_w) / elapsed), "write_p50_ms": round(pct(lat_w, 0.5), 1),
            "write_p95_ms": round(pct(lat_w, 0.95), 1), "write_p99_ms": round(pct(lat_w, 0.99), 1),
            "read_p95_ms": round(pct(lat_r, 0.95), 1), "errors": len(errors), "error_kinds": sorted(set(errors))[:3]}


def volume(url: str, rows: int) -> dict:
    """Latensi kueri tipikal dashboard setelah `rows` baris task_events (tahunan pemakaian berat ~ ratusan ribu)."""
    engine = create_db_engine(url)
    sf = create_session_factory(engine)
    with sf() as s:
        proj = Project(name="volume")
        s.add(proj)
        s.commit()
        from app.db.models import Task
        t = Task(project_id=proj.id, title="t", role="analyst", action_type="analysis")
        s.add(t)
        s.commit()
        tid, proj_id = t.id, proj.id
    batch = 5000
    t0 = time.perf_counter()
    with sf() as s:
        for i in range(0, rows, batch):
            s.bulk_insert_mappings(TaskEvent, [{"task_id": tid, "project_id": proj_id, "type": "status", "from_status": "queued", "to_status": "running", "reason": "uji"} for _ in range(batch)])
        s.commit()
    insert_s = time.perf_counter() - t0
    lat = []
    for _ in range(30):
        t1 = time.perf_counter()
        with sf() as s:
            s.scalar(select(func.count()).select_from(TaskEvent))
            s.execute(select(TaskEvent).where(TaskEvent.task_id == tid).order_by(TaskEvent.seq.desc()).limit(50)).all()
            s.execute(select(TaskEvent.to_status, func.count()).group_by(TaskEvent.to_status)).all()
        lat.append((time.perf_counter() - t1) * 1000)
    engine.dispose()
    return {"rows": rows, "bulk_insert_s": round(insert_s, 2), "dashboard_query_p50_ms": round(statistics.median(lat), 1),
            "dashboard_query_p95_ms": round(pct(lat, 0.95), 1)}


def run(label: str, url: str, seconds: float) -> None:
    print(f"\n=== {label} ===")
    for w in (1, 4, 8):
        print(" ", scenario(url, w, seconds))
    print(" ", volume(url, 200_000))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--postgres")
    ap.add_argument("--seconds", type=float, default=6)
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="evaldb-"))
    url = f"sqlite:///{(tmp / 'e.db').as_posix()}"
    subprocess.run([sys.executable, "-m", "alembic", "-x", f"url={url}", "upgrade", "head"], cwd=API, check=True, capture_output=True)
    run("SQLite WAL (busy_timeout 5 dtk)", url, a.seconds)
    if a.postgres:
        run("PostgreSQL 17", a.postgres, a.seconds)


if __name__ == "__main__":
    main()
