# 6. DEVELOPMENT GUIDE & CODING RULES

**Nama Produk:** Roihan AI Office  
**Direktori Kerja:** `D:\workspace\roihan-ai-office`  
**Standar Pengembangan:** Master Addendum v1.0, v1.1, v2.0, dan v2.1  

---

## 1. Prasyarat Lingkungan Pengembangan (Prerequisites)

Untuk menjalankan dan mengembangkan **Roihan AI Office** secara lokal:
- **Python:** `3.10+` (kompatibel hingga Python `3.15` pada lingkungan pengembangan lokal; `3.11+` pada lingkungan cloud Render).
- **Node.js & npm:** Node.js `20+`.
- **Database:** PostgreSQL `16` / `17` (lokal di `127.0.0.1:5432/roihan` atau Neon Serverless PostgreSQL). SQLite didukung untuk eksekusi unit test terisolasi.
- **Git:** Terpasang untuk kontrol versi repositori dan manajemen salinan workspace situs.
- **Google Gemini API Key:** Opsional untuk mode pengembangan biasa (karena pengujian otomatis menggunakan `FakeProvider`), wajib jika ingin menguji pemanggilan AI nyata (`gemini-2.5-flash` / `gemini-2.5-pro`).
- **Catatan Penting:** **Ollama tidak lagi diperlukan** sebagai dependensi runtime maupun pengembangan.

---

## 2. Konfigurasi Lingkungan Lokal (`.env`)

1. Salin berkas `.env.example` menjadi `.env` di direktori akar `roihan-ai-office/`.
2. Buat token lokal acak minimal 32 karakter:
   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. Konfigurasikan variabel utama di `.env`:
   ```ini
   APP_ENV=development
   APP_MODE=local
   DATABASE_URL=postgresql+psycopg://postgres:password@127.0.0.1:5432/roihan
   APP_LOCAL_TOKEN=<token-acak-32-karakter>
   OWNER_EMAIL=owner@roihan.id
   BOOTSTRAP_TOKEN=<token-bootstrap-sekali-pakai>

   # AI Provider (Google Gemini API)
   GEMINI_ENABLED=true
   GEMINI_API_KEY=<kunci-api-gemini-anda>
   GEMINI_DEFAULT_MODEL=gemini-2.5-flash
   GEMINI_PRO_MODEL=gemini-2.5-pro

   # Kontrol Biaya & Anggaran
   BUDGET_MONTHLY_LIMIT=0
   BUDGET_ALLOW_PAID_CALLS=false
   AI_MAX_TOKENS_CAP=8192

   # Worker & Keamanan
   WORKER_ENABLED=true
   CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
   ```

> **Peringatan Keamanan:** Berkas `.env` memuat rahasia dan **dilarang keras** di-commit ke Git.

---

## 3. Menjalankan Aplikasi di Lingkungan Lokal

Buka **dua terminal PowerShell** terpisah dari direktori `D:\workspace\roihan-ai-office`:

### Terminal 1 — Backend API (`apps/api`)
```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8000
```
Verifikasi kesehatan backend di: `http://127.0.0.1:8000/api/health`

### Terminal 2 — Frontend Web (`apps/web`)
```powershell
cd apps/web
npm install
npm run dev
```
Buka antarmuka aplikasi di browser: `http://localhost:3000`

---

## 4. Standar Desain UI/UX (Modern Minimalist SaaS)

Setiap perubahan atau penambahan komponen frontend di `apps/web` wajib mematuhi sistem desain **Modern Minimalist SaaS**:

1. **Design Tokens Terpusat:**
   - **Background Utama:** Warm Charcoal (`#131517`) / Off-White sesuai mode tema.
   - **Surface Kartu / Panel:** Dark Surface (`#1e2226`) / Pure White (`#ffffff`) dengan border netral halus.
   - **Primary Accent:** Energetic Orange (`#ff6b35` / `#ff5722`).
   - **Border Radius:** Sudut membulat konsisten (`14px` hingga `18px`).
   - **Tipografi:** Keluarga font tunggal **Montserrat** (`@fontsource-variable/montserrat`) dengan hierarki tegas (Page Title, Section Title, Card Title, Body, Supporting/Metadata).
2. **Larangan Gaya Visual Lama:**
   - **Dilarang keras** mengaktifkan kembali `cyber-ui.css`, sudut *chamfer polygon* (`clip-path`), efek neon cyan/magenta berlebihan, teks *glitch*, atau komponen dekoratif 3D cyberpunk.
