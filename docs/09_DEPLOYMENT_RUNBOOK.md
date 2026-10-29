# 9. DEPLOYMENT RUNBOOK (ONLINE Rp0 & LOCAL)

**Nama Produk:** Roihan AI Office  
**Arsitektur Deployment:** Zero-Cost Cloud (Vercel Free + Render Free + Neon Serverless PostgreSQL) & Local Mode  
**Dokumen Acuan:** Addendum v2.1 — Online Deployment, Single-Owner Access & Zero-Cost Initial Setup  

---

## 1. Topologi Deployment Online Zero-Cost (Rp0)

Roihan AI Office dirancang agar dapat diakses secara online dari perangkat mana pun (HP, tablet, laptop) melalui HTTPS tanpa memerlukan komputer lokal yang menyala 24/7 dan dengan biaya infrastruktur awal **Rp0**:

| Komponen | Penyedia Cloud (Paket Gratis) | Spesifikasi Layanan | Domain / Endpoint |
| :--- | :--- | :--- | :--- |
| **Database Utama** | **Neon** (`neon.tech`) | Serverless PostgreSQL 16/17 (Free Tier: 0.5 GB Storage, Region Singapore `ap-southeast-1`, SSL Required) | `ep-*.ap-southeast-1.aws.neon.tech/neondb` |
| **Backend API & Worker** | **Render** (`render.com`) | Free Web Service (Python 3.11+, FastAPI + Uvicorn, 512 MB RAM, Region Singapore) | `https://roihan-ai-office-api.onrender.com` |
| **Frontend Web UI** | **Vercel** (`vercel.com`) | Hobby / Free Tier (Next.js 16 App Router, SSR Proxy, Global Edge HTTPS) | `https://roihan-ai-office.vercel.app` |
| **AI Inference** | **Google AI Studio (Gemini API)** | `gemini-2.5-flash` / `gemini-2.5-pro` (Dikontrol penuh oleh `BUDGET_ALLOW_PAID_CALLS`) | `generativelanguage.googleapis.com` |

---

## 2. Langkah demi Langkah Deployment Online (Rp0)

