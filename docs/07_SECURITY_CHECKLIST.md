# 7. SECURITY ARCHITECTURE & CHECKLIST

**Nama Produk:** Roihan AI Office  
**Model Ancaman:** Single-Owner Cloud & Local Web Application dengan Eksekusi Agen AI Otonom Terkendali  
**Standar Kepatuhan:** OWASP Best Practices, WCAG 2.2 AA, & UU Pelindungan Data Pribadi (UU No. 27 Tahun 2022)  

---

## 1. Model Ancaman (Threat Model)

Roihan AI Office melindungi sistem dan pemilik bisnis dari 6 vektor ancaman utama:
1. **Akses Tidak Sah dari Internet:** Upaya pembajakan akun pemilik, pendaftaran akun liar, atau *brute-force* kata sandi saat aplikasi di-deploy secara online.
2. **Cross-Origin & Browser Attacks:** Halaman web jahat di browser yang mencoba memanggil API, mencuri token sesi, melakukan *clickjacking*, atau membajak koneksi WebSocket.
3. **Kebocoran Rahasia (Secret Leakage):** Bocornya `GEMINI_API_KEY`, `APP_LOCAL_TOKEN`, `BOOTSTRAP_TOKEN`, atau kunci pencarian web ke repositori Git, bundel klien Next.js (`.next/static`), log aplikasi, atau snapshot backup.
4. **Pembengkakan Biaya AI Tak Terkendali:** Panggilan model berbayar tanpa izin, *infinite loop* pada tugas terjadwal, atau *fallback* diam-diam ke provider mahal.
5. **Tindakan Agen di Luar Kewenangan & Prompt Injection:** Manipulasi agen melalui konten web/dokumen eksternal untuk mengirim spam, mempublikasikan klaim produk palsu, atau menyetujui tindakan berisiko sendiri.
6. **Server-Side Request Forgery (SSRF) & Path Traversal:** Eksploitasi crawler SEO atau fitur pencari web untuk memindai jaringan internal/metadata cloud, atau arsip backup/unggah berkas yang menulis ke luar direktori kerja.

---

## 2. Kontrol Keamanan Berlapis (Implemented Security Controls)

### 2.1 Autentikasi Pemilik Tunggal (Single-Owner Authentication)
- [x] **Kunci Permanen Bootstrap:** Hanya 1 akun pemilik yang diizinkan di tabel `owner_accounts`. Setelah inisialisasi perdana via `/api/auth/bootstrap` (dengan validasi `OWNER_EMAIL` dan `BOOTSTRAP_TOKEN`) berhasil, endpoint bootstrap otomatis mengembalikan `HTTP 403 Forbidden` secara permanen.
- [x] **Hashing Kata Sandi Kuat:** Menggunakan algoritma **PBKDF2-HMAC-SHA256** dengan salt acak unik 16-byte dan **600.000 iterasi** (standar rekomendasi OWASP).
- [x] **Proteksi Brute-Force:** Setelah **5 kali gagal login berturut-turut**, akun otomatis dikunci sementara selama **15 menit** (`HTTP 429 Too Many Requests`) dan seluruh percobaan gagal dicatat di `audit_logs`.
- [x] **Keamanan Sesi (`owner_sessions`):** Token sesi menggunakan `secrets.token_urlsafe(32)`, disimpan sebagai hash di database, dan dikirim melalui cookie dengan atribut `HttpOnly`, `SameSite=Lax`, dan `Secure` (saat HTTPS aktif). Logout langsung mencabut (*revoke*) sesi di database.
- [x] **Proteksi Seluruh Rute API:** Seluruh endpoint `/api/*` (kecuali `/api/health` dan rute login/bootstrap publik) memvalidasi sesi aktif atau Bearer token dengan perbandingan waktu-konstan (`secrets.compare_digest`).