3. **Kejujuran State UI & Data:**
   - Semua komponen wajib memiliki state `loading`, `error`, `empty`, `disabled`, dan `success` yang terikat langsung ke konfirmasi backend.
   - **Dilarang menampilkan data mock sebagai data produksi.** Bedakan dengan tegas antara angka `0`, nilai `null` (*"Belum ada data"*), dan fitur/integrasi yang `not_connected`.
4. **Aksesibilitas & Responsivitas:**
   - Target kepatuhan **WCAG 2.2 AA** (kontras teks memadai, *focus ring* terlihat saat navigasi keyboard, *accessible label* pada tombol ikon).
   - Bebas dari *horizontal overflow* pada layar mobile, tablet, maupun desktop.

---

## 5. Standar Arsitektur Backend & AI Adapter

1. **Prinsip Backup Sebelum Refactor:**
   - Sebelum melakukan perubahan skema atau refaktor besar, buat checkpoint Git dan jalankan snapshot database (`python -m app.backup create` & `verify`).
2. **Pemanggilan AI Terpusat (`ModelGateway`):**
   - Seluruh agen pemasaran wajib memanggil model melalui `ModelGateway` dan kontrak `ModelProvider` (`apps/api/app/providers/cloud.py` untuk Gemini API atau `tests/fakes.py` untuk pengujian).
   - Dilarang menulis nama model secara *hardcoded* di dalam logika agen; gunakan konfigurasi runtime.
   - Pastikan pemeriksaan anggaran (`budget_check`) dan batas token dijalankan sebelum pemanggilan model berbayar.
3. **Penegakan Akses di Backend (Deny-by-Default):**
   - Pembatasan hak akses agen, validasi transisi status task, pemeriksaan *Product Release Gate*, linter klaim (`check_claims`), dan pengikatan hash SHA-256 pada *Approval Gate* wajib ditegakkan di kode backend Python, bukan hanya mengandalkan instruksi prompt.
4. **Anti-Prompt Injection & Konten Eksternal:**
   - Semua berkas unggahan, hasil pencarian web (Tavily/Brave), halaman yang di-crawl, dan teks prospek wajib diperlakukan sebagai **data tidak tepercaya**, bukan instruksi sistem.
5. **Internasionalisasi (i18n):**
   - Bahasa antarmuka default adalah **Bahasa Indonesia (`id`)** dengan dukungan pengalihan ke **Bahasa Inggris (`en`)** melalui kamus `apps/web/src/i18n/dictionaries.ts`.

---

## 6. Perintah Verifikasi Kualitas Kode (Quality Checks)

Sebelum menyelesaikan setiap *task* atau membuat *commit*, pengembang/agen coding wajib menjalankan perintah berikut dan memastikan seluruhnya lulus:

### 6.1 Pemeriksaan Backend (`apps/api`)
```powershell
cd apps/api
# Jalankan seluruh test suite pytest
.\.venv\Scripts\python.exe -m pytest

# Jalankan audit keamanan otomatis
.\.venv\Scripts\python.exe ..\..\scripts\audit_security.py --deps
```

### 6.2 Pemeriksaan Frontend (`apps/web`)
```powershell
cd apps/web
# Pemeriksaan tipe TypeScript (wajib 0 error)
npx tsc --noEmit

# Jalankan unit & component test Vitest
npm test -- --run

# Pemeriksaan linter & build produksi
npm run lint
npm run build
```

---

## 7. Aturan Wajib bagi AI Coding Agent (21 Aturan Emas)

1. Pelajari dokumentasi resmi di `docs/` sebelum mengubah kode.
2. Periksa implementasi aktual di repositori; jangan mengasumsikan fitur/endpoint sudah ada tanpa memverifikasinya.
3. Jangan mengganti stack teknologi inti (Next.js, FastAPI, SQLAlchemy, Alembic, PostgreSQL) tanpa persetujuan pemilik.
4. Jangan menghapus fitur atau tabel yang sudah berfungsi secara destruktif.
5. Buat perubahan kecil, terisolasi, dan dapat diuji (*atomic changes*).
6. Jangan pernah menulis API key, token, atau kredensial di dalam source code maupun log.
7. Jangan melewati *Approval Gate*, *Budget Gate*, atau *Product Release Gate*.
8. **Jangan pernah mengklaim pengujian berhasil jika perintah tes tidak benar-benar dijalankan.**
9. Dokumentasikan setiap perubahan perilaku sistem, migrasi database, atau variabel lingkungan baru di dokumen terkait dalam `docs/`.