### Langkah 1: Siapkan Database PostgreSQL di Neon Free
1. Masuk ke [neon.tech](https://neon.tech) dan buat project baru bernama `roihan-ai-office-db` di region **Singapore (`ap-southeast-1`)**.
2. Salin **Connection String** database Anda dan ubah skema drivernya menjadi `postgresql+psycopg://`:
   ```text
   postgresql+psycopg://roihan_user:PASSWORD@ep-xyz-123.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```

### Langkah 2: Deploy Backend API ke Render Free
1. Masuk ke [render.com](https://render.com), pilih **New Web Service**, dan hubungkan ke repositori GitHub `roihan-ai-office` (atau gunakan blueprint `render.yaml`).
2. Atur konfigurasi layanan:
   - **Name:** `roihan-ai-office-api`
   - **Region:** Singapore
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r apps/api/requirements.txt`
   - **Start Command:** `cd apps/api && python -m uvicorn app.main:get_app --factory --host 0.0.0.0 --port $PORT`
3. Tambahkan **Environment Variables** berikut pada tab **Environment** di Render:

   | Variabel | Nilai Konfigurasi Produksi |
   | :--- | :--- |
   | `PYTHONPATH` | `apps/api` |
   | `APP_ENV` | `production` |
   | `APP_MODE` | `production` |
   | `DATABASE_URL` | `postgresql+psycopg://...` *(Connection string Neon dari Langkah 1)* |
   | `APP_LOCAL_TOKEN` | *(String acak kriptografis kuat minimal 32 karakter)* |
   | `OWNER_EMAIL` | `owner@roihan.id` *(Alamat email resmi pemilik tunggal)* |
   | `BOOTSTRAP_TOKEN` | *(Token rahasia sekali pakai untuk inisialisasi akun pemilik)* |
   | `GEMINI_ENABLED` | `true` |
   | `GEMINI_API_KEY` | *(Kunci API Google Gemini Anda)* |
   | `BUDGET_ALLOW_PAID_CALLS` | `false` *(Kunci panggilan di luar kuota gratis kecuali diizinkan)* |
   | `BUDGET_MONTHLY_LIMIT` | `0` |
   | `WORKER_ENABLED` | `true` |
   | `CORS_ORIGINS` | `["https://roihan-ai-office.vercel.app"]` |

4. Jalankan migrasi skema database ke revisi terbaru (`0015` head) melalui Render Shell atau pre-deploy command:
   ```bash
   cd apps/api && python -m alembic upgrade head
   ```
5. Verifikasi bahwa endpoint kesehatan merespons `200 OK`:
   ```text
   https://roihan-ai-office-api.onrender.com/api/health
   ```

### Langkah 3: Deploy Frontend Web ke Vercel Free
1. Masuk ke [vercel.com](https://vercel.com) dan impor repositori `roihan-ai-office` (menggunakan konfigurasi `vercel.json`).
2. Atur konfigurasi project Vercel:
   - **Framework Preset:** Next.js
   - **Root Directory:** `apps/web`
3. Tambahkan **Environment Variables** di Vercel:

   | Variabel | Nilai Konfigurasi Produksi | Catatan Keamanan |
   | :--- | :--- | :--- |
   | `API_BASE_URL` | `https://roihan-ai-office-api.onrender.com` | URL Render Backend |
   | `APP_LOCAL_TOKEN` | *(Sama persis dengan `APP_LOCAL_TOKEN` di Render)* | **Hanya server-side! DILARANG memakai prefix `NEXT_PUBLIC_`** |

> [!WARNING]
> `APP_LOCAL_TOKEN` adalah token rahasia server-ke-server yang hanya diakses oleh proses Node.js di sisi server Vercel (Next.js SSR Proxy) atau worker/CLI internal. Token ini **tidak pernah** dikirimkan ke browser pengguna. Browser pengguna diotentikasi secara eksklusif menggunakan cookie `HttpOnly` (`roihan_session`).

4. Klik **Deploy** dan tunggu proses build Next.js selesai hingga URL publik `https://roihan-ai-office.vercel.app` aktif.

### Langkah 4: Bootstrap Sekali Pakai Akun Pemilik (dari HP / Laptop)
1. Buka `https://roihan-ai-office.vercel.app` melalui browser ponsel atau laptop.
2. Karena tabel `owner_users` masih kosong, sistem otomatis menampilkan formulir **Inisialisasi Akun Pemilik (Setup Awal)**.
3. Isi formulir dengan:
   - **Nama Lengkap:** Nama pemilik (CEO)
   - **Email:** Wajib sama persis dengan nilai `OWNER_EMAIL` di server Render
   - **Kata Sandi:** Minimal 8 karakter kuat
   - **Token Bootstrap:** Nilai `BOOTSTRAP_TOKEN` yang diset di Render
4. Klik **Inisialisasi Akun Pemilik**.
5. Akun pemilik langsung terbentuk di tabel `owner_users`, endpoint `/api/auth/bootstrap` terkunci permanen (`HTTP 403`), sesi aman `HttpOnly` aktif, dan Anda diarahkan masuk ke Command Center!

---

## 3. Mitigasi Operasional Paket Gratis (Free-Tier Behavior)

| Karakteristik Free-Tier | Perilaku Sistem & Penanganan di Roihan AI Office |
| :--- | :--- |
| **Spin-Down Render (Idle 15 Menit)** | Render menghentikan container sementara jika tidak ada trafik selama 15 menit. Saat aplikasi dibuka kembali, permintaan pertama memerlukan waktu *cold-start* ~25–30 detik. UI menampilkan indikator sinkronisasi tanpa error fatal. |
| **Filesystem Ephemeral Render** | Disk lokal container Render Free bersifat *ephemeral* (direset ke image awal setiap restart, deploy baru, atau pemulihan idle). Seluruh data bisnis penting (**49 tabel**: sesi, task, kampanye, prospek, checkpoint, log) disimpan 100% di **Neon PostgreSQL**, sehingga tidak ada data tabel yang hilang saat restart. |
| **Interupsi Worker saat Container Restart** | Saat container Render hidup kembali pasca-restart, `PowerController.startup_recovery()` otomatis mendeteksi tugas yang terputus dan memulihkannya dari checkpoint valid terakhir di PostgreSQL. |
| **Batas Penyimpanan Neon (0.5 GB)** | Sangat memadai untuk jutaan baris data pemasaran, CRM, dan audit SEO. Hindari menyimpan berkas biner/video berukuran besar di dalam database; gunakan tautan eksternal untuk aset media besar. |

> [!CAUTION]
> Pada lingkungan Render Free, direktori lokal seperti snapshot cadangan di `data/backups/`, berkas konfigurasi runtime di `data/*.json`, dan berkas kerja di `data/projects/` akan terhapus saat instance melakukan restart. Untuk lingkungan produksi online gratis:
> 1. Tetapkan konfigurasi AI & kredensial langsung melalui Environment Variables di dashboard Render.
> 2. Manfaatkan **Neon Point-in-Time Restore** untuk pemulihan database cloud.
> 3. Jika membuat backup snapshot lewat UI (`/api/backups`), segera unduh berkas arsip snapshot ke komputer lokal Anda untuk penyimpanan permanen.

---

## 4. Prosedur Rollback Deployment

Jika pembaruan kode menyebabkan kendala pada lingkungan produksi:
1. **Rollback Frontend (Vercel):** Buka dashboard Vercel -> tab **Deployments** -> pilih deployment stabil sebelumnya -> klik **Instant Rollback**.
2. **Rollback Backend (Render):** Buka dashboard Render -> tab **Events / Deploys** -> pilih commit stabil sebelumnya -> klik **Rollback to this deploy**.
3. **Rollback Database (Neon Point-in-Time Restore):** Buka [console.neon.tech](https://console.neon.tech) -> pilih project `roihan-ai-office-db` -> menu **Restore** -> kembalikan state database ke titik waktu (*timestamp*) sebelum deployment dilakukan, atau pulihkan melalui snapshot CLI dengan flag `--force`:
   ```bash
   python -m app.backup restore <nama-backup> --force
   ```

---

## 5. Checklist Penerimaan Deployment (Post-Deployment Checklist)

- [x] URL Frontend Vercel dan Backend Render hanya dapat diakses melalui **HTTPS (TLS 1.3)**.
- [x] `GET /api/health` melaporkan database PostgreSQL dan konfigurasi Gemini API sehat.
- [x] Akun pemilik tunggal berhasil di-bootstrap dan percobaan akses ulang ke `/api/auth/bootstrap` ditolak dengan `403 Forbidden`.
- [x] Cookie sesi memiliki atribut `HttpOnly`, `SameSite=Lax`, dan `Secure` (di production).
- [x] Koneksi WebSocket real-time (`/api/ws`) berhasil terhubung menggunakan tiket sekali pakai dari `POST /api/events/ticket`.
- [x] `BUDGET_ALLOW_PAID_CALLS=false` aktif sebagai pengaman biaya awal Rp0.