### 2.2 Keamanan Jaringan, CORS, Headers & WebSocket
- [x] **Isolasi Token di Server Next.js:** `APP_LOCAL_TOKEN` dan `GEMINI_API_KEY` tidak pernah menggunakan prefix `NEXT_PUBLIC_` dan tidak pernah masuk ke bundel JavaScript browser.
- [x] **CORS Ketat:** Hanya mengizinkan origin yang terdaftar secara eksplisit di `CORS_ORIGINS` (misalnya `https://roihan-ai-office.vercel.app`).
- [x] **Tiket WebSocket Sekali Pakai:** Koneksi WebSocket (`/api/ws`) menggunakan tiket *one-time* berumur pendek (30 detik) dan memverifikasi header `Origin`.
- [x] **HTTP Security Headers (API & Frontend):**
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Cache-Control: no-store` (pada respons API)
  - `Content-Security-Policy (CSP)`: `default-src 'self'`, melarang `object-src` dan `frame-ancestors`.
  - `Permissions-Policy`: Mematikan akses kamera, mikrofon, dan geolokasi yang tidak diperlukan.

### 2.3 Perlindungan Rahasia & Pengendalian Biaya AI
- [x] **Redaksi Log & Checkpoint Otomatis (`redact_secrets_in_logs`):** Seluruh teks pada log aplikasi, `audit_logs`, `task_checkpoints`, dan laporan kesalahan disaring dari pola API key, Bearer token, kunci privat, serta nilai rahasia yang dikenal.
- [x] **Isolasi Rahasia pada Backup:** Snapshot database (`app.backup`) tidak pernah menyertakan berkas `.env` ke dalam arsip publik tanpa perlindungan terpisah.
- [x] **Budget Gate Berlapis:**
  - `BUDGET_ALLOW_PAID_CALLS=false` dan `BUDGET_MONTHLY_LIMIT=0` secara bawaan.
  - Pembatasan token keluaran maksimum (`AI_MAX_TOKENS_CAP`).
  - Pemeriksaan sisa anggaran spesifik kampanye SEO sebelum memanggil model berbayar; jika harga model tidak diketahui atau estimasi melebihi sisa anggaran, panggilan otomatis diblokir.
  - Tidak ada *fallback* diam-diam ke provider berbayar lain saat terjadi kegagalan.

### 2.4 Kontrol Otonomi Agen, Approval Gate & Anti-Prompt Injection
- [x] **Approval Terikat Hash Payload (`payload_hash` / `body_hash`):** Setiap tindakan berisiko tinggi/kritis (`publish`, `external_outreach`, `spend`) wajib disetujui oleh manusia (`ceo`). Persetujuan mengikat hash SHA-256 dari isi tindakan, berlaku sekali pakai (*single-use*), dan memiliki batas waktu kedaluwarsa (`APPROVAL_TTL_HOURS`, default 24 jam).
- [x] **Agen Tidak Bisa Menyetujui Sendiri:** Upaya persetujuan oleh `agent`, `manager`, `worker`, atau `system` selalu ditolak oleh backend (`agent_cannot_approve`).
- [x] **Tidak Ada Pengiriman Otomatis Tanpa Outbox:** Konten dan pesan outreach yang telah disetujui masuk ke kotak keluar (`outbound_messages`) dengan verifikasi ulang *Product Release Gate*, linter klaim (`check_claims`), batas frekuensi harian, dan daftar jangan-hubungi (*suppression list*).
- [x] **Pertahanan Prompt Injection:** Teks dari halaman web atau dokumen unggahan diberi penanda eksplisit `SUMBER WEB TIDAK TEPERCAYA`, dipisahkan dari instruksi sistem, dan pola kalimat *prompt injection* ditandai sebelum diproses agen.

### 2.5 Keamanan Crawler Web (SSRF-Guard) & Penyimpanan Berkas
- [x] **SSRF-Guard Berlapis (`app/web/`):**
  - Hanya mengizinkan skema `http` dan `https` pada port `80` dan `443`.
  - Menolak `localhost`, IP loopback (`127.0.0.0/8`, `::1`), jaringan privat (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local / metadata cloud (`169.254.169.254`), IPv4-mapped IPv6, serta domain `.local` / `.internal`.
  - Memvalidasi ulang alamat IP setelah resolusi DNS dan pada **setiap langkah redirect** (maksimal 4 redirect).
  - Mematuhi `robots.txt`, membatasi ukuran respons (maks. 500 KB), waktu tunggu (maks. 15 detik), dan kuota permintaan harian (`web_daily_limit`).
- [x] **Keamanan Unggah Berkas & Arsip Backup:**
  - Menolak berkas executable dan SVG, memvalidasi kesesuaian isi terhadap ekstensi (*magic bytes*), menyanitasi nama berkas, serta mencegah *path traversal* (`..`, path absolut, atau symlink) pada ekstraksi tar (`filter="data"`).

### 2.6 Perlindungan Data Pribadi & Kepatuhan UU PDP
- [x] **Minimisasi Data & Filter PII Sensitif:** Menolak input yang memuat NIK/KTP, NPWP, nomor kartu pembayaran (validasi Luhn), tanggal lahir, agama, data kesehatan, serta email pribadi (seperti `@gmail.com`) kecuali berasal dari sumber `inbound`.
- [x] **Penyamaran Kontak Bawaan (Default Masking):** Email dan nomor telepon bisnis prospek disamarkan di seluruh respons API dan tampilan tabel. Pembukaan kontak asli wajib melalui aksi eksplisit yang tercatat di `audit_logs` (`lead.pii_viewed`).
- [x] **Suppression List Berbasis Hash:** Prospek yang meminta *opt-out* atau penghapusan disimpan hanya sebagai hash SHA-256 (`suppression_entries`) agar tidak pernah dihubungi kembali tanpa menyimpan PII asli mereka.

---

## 3. Daftar Periksa Verifikasi Keamanan (Pre-Release Security Checklist)

Jalankan daftar periksa dan perintah otomatis berikut sebelum setiap rilis atau deployment:

```powershell
# 1. Jalankan pemindai rahasia, pemeriksaan .gitignore, bundel klien Next.js, dan audit dependensi
python scripts/audit_security.py --deps

