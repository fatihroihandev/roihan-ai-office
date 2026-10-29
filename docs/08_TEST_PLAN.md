# 8. TEST PLAN & QUALITY ASSURANCE GATE

**Nama Produk:** Roihan AI Office  
**Framework Pengujian:** `pytest` (Backend Python) & `Vitest` + `TypeScript Compiler` (Frontend Next.js)  
**Baseline Kualitas Terverifikasi:** Backend **945 passed, 2 skipped, 0 failed** (dari 947 tes); Frontend **89 passed, 0 failed** (11 test files); TypeScript **0 error**.  

---

## 1. Strategi & Tingkatan Pengujian

Pengembangan dan pemeliharaan Roihan AI Office menerapkan strategi pengujian berlapis berbasis bukti nyata (**Zero Unverified Claims**):

1. **Unit Tests:**
   - Menguji fungsi murni, validasi skema Pydantic, tabel transisi status task, perhitungan *Difficulty Score* & *Risk Override*, skor kecocokan prospek deterministik (0–100), linter klaim (`check_claims`), fungsi penyamaran PII/rahasia, dan pemetaan state UI.
2. **Integration Tests (dengan `FakeProvider` & Database Uji):**
   - Menguji integrasi seluruh endpoint FastAPI dengan database (PostgreSQL / SQLite), antrean worker, adapter Google Gemini API & `FakeProvider` (`tests/fakes.py` tanpa biaya kuota internet), siklus hidup *Approval Gate*, *Product Release Gate*, *Autonomous SEO*, *Office Power Control*, serta mekanisme backup/restore.
3. **Security & Mutation Verification Tests:**
   - Menyisir seluruh skema OpenAPI secara otomatis untuk memastikan penegakan autentikasi, header keamanan, SSRF-Guard, pencegahan *path traversal*, dan memverifikasi bahwa mutasi pada aturan kritis (approval, klaim produk, privasi prospek) pasti tertangkap oleh test suite.
4. **End-to-End (E2E) & Game-Day Resilience Tests:**
   - Menguji skenario operasional penuh dari hulu ke hilir serta ketahanan sistem saat terjadi interupsi paksa (*crash recovery*, siklus OFF/ON berulang, dan pemulihan snapshot database).

---

## 2. Cakupan Suite Pengujian Berdasarkan Modul

### 2.1 Backend Test Suite (`apps/api/tests/`)

