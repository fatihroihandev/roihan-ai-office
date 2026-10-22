"""Game day (Fase 11): matikan paksa backend di tengah task yang sedang berjalan, nyalakan ulang, dan buktikan pemulihannya.

Memakai proses uvicorn NYATA, database sementara, dan Ollama lokal sungguhan. Jalankan dari akar repo:
    apps/api/.venv/Scripts/python scripts/gameday_restart.py
Lulus bila: (1) task yang terputus menjadi `interrupted` lalu `queued/recovered` dan akhirnya selesai, (2) percobaan lama tercatat
`interrupted`, (3) data proyek masih ada setelah mati paksa, (4) cadangan yang diambil saat berjalan dapat diverifikasi.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
PORT = 8101
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "token-gameday-1234567890"
H = {"Authorization": f"Bearer {TOKEN}"}


def start(tmp: Path) -> subprocess.Popen:
    env = {**os.environ, "APP_LOCAL_TOKEN": TOKEN, "DATABASE_URL": f"sqlite:///{(tmp / 'g.db').as_posix()}", "DATA_DIR": str(tmp / "data"),
           "WORKER_ENABLED": "true", "BACKUP_ENABLED": "false", "OLLAMA_ENABLED": "true", "WORKER_POLL_INTERVAL_S": "0.5"}
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:get_app", "--factory", "--port", str(PORT), "--log-level", "warning"],
                         cwd=API, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            if httpx.get(f"{BASE}/api/health", timeout=1).status_code == 200:
                return p
        except httpx.HTTPError:
            time.sleep(0.5)
    p.kill()
    raise SystemExit("backend tidak mau naik")


def kill9(p: subprocess.Popen) -> None:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)  # setara kill -9: tanpa shutdown bersih
    p.wait()


def task(tid: str) -> dict:
    return httpx.get(f"{BASE}/api/tasks/{tid}", headers=H, timeout=10).json()


def wait(tid: str, want: set[str], timeout: float) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        t = task(tid)
        if t["status"] in want:
            return t
        time.sleep(0.5)
    raise SystemExit(f"timeout menunggu {want}; status terakhir: {task(tid)['status']}")


def check(ok: bool, msg: str) -> None:
    print(("[LULUS] " if ok else "[GAGAL] ") + msg)
    if not ok:
        raise SystemExit(1)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="gameday-"))
    subprocess.run([sys.executable, "-m", "alembic", "-x", f"url=sqlite:///{(tmp / 'g.db').as_posix()}", "upgrade", "head"], cwd=API, check=True,
                   capture_output=True)
    p = start(tmp)
    try:
        pid = httpx.post(f"{BASE}/api/projects", json={"name": "Game day"}, headers=H).json()["id"]
        tid = httpx.post(f"{BASE}/api/tasks", headers=H, json={
            "project_id": pid, "title": "Analisis risiko restart", "role": "analyst", "action_type": "analysis",
            "description": "Sebutkan tiga risiko kegagalan sistem lokal dalam tiga kalimat pendek."}).json()["id"]
        httpx.post(f"{BASE}/api/tasks/{tid}/queue", headers=H).raise_for_status()
        wait(tid, {"running"}, 60)
        print("task berjalan; mematikan paksa backend ...")
        kill9(p)

        p = start(tmp)
        check(httpx.get(f"{BASE}/api/projects/{pid}", headers=H).json()["name"] == "Game day", "data proyek utuh setelah mati paksa")
        t = wait(tid, {"completed", "failed", "interrupted"}, 240)
        events = [(e["to_status"], e.get("reason")) for e in task(tid).get("events", [])]
        print("riwayat status:", events)
        attempts = [a["status"] for a in task(tid).get("attempts", [])]
        print("percobaan:", attempts)
        check(("interrupted", "worker_restart") in events, "task terputus tercatat sebagai interrupted (worker_restart)")
        check(("queued", "recovered") in events, "task idempoten dipulihkan ke antrean")
        check("interrupted" in attempts, "percobaan lama ditandai interrupted")
        check(t["status"] == "completed", "task selesai setelah pemulihan")

        sys.path.insert(0, str(API))
        from app.backup import service as svc
        b = svc.create_backup(tmp / "g.db", tmp / "data" / "backups", tmp / "data" / "projects", label="gameday")
        check(svc.verify_backup(b).ok, "cadangan yang diambil saat backend hidup valid")
    finally:
        kill9(p)
    print("\nGAME DAY LULUS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
