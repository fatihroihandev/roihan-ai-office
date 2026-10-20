# Roihan Software House

Platform software house lokal berbasis AI: tim agent Engineering dan Marketing, model router, approval center, dan kantor virtual 3D.

Sumber acuan utama: [`docs/MASTER_DEVELOPMENT.md`](docs/MASTER_DEVELOPMENT.md). Baca dokumen itu sebelum mengubah kode.

## Status

Phase 0 sampai 5 (kode selesai; verifikasi sandbox langsung menunggu distro WSL): backend FastAPI + SQLite + migration, frontend Next.js (Indonesia/Inggris), health check, manajemen proyek dan file (`/projects`), AI Control Center (`/ai`), serta task engine dengan Manager (`/tasks`: papan task real-time, status agent, rencana otomatis). Agent Analyst, Reporter, Developer, dan QA dapat bekerja (Developer dan QA hanya jika sandbox lolos uji isolasi); Reviewer dan Marketing belum tersedia (task-nya diblokir secara jujur).

## Prasyarat Phase 0

- Python 3.10+ (diuji dengan 3.15)
- Node.js 20+ (diuji dengan 24)
- Git
- [Ollama](https://ollama.com) dengan model `qwen2.5-coder:7b` (`ollama pull qwen2.5-coder:7b`)

## Benchmark model lokal

```
python scripts/benchmark_ollama.py --model qwen2.5-coder:7b
```

Opsi: `--runs-json 20`, `--skip-json`, `--skip-code`, `--skip-bugfix`. Hasil mentah disimpan di `data/benchmarks/` (struktur, prompt, versi model, dan output).

Kode hasil model dijalankan sebagai subprocess lokal dengan timeout dan filter impor berbahaya. Ini **bukan sandbox**; sandbox sebenarnya dikerjakan di Phase 5.

## Konfigurasi

Salin `.env.example` ke `.env`, lalu isi `APP_LOCAL_TOKEN` dengan nilai acak (minimal 16 karakter), misalnya:

```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Secret tidak boleh di-commit. Backend dan frontend sama-sama membaca `.env` di root repository.

## Menjalankan

Backend (`apps/api`):

```
cd apps/api
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8000
```

Frontend (`apps/web`):

```
cd apps/web
npm install
npm run dev
```

Buka http://localhost:3000. Token lokal hanya dipakai di sisi server Next.js (proxy `/api/health`) dan tidak dikirim ke browser.

Endpoint backend: `GET /api/health` (publik, minimal). Semua endpoint lain, termasuk `/api/health/details` dan `/api/projects/*`, memerlukan `Authorization: Bearer <APP_LOCAL_TOKEN>`. Dokumentasi interaktif: http://127.0.0.1:8000/docs.

Worker task berjalan di dalam proses backend (matikan dengan `WORKER_ENABLED=false`). Pembaruan real-time memakai WebSocket langsung ke `ws://127.0.0.1:8000`; jika port backend berbeda, set `NEXT_PUBLIC_API_WS_URL` di `apps/web/.env.local`. Tindakan berisiko tinggi tertahan di `pending_approval` sampai Approval Center (Phase 6) tersedia.

AI lokal memerlukan Ollama berjalan dengan model `qwen2.5-coder:7b`. Panggilan API berbayar selalu diblokir. Setelah memperbarui kode, jalankan `pip install -r requirements.txt` dan `alembic upgrade head` lagi, lalu restart backend. File proyek disimpan di `data/projects/<id>/` (`input/` untuk dokumen sumber, `workspace/` untuk hasil kerja).

## Sandbox eksekusi kode (Phase 5)

Kode hasil AI **tidak pernah dijalankan di Windows Anda**. Developer dan QA hanya menulis file di workspace proyek
(`data/projects/<id>/workspace/source-code`, dicatat dengan Git) lalu meminta perintah dari daftar yang diizinkan
(`pytest`, `python_file`, `compile`). Eksekusinya berjalan di distro WSL2 khusus, dan task Developer/QA diblokir
(`sandbox_disabled`) sampai sandbox siap dan lolos uji isolasi otomatis.

Menyiapkan sandbox (sekali saja; Ubuntu asli Anda tidak diubah, skrip menyalinnya menjadi distro `roihan-sandbox`):

```
wsl --install -d Ubuntu          # jika belum ada
powershell -ExecutionPolicy Bypass -File scripts\setup_sandbox_wsl.ps1
```

Lalu isi `.env`: `SANDBOX_BACKEND=wsl` dan `SANDBOX_WSL_DISTRO=roihan-sandbox`, restart backend, dan buka halaman **Task**
untuk melihat status sandbox dan hasil uji isolasi. Lapisan isolasi: tanpa jaringan, user tanpa hak khusus, environment
kosong (tanpa secret), batas memori/proses/CPU/waktu, tanpa mount drive Windows, tanpa interop Windows.

## Tes

```
cd apps/api && .venv/Scripts/python -m pytest
cd apps/web && npm test && npm run lint && npm run typecheck
```
