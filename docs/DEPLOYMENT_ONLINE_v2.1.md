# PANDUAN DEPLOYMENT ONLINE, AKSES SINGLE-OWNER & SETUP RP0 (ADDENDUM v2.1)

**Nama Produk:** Roihan AI Office  
**Dokumen Acuan:** ADDENDUM v2.1 — Online Deployment, Single-Owner Access & Zero-Cost Initial Setup  
**Tanggal:** 27 Oktober 2026  
**Status:** **SPESIFIKASI OPERASIONAL WAJIB & TERUJI**

---

## 1. TUJUAN & ARSITEKTUR ZERO-COST (Rp0)

Roihan AI Office dirancang agar dapat diakses secara online dari mana saja (HP, tablet, laptop, PC kantor) melalui protokol aman HTTPS tanpa memerlukan komputer pribadi yang menyala 24/7, dengan biaya infrastruktur awal **Rp0** memanfaatkan batas paket gratis (*free-tier*) yang kompatibel.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PERANGKAT PENGGUNA (HP / LAPTOP)                     │
│               Akses HTTPS mandiri via Browser Mobile/Desktop           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS (TLS 1.3)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (VERCEL / CLOUDFLARE)                     │
│ - Platform: Next.js 16 App Router (React 19, TypeScript)               │
│ - Domain bawaan: https://roihan-ai-office.vercel.app                  │
│ - Fitur: Single-Owner Gateway, Modern Minimalist SaaS UI, SSR Proxy    │
│ - Biaya: Rp0 (Paket Hobby / Free Tier Tanpa Batas Waktu)               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS API Calls & Cookie Forwarding
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      BACKEND (RENDER WEB SERVICE)                      │
│ - Platform: FastAPI + Uvicorn (Python 3.11)                            │
│ - Domain bawaan: https://roihan-ai-office-api.onrender.com             │
│ - Fitur: Task Worker Engine, AI Gateway, Single-Owner Auth Guard       │
│ - Biaya: Rp0 (Render Free Web Service 512MB RAM)                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Pooled Connection (SSL Required)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   DATABASE TERKELOLA (NEON POSTGRESQL)                 │
│ - Platform: Serverless PostgreSQL 16                                   │
│ - Skema: 48 Tabel (Alembic Revision 0015 Head)                         │
│ - Fitur: Penyimpanan persisten, isolasi tenant, backup snapshot        │
│ - Biaya: Rp0 (Neon Free Tier 0.5 GB Storage, Autoscaling Compute)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. SINGLE-OWNER AUTHENTICATION (KEAMANAN PEMILIK TUNGGAL)

Sesuai **Bagian 3 & 4 Addendum v2.1**, sistem beroperasi dalam mode **Single-Owner**:

1. **Satu Akun Sah:** Hanya ada 1 akun pemilik yang diizinkan berada di database. Registrasi publik ditutup permanen.
2. **Bootstrap Sekali Pakai:**
   - Saat sistem pertama kali dijalankan di cloud, halaman login otomatis menampilkan form **Inisialisasi Akun Pemilik**.
   - Pemilik mendaftarkan email resmi (wajib cocok dengan `OWNER_EMAIL` jika dikonfigurasi di server).
   - Setelah akun berhasil dibuat, endpoint `/api/auth/bootstrap` **otomatis terkunci permanen** (mengembalikan HTTP 403 Forbidden untuk setiap upaya pendaftaran berikutnya).
3. **Kriptografi Kata Sandi:** Menggunakan algoritma standar industri **PBKDF2-HMAC-SHA256** dengan salt unik 16-byte dan 600.000 iterasi rekomendasi OWASP.
4. **Proteksi Brute-Force & Rate Limiting:**
   - Jika terjadi 5 kali kegagalan login berturut-turut, akun otomatis dikunci sementara selama 15 menit (`HTTP 429 Too Many Requests`).
   - Setiap upaya login gagal dicatat ke dalam `AuditLog`.