| Area Pengujian | Berkas / Kelompok Tes Utama | Fokus Verifikasi |
| :--- | :--- | :--- |
| **Autentikasi & Keamanan** | `test_security_audit.py` | Validasi sesi Single-Owner, kunci permanen bootstrap, *rate limit* 5x gagal login, proteksi seluruh rute OpenAPI (`401`), CORS, tiket WebSocket sekali pakai, CSP & security headers, dan pemindai rahasia. |
| **AI Provider & Budget Gate** | `test_providers.py`, `test_router.py`, `fakes.py` | Kontrak `ModelProvider`, integrasi adapter Google Gemini API (`cloud.py`), ketahanan `FakeProvider`, normalisasi error/timeout, blokir panggilan berbayar (`BUDGET_ALLOW_PAID_CALLS=false`), dan pencatatan `model_usage` tanpa membocorkan prompt. |
| **Task Engine & Approval Gate** | `test_tasks.py`, `test_approvals.py` | Transisi status task yang sah, resolusi rantai dependensi (DAG), batas retry (`max_retries=2`), pengikatan hash SHA-256 pada approval, masa berlaku TTL, pemakaian sekali pakai, dan penolakan persetujuan oleh agen (`agent_cannot_approve`). |
| **Autonomous SEO & Situs** | `test_seo.py`, `test_sites.py` | CRUD `SeoCampaign`, penguncian domain, audit HTML/situs deterministik, penyimpanan `SeoKeyword` & `SeoRecommendation` dengan bukti sumber (*source grounding*), pengecekan anggaran kampanye pra-pemanggilan AI, dan pencegahan duplikasi task aktif. |
| **Katalog Produk & Gerbang Rilis** | `test_products.py` | 10 syarat *Product Release Gate*, perhitungan ulang otomatis izin pemasaran (`not_allowed`, `beta_only`, `allowed`), pembuatan `marketing_brief`, dan akurasi linter klaim `check_claims`. |
| **Leads, CRM & Kepatuhan UU PDP** | `test_marketing.py` | Validasi sumber prospek yang sah, penolakan NIK/kartu/email pribadi non-inbound, penyamaran kontak bawaan, audit `lead.pii_viewed`, *suppression list* berbasis hash, skor deterministik 0–100, bukti kenaikan tahap, dan kebijakan retensi. |
| **Content, Campaigns & Outbox** | `test_content.py`, `test_campaigns.py` | Siklus pembuatan draf konten/outreach dari `marketing_brief`, wajib kalimat *unsubscribe*, pengajuan approval terikat `body_hash`, antrean `outbound_messages`, batas frekuensi harian, dan perhitungan ROI. |
| **Akses Web Terkendali (SSRF)** | `test_web.py` | Penolakan 16+ variasi URL berbahaya (loopback, IP privat, link-local metadata cloud, IPv6 mapped), revalidasi DNS pada tiap redirect, kepatuhan `robots.txt`, batas ukuran 500 KB, dan kuota harian. |
| **Office Power Control & Recovery** | `test_power.py` | Idempotensi perintah OFF/ON, penghentian worker terkontrol, integritas SHA-256 pada `task_checkpoints`, deteksi *crash* saat startup, pencegahan eksekusi ulang task yang sudah `completed` atau berisiko, dan penyelesaian `RecoveryItem`. |
| **Backup & Disaster Recovery** | `test_backup.py`, `test_recovery.py` | Pembuatan snapshot atomik (`database.jsonl.gz` + `manifest.json`), verifikasi SHA-256 & jumlah baris 48 tabel, *round-trip restore* dengan perlindungan `pre-restore`, dan penolakan arsip tar berbahaya. |

### 2.2 Frontend Test Suite (`apps/web/src/`)

| Area Pengujian | Fokus Verifikasi |
| :--- | :--- |
| **Type Safety (`tsc --noEmit`)** | Memastikan 0 error tipe TypeScript di seluruh halaman, komponen UI, dan kontrak API. |
| **API Route Proxy (`apiRoutes.test.ts`)** | Memastikan seluruh metode HTTP (`GET`, `POST`, `PATCH`, `PUT`, `DELETE`) diekspor dengan benar pada rute proxy Next.js dan meneruskan sesi/token dengan aman. |
| **Dashboard & Charts (`situation.test.ts`, `palette.test.ts`)** | Memvalidasi perhitungan deterministik indikator situasi, palet warna aksesibel (WCAG 2.2 AA), serta pembedaan nilai `0` vs `null` (*"Belum ada data"*). |
| **Navigation & Workspace State (`nav.test.ts`)** | Memvalidasi perpindahan tampilan modular (`/?view=...`), sinkronisasi state terbaru (respons lama tidak pernah menimpa respons yang lebih baru), dan perilaku responsif. |

---

## 3. Skenario Pengujian End-to-End (E2E) Wajib

Sebelum rilis dinyatakan lulus, 10 skenario alur kerja terpadu berikut harus terverifikasi:

1. **Single-Owner Bootstrap & Login Guard:** Inisialisasi akun pemilik pertama kali berhasil -> panggilan bootstrap kedua ditolak `403` -> 5x salah password mengunci login `429` -> login benar menerbitkan cookie `HttpOnly` dan membuka Command Center.
2. **Perencanaan Tugas Marketing:** CEO memasukkan tujuan pemasaran -> *Marketing Orchestrator* menyusun *draft tasks* bebas siklus -> CEO mengantrekan tugas -> worker mengeksekusi tugas secara berurutan.
3. **Gerbang Rilis Produk & Proteksi Klaim:** Produk berstatus `draft` ditolak saat dibuatkan konten promosi -> setelah klaim fitur terverifikasi/diatestasi dan izin `beta_only` diberikan, agen Content membuat draf yang menyebut label beta dan lolos `check_claims`.
4. **Siklus Kampanye Autonomous SEO:** Buat kampanye SEO baru -> jalankan audit teknis situs -> tinjau rekomendasi berurut *severity* -> jalankan riset keyword (volume tanpa bukti sumber tetap `null`) -> setujui keyword untuk Content Studio.
5. **Akuisisi Prospek B2B & Perlindungan Privasi:** Ekstrak prospek dari teks/pencarian web -> kandidat bergmail pribadi atau masuk *suppression list* ditolak -> prospek sah tersimpan dengan kontak tersamar -> klik tampilkan kontak mencatat `lead.pii_viewed` di `audit_logs`.
6. **Approval Gate & Kotak Keluar:** Ajukan pengiriman outreach / publikasi konten -> tertahan di `pending_approval` -> upaya perubahan isi membatalkan approval -> setelah CEO menyetujui, item masuk ke `outbound_messages` (`queued_manual`) -> CEO tandai terkirim (`dispatched_manual`).
7. **Penegakan Anggaran AI (Budget Cap):** Saat `BUDGET_ALLOW_PAID_CALLS=false` atau sisa anggaran kampanye SEO tidak mencukupi, pemanggilan model berbayar diblokir tanpa membebani biaya.
8. **Kontrol Daya OFF / ON & Checkpoint:** Tekan OFF saat tugas berjalan -> status menjadi `PAUSED` setelah checkpoint SHA-256 terverifikasi -> tekan ON -> tugas berlanjut hingga `completed` tanpa menggandakan pekerjaan yang sudah selesai.
9. **Pemulihan Crash Mendadak (Crash Recovery):** Matikan proses backend secara paksa saat tugas berjalan -> nyalakan kembali backend -> `startup_recovery()` mendeteksi *unclean shutdown*, memulihkan tugas aman, dan menahan tugas berisiko sebagai `RecoveryItem`.
10. **Backup & Restore Database:** Buat snapshot cadangan -> verifikasi `manifest.json` -> lakukan restore pada database uji -> seluruh 48 tabel pulih dengan jumlah baris dan hash yang identik.

---

## 4. Cara Menjalankan Seluruh Suite Pengujian

### 4.1 Eksekusi Cepat (Tanpa Biaya API — Menggunakan `FakeProvider`)
```powershell
# 1. Backend Pytest Suite
cd D:\workspace\roihan-ai-office\apps\api
.\.venv\Scripts\python.exe -m pytest -q

# 2. Frontend Vitest & TypeScript Check
cd D:\workspace\roihan-ai-office\apps\web
npx tsc --noEmit
npm test -- --run

# 3. Security Audit Script
cd D:\workspace\roihan-ai-office
apps\api\.venv\Scripts\python.exe scripts\audit_security.py --deps
```

### 4.2 Pengujian pada Database PostgreSQL Terisolasi
```powershell
cd D:\workspace\roihan-ai-office\apps\api
$env:TEST_POSTGRES_URL="postgresql+psycopg://postgres:password@127.0.0.1:5432/roihan_test"
.\.venv\Scripts\python.exe -m pytest
```

---

## 5. Kriteria Kelulusan Pengujian (Quality Gate Definition of Done)

Sebuah fase atau rilis **dilarang** dinyatakan selesai apabila:
- Ada 1 saja tes fungsional di `pytest` atau `Vitest` yang gagal (`failed`).
- Terdapat error kompilasi pada `npx tsc --noEmit` atau `npm run build`.
- Terdapat kebocoran secret atau rute API tanpa autentikasi yang terdeteksi oleh `scripts/audit_security.py`.
- Hasil tes hanya diklaim secara lisan tanpa bukti eksekusi perintah terminal yang nyata.
