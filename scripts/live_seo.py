"""Uji langsung Phase 14 dengan uvicorn + Ollama sungguhan: audit, riset kata kunci (volume hanya dari materi), brief, analitik.
Jalankan dari akar repo:  apps/api/.venv/Scripts/python scripts/live_seo.py
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
PORT, TOKEN = 8103, "token-live-seo-1234567890"
BASE, H = f"http://127.0.0.1:{PORT}", {"Authorization": f"Bearer {TOKEN}"}
HTML = "<html><head><title>Roihan</title></head><body><h1>A</h1><h1>B</h1><img src='x.png'></body></html>"
MATERIAL = "Data internal: 'jasa pembuatan website' dicari sekitar 1.900 per bulan, persaingan tinggi. Kata kunci 'aplikasi kasir' belum ada datanya."


def check(ok, msg):
    print(("[LULUS] " if ok else "[GAGAL] ") + msg)
    if not ok:
        raise SystemExit(1)


def done(tid, timeout=300):
    end = time.time() + timeout
    while time.time() < end:
        t = httpx.get(f"{BASE}/api/tasks/{tid}", headers=H, timeout=15).json()
        if t["status"] in {"completed", "failed", "blocked"}:
            return t
        time.sleep(0.5)
    raise SystemExit("timeout")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="live-seo-"))
    url = f"sqlite:///{(tmp / 'g.db').as_posix()}"
    subprocess.run([sys.executable, "-m", "alembic", "-x", f"url={url}", "upgrade", "head"], cwd=API, check=True, capture_output=True)
    env = {**os.environ, "APP_LOCAL_TOKEN": TOKEN, "DATABASE_URL": url, "DATA_DIR": str(tmp / "data"), "WORKER_ENABLED": "true", "BACKUP_ENABLED": "false",
           "OLLAMA_ENABLED": "true", "WORKER_POLL_INTERVAL_S": "0.5"}
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:get_app", "--factory", "--port", str(PORT), "--log-level", "warning"], cwd=API, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                if httpx.get(f"{BASE}/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        post = lambda path, body=None: httpx.post(f"{BASE}{path}", headers=H, json=body, timeout=30)  # noqa: E731
        t = done(post("/api/marketing/seo/tasks/audit", {"url": "https://x.example/", "html": HTML}).json()["task_id"], 60)
        check(t["status"] == "completed", "audit selesai tanpa model")
        t = done(post("/api/marketing/seo/tasks/keywords", {"topic": "layanan software house", "material": MATERIAL}).json()["task_id"])
        check(t["status"] == "completed", f"riset kata kunci selesai ({t['status']}, {t.get('last_error')})")
        t = done(post("/api/marketing/seo/tasks/brief", {"topic": "jasa pembuatan website", "material": MATERIAL}).json()["task_id"])
        print("   brief:", t["status"], t.get("last_error_kind"))
        t = done(post("/api/marketing/seo/tasks/analysis").json()["task_id"], 60)
        check(t["status"] == "completed", "laporan analitik selesai")
        arts = httpx.get(f"{BASE}/api/marketing/seo/artifacts", headers=H).json()
        kw = next(a for a in arts if a["kind"] == "keywords")
        items = httpx.get(f"{BASE}/api/marketing/seo/artifacts/{kw['id']}", headers=H).json()["data"]["items"]
        for i in items:
            print(f"   {i['keyword']!r}: volume={i['volume']} persaingan={i['competition']}")
        vols = [i["volume"] for i in items if i["volume"] is not None]
        check(all(v == 1900 for v in vols), "setiap volume tersimpan persis dari materi (tidak ada angka karangan)")
        check(all(i["volume"] is None for i in items if "kasir" in i["keyword"]), "kata kunci tanpa data tidak diberi angka")
        check(httpx.get(f"{BASE}/api/dashboard", headers=H).json()["ai"]["paid_calls_24h"] == 0, "tidak ada panggilan berbayar")
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    print("\nLIVE SEO LULUS")


if __name__ == "__main__":
    main()