5. **Manajemen Sesi:**
   - Sesi disimpan secara persisten di tabel `owner_sessions`.
   - Menggunakan token acak 32-byte berkekuatan tinggi (`secrets.token_urlsafe(32)`).
   - Cookie ditandai dengan flag `HttpOnly`, `SameSite=Lax`, dan `Secure` (saat HTTPS aktif).
   - Tombol logout di dock navigasi langsung mencabut (*revoke*) sesi di database dan menghapus cookie dari browser.

---

## 3. LANGKAH-LANGKAH DEPLOYMENT ONLINE (ZERO-COST Rp0)

### Langkah 1: Siapkan Database Neon Free (PostgreSQL)
1. Buka [neon.tech](https://neon.tech) dan buat akun gratis.
2. Buat project baru dengan nama `roihan-ai-office-db`, pilih region **Singapore (ap-southeast-1)**.
3. Salin **Connection String** yang diberikan. Ubah skema driver menjadi `postgresql+psycopg://`:
   ```text
   postgresql+psycopg://roihan_user:PASSWORD@ep-xyz-123.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```

### Langkah 2: Deploy Backend ke Render Free
1. Buka [render.com](https://render.com) dan hubungkan akun GitHub Anda.
2. Buat **New Web Service**, pilih repositori `roihan-ai-office`.
3. Konfigurasikan parameter layanan:
   - **Name:** `roihan-ai-office-api`
   - **Region:** Singapore
   - **Branch:** `main`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r apps/api/requirements.txt`
   - **Start Command:** `cd apps/api && python -m uvicorn app.main:get_app --factory --host 0.0.0.0 --port $PORT`
4. Masukkan Environment Variables di tab **Environment**:
   - `PYTHONPATH`: `apps/api`
   - `APP_ENV`: `production`
   - `APP_MODE`: `production`
   - `DATABASE_URL`: *(Connection string Neon dari Langkah 1)*
   - `APP_LOCAL_TOKEN`: *(Buat string acak minimal 32 karakter)*
   - `OWNER_EMAIL`: `owner@roihan.id` *(Email sah Anda)*
   - `BOOTSTRAP_TOKEN`: *(String acak rahasia sekali pakai untuk bootstrap)*
   - `GEMINI_ENABLED`: `true`
   - `GEMINI_API_KEY`: *(Kunci API Google Gemini Anda)*
   - `BUDGET_ALLOW_PAID_CALLS`: `false`
   - `BUDGET_MONTHLY_LIMIT`: `0`
   - `WORKER_ENABLED`: `true`
   - `CORS_ORIGINS`: `["https://roihan-ai-office.vercel.app"]`
5. Jalankan migrasi database perdana di Render Shell atau pre-deploy:
   ```bash
   cd apps/api && python -m alembic upgrade head
   ```
6. Render akan memberikan URL HTTPS publik, misalnya: `https://roihan-ai-office-api.onrender.com`.

### Langkah 3: Deploy Frontend ke Vercel Free
1. Buka [vercel.com](https://vercel.com) dan impor repositori `roihan-ai-office`.
2. Pada konfigurasi project:
   - **Framework Preset:** Next.js
   - **Root Directory:** `apps/web`
3. Masukkan Environment Variables:
   - `API_BASE_URL`: `https://roihan-ai-office-api.onrender.com` *(URL Render backend dari Langkah 2)*
   - `APP_LOCAL_TOKEN`: *(Sama persis dengan APP_LOCAL_TOKEN di backend)*
4. Klik **Deploy**. Vercel akan mem-build Next.js App Router dan memberikan URL publik HTTPS, misalnya: `https://roihan-ai-office.vercel.app`.

### Langkah 4: Bootstrap Akun Pemilik dari HP / Laptop
1. Buka URL frontend Vercel Anda (`https://roihan-ai-office.vercel.app`) dari browser ponsel atau laptop mana pun.
2. Sistem otomatis menampilkan layar **Inisialisasi Akun Pemilik (Setup Awal)**.
3. Masukkan:
   - Nama Lengkap: `Roihan Fatih`
   - Email: `owner@roihan.id` *(Wajib sama dengan OWNER_EMAIL)*
   - Kata Sandi: *(Minimal 8 karakter)*
   - Token Bootstrap: *(Masukkan nilai BOOTSTRAP_TOKEN yang diset di Render)*
4. Klik **Inisialisasi Akun Pemilik**.
5. Akun terbentuk seketika, sesi login diamankan dengan cookie HttpOnly, dan Anda langsung diarahkan ke Command Center Marketing Dashboard!

---

## 4. AUDIT KOMPATIBILITAS PAKET GRATIS (FREE-TIER LIMITS)

| Aspek | Batas Free-Tier | Mitigasi & Desain di Roihan AI Office |
| :--- | :--- | :--- |
| **Backend Spin-Down** | Render Free menjeda server setelah 15 menit tidak ada traffic. | Kunjungan pertama setelah jeda memakan waktu *cold-start* ~30 detik. Antarmuka frontend menampilkan status sinkronisasi elegan tanpa crash. |
| **Penyimpanan Ephemeral** | Filesystem Render di-reset setiap kali deploy atau restart. | **Semua data persisten 100% disimpan di Neon PostgreSQL** (bukan di harddisk lokal). Checkpoint dan task state aman dari restart. |
| **Background Task Persistence** | Worker bisa terhenti jika kontainer Render di-restart. | Seluruh task status dipersistenkan di database. Saat backend hidup kembali, `PowerController.startup_recovery()` otomatis memulihkan task yang tertunda. |
| **Database Storage** | Neon Free memberikan kuota 0.5 GB. | Sangat cukup untuk jutaan baris data teks marketing, lead B2B, dan riwayat audit. Tabel berukuran besar seperti upload gambar diarahkan menggunakan link eksternal. |
| **WebSocket Reconnection** | Koneksi WebSocket terputus saat cold start. | Client frontend dilengkapi mekanisme *reconnect exponential backoff* dan catch-up REST API (`/api/events?since=seq`). |
| **Biaya AI API** | Gemini Free Tier memberikan kuota gratis yang memadai untuk flash model. | Parameter `BUDGET_ALLOW_PAID_CALLS=false` mengunci sistem dari panggilan berbayar di luar batas gratis. |

---

## 5. PROSEDUR BACKUP DAN DISASTER RECOVERY ONLINE

1. **Snapshot Database Neon:**
   - Masuk ke dashboard [console.neon.tech](https://console.neon.tech).
   - Buka project `roihan-ai-office-db` &rarr; tab **Branches** / **Backups**.
   - Fitur *point-in-time restore* Neon memungkinkan rollback database ke menit mana pun dalam 7 hari terakhir secara instan dan gratis.
2. **Snapshot CLI Mandiri:**
   Pemilik dapat menjalankan ekspor snapshot database kapan saja melalui terminal lokal atau runner:
   ```bash
   $env:PYTHONPATH="apps/api"
   python -m app.backup create
   ```
   File hasil snapshot (`database.jsonl.gz`) tersimpan aman dengan verifikasi checksum SHA-256.

---

## 6. CHECKLIST KRITERIA PENERIMAAN DEPLOYMENT (ACCEPTANCE CRITERIA)

- [x] **Akses Lintas Perangkat:** Aplikasi dapat dibuka dari ponsel, tablet, laptop via HTTPS.
- [x] **Single-Owner Guard:** Hanya 1 akun pemilik yang dapat dibuat dan login; registrasi publik ditutup permanen.
- [x] **Perlindungan Brute-Force:** Kunci otomatis 15 menit setelah 5x gagal login.
- [x] **Keamanan Sesi:** Cookie bertanda HttpOnly, SameSite=Lax, dan Secure.
- [x] **Autentikasi Terintegrasi Backend:** Seluruh rute API yang dilindungi memvalidasi sesi atau bearer token.
- [x] **WebSocket Berizin:** WebSocket dilindungi mekanisme ticket sekali pakai berbatas waktu.
- [x] **Persistensi Data Cloud:** Database terhubung ke Neon PostgreSQL dengan migrasi 0015 (head).
- [x] **Zero-Cost Rp0:** Tidak ada kartu kredit atau tagihan hosting berbayar yang diaktifkan.
- [x] **Dokumentasi Blueprint:** `render.yaml`, `vercel.json`, dan `.env.production.example` tersedia lengkap.
