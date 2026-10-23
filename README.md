# Roihan Software House

Platform software house lokal berbasis AI: tim agent Engineering dan Marketing, model router, approval center, dan kantor virtual 3D.

Sumber acuan utama: [`docs/MASTER_DEVELOPMENT.md`](docs/MASTER_DEVELOPMENT.md). Baca dokumen itu sebelum mengubah kode.

## Status

Phase 0 sampai 7 selesai: backend FastAPI + PostgreSQL + migration, frontend Next.js (Indonesia/Inggris), health check, manajemen proyek dan file (`/projects`), AI Control Center (`/ai`), serta task engine dengan Manager (`/tasks`: papan task real-time, status agent, rencana otomatis). Agent Analyst, Reporter, Developer, QA, dan Reviewer dapat bekerja (Developer, QA, dan Reviewer yang menjalankan tes hanya jika sandbox lolos uji isolasi); agent Marketing belum tersedia (task-nya diblokir secara jujur). Tindakan berisiko tinggi atau kritis tidak berjalan sebelum CEO menyetujuinya di Approval Center (`/approvals`). Katalog produk dengan Product Release Gate tersedia di `/products`: Marketing hanya boleh memakai klaim produk yang terverifikasi.

Roadmap lanjutan (Master Development v2.3): **Phase 13** Office Power Control dan **Phase 14** SEO Specialist selesai. **Phase 15** aktif kembali atas instruksi CEO; kandidat MVP dan bukti QA ada di workspace proyek terisolasi. Belum siap rilis: penerima/SMTP kontak dan domain/hosting belum dikonfigurasi, Reviewer memberi `changes_requested`, dan belum ada persetujuan rilis publik. Spesifikasi: `docs/MASTER_DEVELOPMENT.md` Bagian 29. **Cara penggunaan: `docs/PANDUAN_PENGGUNAAN.md`.**

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

Backend memakai PostgreSQL. Siapkan database `roihan` dan user, lalu sesuaikan `DATABASE_URL` di `.env` dengan kredensial lokal Anda. Untuk cutover dari SQLite: hentikan backend dan simpan salinan `data/database/roihan.db`; dari `apps/api`, naikkan skema sumber ke head dengan `python -m alembic -x url=<sqlite-url> upgrade head`, lalu naikkan skema PostgreSQL dengan `python -m alembic upgrade head` saat `DATABASE_URL` menunjuk ke PostgreSQL. Dari root repo, salin data dengan `apps/api/.venv/Scripts/python scripts/migrate_sqlite_to_postgres.py <sqlite-url> <postgres-url>`. Tujuan harus database kosong yang sudah dimigrasikan. Setelah salinan berhasil, mulai backend. Backup otomatis mencakup snapshot PostgreSQL terkompresi dan arsip folder proyek; pemulihan PostgreSQL dijalankan lewat CLI saat backend berhenti.

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

## Marketing dan Sales (Phase 8)

- **Halaman `/marketing`**: kebijakan data prospek, metrik, pipeline, peluang, draf outreach, intake prospek dari teks, dan riset pasar. Detail prospek di
  `/marketing/leads/[id]` (asal data, rincian skor, interaksi, tindakan).
- **Sumber dan privasi**: prospek hanya dari sumber yang diizinkan dan tercatat asalnya; data sensitif dan email pribadi ditolak; kontak disamarkan secara bawaan
  dan membukanya tercatat di audit. Yang menolak (opt-out) masuk daftar jangan-hubungi (hash) dan tidak dapat didaftarkan ulang.
- **Agent hanya mengusulkan**: Lead Generation mengekstrak hanya dari teks yang Anda tempel (fakta yang tidak ada di teks dibuang); Market Research menandai temuan
  tanpa bukti sebagai belum terverifikasi; Sales menyusun draf dari ringkasan resmi produk dan wajib lolos linter klaim. **Tidak ada pengiriman otomatis**: Anda yang
  mengirim, lalu mencatat "sudah saya kirim". Perpindahan tahap prospek memerlukan interaksi nyata yang Anda catat.