# 2. Jalankan suite pengujian audit keamanan OpenAPI & otorisasi
cd apps/api
.\.venv\Scripts\python.exe -m pytest tests/test_security_audit.py tests/test_web.py tests/test_backup.py
```

| No | Item Pemeriksaan | Target Lulus |
| :--- | :--- | :--- |
| 1 | Semua endpoint `/api/*` yang dilindungi mengembalikan `401 Unauthorized` saat dipanggil tanpa sesi/token atau dengan token salah. | **100% Lulus** |
| 2 | Endpoint `/api/auth/bootstrap` mengembalikan `403 Forbidden` setelah akun pemilik terdaftar. | **100% Lulus** |
| 3 | Login gagal 5x berturut-turut mengunci akun selama 15 menit (`429 Too Many Requests`). | **100% Lulus** |
| 4 | Pemindaian direktori `.next/static` dan repositori Git tidak menemukan `APP_LOCAL_TOKEN`, `GEMINI_API_KEY`, atau kunci privat. | **0 Temuan** |
| 5 | `pip-audit` (Python) dan `npm audit --omit=dev` (Node produksi) bebas dari kerentanan aktif. | **0 Kerentanan Produksi** |
| 6 | SSRF-Guard menolak seluruh 16+ variasi URL internal/loopback/metadata cloud dan redirect ke IP privat. | **100% Lulus** |
| 7 | Panggilan model berbayar ditolak secara deterministik ketika `BUDGET_ALLOW_PAID_CALLS=false` atau melebihi anggaran. | **100% Lulus** |
