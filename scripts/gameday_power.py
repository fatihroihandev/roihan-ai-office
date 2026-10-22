"""Game day Office Power Control (Phase 13): OFF/ON dan crash pada proses uvicorn NYATA dengan Ollama sungguhan.

Skenario:
  A. OFF saat task berjalan -> PAUSED (checkpoint pause valid, task `interrupted`), backend dimatikan paksa saat PAUSED,
     dinyalakan ulang -> tetap PAUSED dan scheduler mati -> ON -> task dipulihkan dan selesai.
  B. Task berjalan lalu backend dimatikan paksa (kill -9) saat RUNNING -> startup recovery (checkpoint dipakai) -> task selesai.
  C. OFF/ON berulang tidak menggandakan pekerjaan: tepat satu percobaan `succeeded` per task.
Jalankan dari akar repo:  apps/api/.venv/Scripts/python scripts/gameday_power.py
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
PORT = 8102
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "token-gameday-1234567890"
H = {"Authorization": f"Bearer {TOKEN}"}
PROMPT = "Tulis enam kalimat pendek tentang pentingnya cadangan data untuk bisnis kecil."


def start(tmp: Path) -> subprocess.Popen:
    env = {**os.environ, "APP_LOCAL_TOKEN": TOKEN, "DATABASE_URL": f"sqlite:///{(tmp / 'g.db').as_posix()}", "DATA_DIR": str(tmp / "data"),
           "WORKER_ENABLED": "true", "BACKUP_ENABLED": "false", "OLLAMA_ENABLED": "true", "WORKER_POLL_INTERVAL_S": "0.5",
           "POWER_PAUSE_GRACE_S": "0", "POWER_CHECKPOINT_INTERVAL_S": "2"}
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:get_app", "--factory", "--port", str(PORT), "--log-level", "warning"],
                         cwd=API, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
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


def get(path: str):
    return httpx.get(f"{BASE}{path}", headers=H, timeout=15).json()


def post(path: str, body=None):
    return httpx.post(f"{BASE}{path}", headers=H, json=body, timeout=15)


def task(tid: str) -> dict:
    return get(f"/api/tasks/{tid}")


def wait(cond, what: str, timeout: float = 240, every: float = 0.4):
    end = time.time() + timeout
    while time.time() < end:
        v = cond()
        if v:
            return v
        time.sleep(every)
    raise SystemExit(f"timeout menunggu: {what}")


def check(ok: bool, msg: str) -> None:
    print(("[LULUS] " if ok else "[GAGAL] ") + msg)
    if not ok:
        raise SystemExit(1)


def new_task(pid: str, title: str) -> str:
    tid = post("/api/tasks", {"project_id": pid, "title": title, "role": "analyst", "action_type": "analysis", "description": PROMPT}).json()["id"]
    post(f"/api/tasks/{tid}/queue")
    return tid


def power_state() -> str:
    return get("/api/power")["state"]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="gameday-power-"))
    subprocess.run([sys.executable, "-m", "alembic", "-x", f"url=sqlite:///{(tmp / 'g.db').as_posix()}", "upgrade", "head"], cwd=API, check=True, capture_output=True)
    p = start(tmp)
    try:
        pid = post("/api/projects", {"name": "Game day power"}).json()["id"]

        print("\n== Skenario A: OFF saat task berjalan, crash saat PAUSED, ON ==")
        a = new_task(pid, "Tugas A")
        wait(lambda: task(a)["status"] == "running", "task A berjalan", 90)
        r = post("/api/power/off")
        check(r.status_code == 202 and r.json()["accepted"], "OFF diterima (202)")
        wait(lambda: power_state() == "PAUSED", "status PAUSED", 60)
        ta = task(a)
        check(ta["status"] == "interrupted", f"task A terputus terkontrol (status={ta['status']})")
        cps = get(f"/api/power/tasks/{a}/checkpoints")
        pause_cps = [c for c in cps if c["kind"] == "pause"]
        check(bool(pause_cps) and pause_cps[0]["valid"] is True, "checkpoint pause tersimpan dan valid")
        again = post("/api/power/off")
        check(again.status_code == 200 and again.json()["already"], "OFF berulang idempoten")
        time.sleep(3)
        check(task(a)["status"] == "interrupted", "scheduler mati: task tidak dijalankan saat PAUSED")
        print("   mematikan paksa backend saat PAUSED ...")
        kill9(p)
        p = start(tmp)
        st = get("/api/power")
        check(st["state"] == "PAUSED" and st["scheduling"] is False, "setelah restart tetap PAUSED dan scheduler mati")
        r = post("/api/power/on")
        check(r.status_code == 202, "ON diterima")
        wait(lambda: power_state() in {"RUNNING", "RECOVERY_REQUIRED"}, "ON selesai", 60)
        check(power_state() == "RUNNING", "kembali RUNNING tanpa item pemulihan")
        check(wait(lambda: task(a)["status"] == "completed", "task A selesai", 240) is True, "task A selesai setelah pemulihan")
        att = [x["status"] for x in task(a)["attempts"]]
        print("   percobaan A:", att)
        check(att.count("succeeded") == 1 and "interrupted" in att, "tepat satu percobaan sukses, percobaan terputus tercatat")
        log = get("/api/power/recovery/log")
        check(any(x["task_id"] == a and x["action"] == "resumed_from_checkpoint" and x["checkpoint_id"] for x in log), "riwayat pemulihan mencatat checkpoint yang dipakai")

        print("\n== Skenario B: crash saat RUNNING (kill -9) ==")
        b = new_task(pid, "Tugas B")
        wait(lambda: task(b)["status"] == "running", "task B berjalan", 90)
        time.sleep(3)  # beri waktu checkpoint berkala (interval 2 dtk)
        check(any(c["kind"] in {"start", "periodic"} for c in get(f"/api/power/tasks/{b}/checkpoints")), "checkpoint start/berkala sudah ada sebelum crash")
        kill9(p)
        p = start(tmp)
        wait(lambda: task(b)["status"] in {"queued", "running", "completed"}, "task B dipulihkan", 60)
        events = [(e["to_status"], e.get("reason")) for e in task(b)["events"]]
        print("   riwayat B:", events)
        check(("interrupted", "crash_recovery") in events and ("queued", "resumed") in events, "crash terdeteksi saat startup dan task dipulihkan")
        check(wait(lambda: task(b)["status"] == "completed", "task B selesai", 240) is True, "task B selesai")
        check(power_state() == "RUNNING", "status akhir RUNNING")

        print("\n== Skenario C: OFF/ON berulang ==")
        c = new_task(pid, "Tugas C")
        wait(lambda: task(c)["status"] == "running", "task C berjalan", 90)
        for i in range(2):
            post("/api/power/off")
            wait(lambda: power_state() == "PAUSED", "PAUSED", 60)
            post("/api/power/on")
            wait(lambda: power_state() in {"RUNNING", "RECOVERY_REQUIRED"}, "ON", 60)
            time.sleep(1)
        wait(lambda: task(c)["status"] == "completed", "task C selesai", 300)
        done = [x for x in task(c)["attempts"] if x["status"] == "succeeded"]
        check(len(done) == 1, f"tepat satu percobaan sukses setelah OFF/ON berulang (percobaan: {[x['status'] for x in task(c)['attempts']]})")
        check(power_state() == "RUNNING", "status akhir RUNNING")
        usage = get("/api/dashboard")["ai"]
        print(f"   pemakaian AI tercatat: {usage['calls_24h']} panggilan, berbayar {usage['paid_calls_24h']}")
        check(usage["paid_calls_24h"] == 0, "tidak ada panggilan berbayar")
    finally:
        kill9(p)
    print("\nGAME DAY POWER LULUS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