- Kebijakan sumber dan retensi (`LEAD_*` di `.env`) adalah **usulan bawaan** yang perlu dikonfirmasi CEO; lihat Bagian 27 di dokumen master.
- Setelah memperbarui kode, jalankan `alembic upgrade head` (ada tabel baru dan kolom `tasks.params`), lalu mulai ulang backend.

## Konten, kampanye, dan tindakan eksternal (Phase 9)

- **Halaman `/marketing/content`**: kotak keluar, kampanye, dan Content Workspace. Content Agent menyusun draf hanya dari ringkasan resmi produk dan wajib lolos
  pemeriksaan klaim; produk yang belum diizinkan dipromosikan ditolak.
- **Publikasi dan pengiriman outreach selalu memerlukan approval Anda** atas isi yang persis sama (kartu Approval menampilkan isinya). Jika isi berubah, izin produk
  dicabut, prospek menolak, atau batas harian/jarak antar pesan terlampaui, tindakan gagal tanpa efek. **Tidak ada pengiriman otomatis**: hasil yang disetujui masuk
  **kotak keluar**; Anda yang mengirim lalu menekan "Sudah saya kirim/publikasikan".
- **Kampanye**: tanpa iklan berbayar (anggaran 0). Angka kinerja dicatat manual; ROI baru muncul jika biaya dan pendapatan tercatat.
- **Serah-terima klien**: pada peluang yang menang, tombol "Serahkan ke Engineering" membuat proyek dengan dokumen kebutuhan dan task draft (analisis, perencanaan)
  yang baru berjalan setelah Anda mengantrekannya.
- Batas (`OUTREACH_*`, `CONTENT_*` di `.env`) adalah usulan bawaan yang perlu dikonfirmasi CEO. Setelah memperbarui kode, jalankan `alembic upgrade head`.

## Kantor virtual dan dashboard (Phase 10)

- **Halaman `/office`** (menu "Kantor"): kantor cyberpunk 3D dengan CEO Office, Engineering, Marketing, Meeting Room, dan Lounge, ditambah panel **Ringkasan CEO**
  (approval dan keputusan yang menunggu, task, Marketing, pemakaian AI, status worker). Status avatar hanya berasal dari backend: agent tanpa task aktif berada di
  Lounge dan tidak pernah tampak bekerja.
- **Mode tampilan**: Otomatis, 3D, atau 2D. 2D (kartu per ruangan) dipakai otomatis jika WebGL tidak tersedia, gerak berkurang diminta sistem operasi, atau 3D gagal.
- **Realtime**: lencana "Realtime" berarti WebSocket tersambung; jika terputus, data dimuat berkala dan potret terakhir ditandai usang sampai tersambung lagi.
- Tidak ada perubahan database pada fase ini; cukup mulai ulang backend dan jalankan `npm install` di `apps/web` (ada paket `three` dan `@react-three/fiber`).

## Backup, pemulihan, dan keamanan (Phase 11)

- **Cadangan otomatis** setiap 24 jam (dan saat backend mulai) ke `data/backups/<waktu>-auto/` (database + folder proyek + `manifest.json`); 14 terbaru disimpan. Atur lewat `BACKUP_*` di `.env`. **Salin folder ini ke disk lain secara berkala.**
- Perintah (dari `apps/api`):
  ```
  .venv/Scripts/python -m app.backup create            # cadangan manual
  .venv/Scripts/python -m app.backup list
  .venv/Scripts/python -m app.backup verify <nama>     # periksa hash + integritas
  ```
- **Memulihkan**: hentikan backend, lalu `.venv/Scripts/python -m app.backup restore <nama> --force`. Keadaan sebelumnya otomatis diselamatkan sebagai cadangan `...-pre-restore`. Setelah itu jalankan backend: task yang terputus dipulihkan oleh worker.
- Uji bencana nyata (proses mati paksa saat task berjalan): `apps/api/.venv/Scripts/python scripts/gameday_restart.py` (butuh Ollama).
- Audit keamanan: `python scripts/audit_security.py --deps`; ringkasan ancaman dan temuan di `docs/SECURITY.md`.
- Profil 3D: buka `/office?perf=1` untuk melihat FPS dan draw call; efek turun ke "Rendah" otomatis jika perangkat lambat.
- Tidak ada migrasi database; cukup mulai ulang backend dan frontend.

