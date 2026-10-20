# Roihan Software House

Platform software house lokal berbasis AI: tim agent Engineering dan Marketing, model router, approval center, dan kantor virtual 3D.

Sumber acuan utama: [`docs/MASTER_DEVELOPMENT.md`](docs/MASTER_DEVELOPMENT.md). Baca dokumen itu sebelum mengubah kode.

## Status

Phase 0 sampai 3 selesai: backend FastAPI + SQLite + migration, frontend Next.js (Indonesia/Inggris), health check, manajemen proyek dan file (`/projects`), serta AI Control Center (`/ai`: provider, registri model, uji model lokal, log penggunaan, kebijakan biaya). Fitur agent belum tersedia.

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

AI lokal memerlukan Ollama berjalan dengan model `qwen2.5-coder:7b`. Panggilan API berbayar selalu diblokir. Setelah memperbarui kode, jalankan `pip install -r requirements.txt` dan `alembic upgrade head` lagi, lalu restart backend. File proyek disimpan di `data/projects/<id>/` (`input/` untuk dokumen sumber, `workspace/` untuk hasil kerja).

## Tes

```
cd apps/api && .venv/Scripts/python -m pytest
cd apps/web && npm test && npm run lint && npm run typecheck
```
