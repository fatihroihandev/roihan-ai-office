# Roihan Software House

Platform software house lokal berbasis AI: tim agent Engineering dan Marketing, model router, approval center, dan kantor virtual 3D.

Sumber acuan utama: [`docs/MASTER_DEVELOPMENT.md`](docs/MASTER_DEVELOPMENT.md). Baca dokumen itu sebelum mengubah kode.

## Status

Phase 0 sampai 7 selesai: backend FastAPI + SQLite + migration, frontend Next.js (Indonesia/Inggris), health check, manajemen proyek dan file (`/projects`), AI Control Center (`/ai`), serta task engine dengan Manager (`/tasks`: papan task real-time, status agent, rencana otomatis). Agent Analyst, Reporter, Developer, QA, dan Reviewer dapat bekerja (Developer, QA, dan Reviewer yang menjalankan tes hanya jika sandbox lolos uji isolasi); agent Marketing belum tersedia (task-nya diblokir secara jujur). Tindakan berisiko tinggi atau kritis tidak berjalan sebelum CEO menyetujuinya di Approval Center (`/approvals`). Katalog produk dengan Product Release Gate tersedia di `/products`: Marketing hanya boleh memakai klaim produk yang terverifikasi.

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

## Approval, review, dan laporan (Phase 6)

- **Approval Center** (`/approvals`): tindakan berisiko `high`/`critical` (mis. `spend`, `publish`, `external_outreach`, `delete_data`) berhenti di
  `pending_approval`. Persetujuan hanya dapat diberikan oleh manusia (pemegang token lokal), terikat pada isi tindakan (jika isi task berubah,
  persetujuan batal), berlaku untuk **satu kali** eksekusi, dan kedaluwarsa otomatis (`APPROVAL_TTL_HOURS`, bawaan 24 jam). Tindakan berisiko tidak
  pernah diulang otomatis; mengulangnya meminta approval baru. Setiap keputusan tercatat di `audit_logs`.
- **Reviewer** (aksi `review`): menilai berdasarkan bukti, bukan klaim. Bukti: diff Git, pemindaian keamanan statis, dan tes yang **dijalankan ulang
  sendiri** di sandbox. Verdict `approved` hanya jika tes ulang lulus, semua acceptance criteria terbukti (dengan bukti yang merujuk tes atau file
  nyata), dan tidak ada temuan berat. Hasil tersimpan di `code_reviews`.
- **Laporan**: setiap task yang selesai atau gagal otomatis menghasilkan `reports/<task-id>.md` dengan 15 bagian sesuai spesifikasi; seluruh fakta berasal
  dari database. Agent Reporter (aksi `report`) menyusun laporan proyek; ringkasannya boleh ditulis model, tetapi dibuang jika memuat angka yang tidak ada
  pada fakta. Laporan dapat dilihat di detail task dan halaman proyek.

## Katalog Produk dan Release Gate (Phase 7)

- **Katalog** (`/products`): produk milik sendiri dan layanan pengembangan dibedakan lewat `line`. Status pengembangan (`draft` sampai `archived`) melekat pada
  **versi**; status produk mengikuti versi terkininya.
- **Status dan izin pemasaran adalah dua hal berbeda.** Izin (`not_allowed`, `beta_only`, `allowed`) hanya dapat diberikan CEO, hanya jika Product Release Gate
  lulus, dan **dihitung ulang setiap dibaca**: jika bukti berubah (klaim disengketakan, status turun, harga berubah) izin otomatis tidak berlaku.
- **Klaim fitur** hanya `verified` jika punya bukti Engineering nyata: task implementasi yang selesai dan terverifikasi, tes yang lulus, tidak ada review yang
  menolak, dan commit-nya termasuk dalam commit yang di-pin pada versi. Klaim tanpa bukti ditandai **BELUM TERVERIFIKASI** beserta alasannya. CEO dapat
  menyatakan klaim secara manual (`attested`) dengan alasan tertulis; pernyataan itu tercatat di audit log dan dibedakan dari bukti sistem.
- **Ringkasan resmi untuk Marketing** (`GET /api/products/{id}/versions/{vid}/marketing-brief`) adalah satu-satunya sumber informasi produk yang boleh dipakai
  Marketing: hanya klaim terverifikasi (dan hanya jika diizinkan), batasan, harga yang disetujui, serta pernyataan wajib (mis. "produk ini masih beta").
  **Linter klaim** (`POST .../check-claims`) menolak draf teks yang menyinggung klaim belum terverifikasi, memakai klaim mutlak ("terbaik", "100%", "tanpa bug"),
  menyiratkan produk sudah rilis, tidak menyebut beta, atau menyebut harga yang belum disetujui.
- Setelah memperbarui kode, jalankan `alembic upgrade head` (ada tabel baru).

## Tes

```
cd apps/api && .venv/Scripts/python -m pytest
cd apps/web && npm test && npm run lint && npm run typecheck
```