## Office Power Control (Phase 13)

Di halaman **Kantor** ada tombol **OFF/ON**: OFF menghentikan penjadwalan, menyimpan checkpoint pekerjaan yang berjalan, dan baru menampilkan **DIJEDA** setelah backend memverifikasi; ON memvalidasi lalu memulihkan pekerjaan dari checkpoint.
Pekerjaan berisiko atau operasi eksternal yang hasilnya tidak pasti tidak diulang otomatis: muncul di panel CEO sebagai **Butuh tindakan manual** untuk Anda putuskan.
Jika aplikasi atau laptop mati mendadak, pemulihan berjalan otomatis saat backend dinyalakan lagi. Jalankan migrasi `alembic upgrade head` (revisi 0010) lalu mulai ulang backend dan frontend.
Atur lewat `POWER_*` di `.env`. Uji bencana nyata: `apps/api/.venv/Scripts/python scripts/gameday_power.py` (butuh Ollama).

## SEO & Digital Marketing (Phase 14)

Menu **Marketing -> SEO & Digital Marketing** (`/marketing/seo`): audit SEO teknis dari HTML yang ditempel, riset kata kunci dan brief konten (volume hanya dari materi Anda), laporan analitik, serta pencatatan metrik pencarian manual. Data yang belum ada tampil "belum ada data", bukan nol. Hasil hanya usulan; rekomendasi teknis dapat dijadikan task draft Engineering. Jalankan `alembic upgrade head` (revisi 0011), lalu mulai ulang backend dan frontend. Uji langsung: `apps/api/.venv/Scripts/python scripts/live_seo.py`.

## Situs yang dipasarkan (portofolio CEO)

Situs pribadi (`fatihroihan.site`, kode di `C:\xampp\htdocs\fatih-roihan-portofolio`) sudah terdaftar: kode sumbernya **disalin** ke proyek "Situs: Portofolio Fatih Roihan" (folder asli tidak diubah). Menu **Marketing -> SEO & Digital Marketing -> Situs yang dipasarkan** untuk audit situs, riset kata kunci, dan brief konten berdasarkan isi situs. Mendaftarkan situs lain: `cd apps/api && .venv\Scripts\python -m app.marketing.import_site --name "Nama" --url https://situs.com --path C:\folder\situs`. Jalankan `alembic upgrade head` (revisi 0012) setelah memperbarui kode.

## Akses web untuk agent

Di **AI Control Center -> Akses web agent**: nyalakan saklar, isi API key Brave Search (gratis di brave.com/search/api), atur batas harian, lalu **Uji pencarian**. Setelah itu di **Marketing -> Cari dari web** Anda bisa meminta agent mencari prospek atau riset pasar. Model tidak terhubung ke internet; backend yang mengambil halaman (patuh robots.txt, alamat lokal diblokir, semua tercatat). Jalankan `alembic upgrade head` (revisi 0013) sebelum memakainya.

## Navigasi layar penuh

Tidak ada bilah navigasi: gunakan **tombol menu melayang** (klik, atau tekan `M`; `Esc` menutup). Tombol dapat diseret ke tepi kiri/kanan dan posisinya diingat di peramban.

## Evaluasi cloud (Phase 12)

Hasil evaluasi awal ada di `docs/CLOUD_EVALUATION.md`. Alat evaluasi: `scripts/evaluate_db.py` (benchmark SQLite/PostgreSQL), `scripts/estimate_cloud_cost.py`,
dan `TEST_POSTGRES_URL=... pytest` untuk menjalankan seluruh tes pada PostgreSQL.

## Tes

```
cd apps/api && .venv/Scripts/python -m pytest
cd apps/web && npm test && npm run lint && npm run typecheck
```

## License

This project is proprietary software. The source code is publicly available for viewing and evaluation only.

No license is granted for reuse, modification, redistribution, or commercial use without prior written permission from the copyright holder, except where permitted by applicable law.

See [LICENSE](./LICENSE) for details. Third-party components remain subject to their respective licenses.