# 2. USER FLOW & OPERATIONAL WORKFLOWS

**Nama Produk:** Roihan AI Office  
**Aktor Utama:** Pemilik Bisnis / CEO (Single-Owner)  
**Aktor Sistem:** Marketing Orchestrator & 5 Agen Spesialis Marketing (SEO, Content, Lead Gen/CRM, Campaign/Social, Analytics)  

---

## 1. Alur Inisialisasi & Autentikasi Pemilik Tunggal (Single-Owner Auth Flow)

Sistem menggunakan arsitektur **Single-Owner** di mana hanya ada 1 akun pemilik yang sah di seluruh platform.

```mermaid
flowchart TD
    A["Buka Aplikasi Roihan AI Office (HTTPS)"] --> B{"Apakah Akun Pemilik Sudah Ada di DB?"}
    B -- "Belum Ada (First Run)" --> C["Tampilkan Layar Inisialisasi Akun Pemilik (Bootstrap)"]
    C --> D["Input Nama, Email (wajib cocok OWNER_EMAIL), Password, & BOOTSTRAP_TOKEN"]
    D --> E{"Validasi Token & Email"}
    E -- "Gagal" --> F["Tampilkan Error & Catat di AuditLog"]
    E -- "Berhasil" --> G["Simpan Owner (PBKDF2-HMAC-SHA256, 600k iterasi)"]
    G --> H["Kunci Permanen Endpoint /api/auth/bootstrap (HTTP 403)"]
    H --> I["Buat Sesi di Tabel owner_sessions & Set Cookie HttpOnly"]
    I --> J["Masuk ke Command Center Workspace (/?view=overview)"]

    B -- "Sudah Ada" --> K["Tampilkan Halaman Login Single-Owner"]
    K --> L["Input Email & Kata Sandi"]
    L --> M{"Cek Rate Limit / Lockout"}
    M -- ">= 5x Gagal Beruntun" --> N["Tolak Login: Terkunci 15 Menit (HTTP 429)"]
    M -- "Aman" --> O{"Verifikasi Password"}
    O -- "Salah" --> P["Tambah Counter Gagal & Catat di AuditLog (HTTP 401)"]
    O -- "Benar" --> Q["Reset Counter Gagal, Buat Sesi Baru & Set Cookie HttpOnly"]
    Q --> J
```

### Aturan Sesi & Logout:
- Setiap permintaan dari browser membawa cookie sesi `HttpOnly`, `SameSite=Lax`, `Secure`.
- Saat CEO menekan tombol **Logout** di dock navigasi, sesi di tabel `owner_sessions` langsung dicabut (*revoked*) dan cookie dihapus dari browser.

---

## 2. Navigasi Utama Command Center Workspace

Setelah login, CEO berada di dalam **Unified Command Center** (`/`) dan dapat berpindah tampilan kerja secara instan melalui dock navigasi vertikal:

| Menu Navigasi | Parameter URL / Rute | Tujuan Operasional Utama |
| :--- | :--- | :--- |
| **1. Overview** | `/?view=overview` | Memantau KPI utama, keputusan tertunda (Approval/Outbox), status agen, dan penggunaan kuota AI. |
| **2. Website & Growth** | `/?view=seo` | Mengelola kampanye SEO, menjalankan audit teknis website, meriset keyword, dan meninjau rekomendasi. |
| **3. Content Studio** | `/?view=content` | Mengelola katalog produk, membuat brief & draf konten AI, memvalidasi klaim, dan mengatur kalender konten. |
| **4. Social Media** | `/?view=social` | Menjadwalkan distribusi konten sosial media dan memantau status publikasi per kanal. |
| **5. Campaigns** | `/?view=campaigns` | Merencanakan kampanye pemasaran, mengelola anggaran, dan mencatat metrik hasil kampanye. |
| **6. Leads & CRM** | `/?view=leads` | Mencari prospek B2B dari web/sumber publik, menilai skor prospek, dan mengelola tahapan *sales pipeline*. |
| **7. Email & Automation** | `/?view=email` | Menyusun draf outreach yang dipersonalisasi dan mengelola pengiriman dari Kotak Keluar (*Outbox*). |
| **8. Analytics** | `/?view=analytics` | Menganalisis tren trafik organik, konversi pipeline, dan perhitungan ROI berbasis bukti data. |
| **9. Operations** | `/?view=operations` (`approvals` / `tasks`) | Menyetujui/menolak tindakan berisiko di Approval Center, memantau antrean Task Engine, dan kontrol daya OFF/ON. |
| **10. Settings** | `/?view=settings` (`ai`) | Mengatur kunci & model Google Gemini API, batas anggaran bulanan, akses web agen, dan backup database. |

---

## 3. Alur Pertumbuhan Website & Autonomous SEO (`/?view=seo`)

```mermaid
flowchart TD
    A["CEO Buka Menu Website & Growth (/?view=seo)"] --> B["Buat / Pilih Kampanye SEO (Domain-Locked URL & Anggaran API)"]
    B --> C{"Pilih Tindakan SEO"}
    
    C -- "1. Audit Teknis Website" --> D["Jalankan Audit Situs Terdaftar / Crawler Aman (SSRF-Guarded)"]
    D --> E["Analisis Deterministik: Title, Meta, H1, Canonical, Robots, Sitemap, Alt, JSON-LD"]
    E --> F["Simpan Artefak Audit & Daftar SeoRecommendation Berdasarkan Severity"]
    F --> G["CEO Tinjau Rekomendasi -> Setujui / Tolak / Ekspor Laporan JSON"]

    C -- "2. Riset Kata Kunci & Brief" --> H["Cek Sisa Anggaran Kampanye & Global Budget"]
    H -- "Melebihi Anggaran / Harga Tak Diketahui" --> I["Blokir Panggilan AI Berbayar"]
    H -- "Aman" --> J["Panggil Gemini API via SEO Specialist Agent"]
    J --> K["Validasi Source Grounding (Volume/Kompetisi wajib ada di bukti sumber, jika tidak = NULL)"]
    K --> L["Simpan sebagai Pending SeoKeyword / Content Brief"]
    L --> M["CEO Lakukan Approval Keyword (Manual / Bulk) untuk Masuk ke Content Studio"]
```

---

## 4. Alur Katalog Produk, Gerbang Rilis & Content Studio (`/?view=content`)

Marketing dilarang keras mempromosikan produk yang belum siap atau membuat klaim palsu.

```mermaid
flowchart TD
    A["CEO Buka Produk (/products) & Buat Versi Produk"] --> B["Tambahkan Klaim Fitur Produk"]
    B --> C{"Verifikasi Bukti Klaim / Atestasi CEO"}
    C -- "Belum Ada Bukti" --> D["Status Klaim: UNVERIFIED (Dilarang Dipromosikan)"]
    C -- "Terbukti / Attested" --> E["Status Klaim: VERIFIED / ATTESTED"]
    E --> F["Evaluasi 10 Butir Product Release Gate"]
    F -- "Lolos Gate" --> G["CEO Beri Izin Pemasaran: beta_only atau allowed"]
    G --> H["Sistem Menghasilkan marketing_brief Resmi"]
    
    H --> I["CEO Buka Content Studio (/?view=content) & Minta Draf Konten ke AI"]
    I --> J["Content Marketing Agent Menyusun Draf Hanya dari marketing_brief"]
    J --> K["Pemeriksaan Otomatis Linter Klaim (check_claims)"]
    K -- "Melanggar (Klaim Mutlak / Harga Tak Sah / Lupa Label Beta)" --> L["Koreksi Otomatis Maks 2x -> Jika Tetap Gagal: blocked_by_claim_check"]
    K -- "Lolos Linter" --> M["Status Konten: ready_for_review"]
    M --> N["CEO Ajukan Publikasi -> Masuk ke Approval Center"]
    N --> O["CEO Setujui Approval (Terikat Hash SHA-256 Isi Konten)"]
    O --> P["Masuk Kotak Keluar (queued_manual) -> CEO Publikasikan & Tandai published_manual"]
```

---

## 5. Alur Akuisisi Prospek B2B, CRM & Outreach (`/?view=leads` & `/?view=email`)

```mermaid
flowchart TD
    A["CEO Buka Leads & CRM (/?view=leads)"] --> B{"Metode Akuisisi Prospek"}
    B -- "Cari dari Web (Otomatis)" --> C["Input Kriteria Bisnis & Kota -> Cari via Tavily / Brave Search API"]
    B -- "Ekstraksi Teks / Manual" --> D["Tempel Teks Sumber Publik Sah / Input Form"]
    
    C --> E["Backend Ambil Halaman Web via SSRF-Guard & Tandai Konten Tidak Tepercaya"]
    E --> F["Lead Generation Agent Ekstrak Perusahaan & Kontak Bisnis"]
    D --> F
    
    F --> G{"Filter Kepatuhan & UU PDP"}
    G -- "Mengandung NIK / Email Pribadi / Ada di Suppression List / Tanpa Bukti" --> H["Tolak Kandidat / Buang Field Karangan"]
    G -- "Valid & Sah" --> I["Hitung Skor Kecocokan Deterministik (0-100) & Simpan Lead (Kontak Tersamar)"]
    
    I --> J["Teruskan ke Sales (Syarat: Qualified, Skor >= 40, Provenance Lengkap)"]
    J --> K["Sales Agent Buat Draf Outreach dari marketing_brief + Kalimat Unsubscribe Wajib"]
    K --> L["Lolos check_claims -> CEO Minta Approval Pengiriman"]
    L --> M["CEO Setujui di Approval Center -> Masuk Kotak Keluar (outbound_messages)"]
    M --> N["CEO Klik 'Buka Email / WhatsApp untuk Kirim' -> Kirim & Tandai 'Sudah Saya Kirim'"]
    N --> O["Tercatat sebagai Interaksi Nyata (email_out) -> Prospek Naik Tahap di Pipeline"]
```

### Penanganan Opt-Out (Berhenti Dihubungi):
- Jika prospek menolak (*opt-out*), CEO menekan tombol **Opt-Out**.
- Sistem menyimpan hash SHA-256 email/domain ke `suppression_entries`, membatalkan seluruh pesan keluar yang tertunda untuk prospek tersebut, dan memblokir pendaftaran ulang secara permanen.

---

## 6. Alur Persetujuan Manusia (Approval Center Lifecycle)

1. Setiap tugas dengan tingkat risiko `High` atau `Critical` (misalnya `publish`, `external_outreach`, `spend`) otomatis berhenti dengan status `pending_approval`.
2. Sistem membuat entri di tabel `approvals` yang mengikat **sidik jari SHA-256 (`payload_hash`)** dari rincian tindakan.
3. CEO membuka `/?view=approvals`, membaca isi persis yang akan dilakukan, lalu memilih **Setujui (`Approve`)** atau **Tolak (`Reject`)**:
   - **Jika Disetujui:** Task berpindah ke `queued`. Saat worker mengeksekusi task, worker memverifikasi ulang bahwa approval belum kedaluwarsa (TTL 24 jam), belum pernah dipakai, dan hash isi task tidak berubah.
   - **Jika Isi Task Diubah Setelah Disetujui:** Approval otomatis gugur dan task wajib meminta approval baru.
   - **Jika Ditolak atau Kedaluwarsa:** Task langsung dibatalkan (`cancelled`) tanpa pernah dieksekusi.

---

## 7. Alur Kontrol Daya Kantor (Office Power Control: OFF / ON & Recovery)

Digunakan saat CEO ingin menjeda seluruh aktivitas agen AI atau memulihkan pekerjaan setelah gangguan:

1. **Menekan Tombol OFF (`POST /api/power/off`):**
   - Status global berpindah dari `RUNNING` ke `PAUSING`.
   - Scheduler berhenti mengambil tugas baru.
   - Tugas yang sedang berjalan diberi waktu tenggang (`POWER_PAUSE_GRACE_S`) untuk menyelesaikan langkah aman, lalu diinterupsi secara terkontrol (`interrupted` dengan alasan `paused`).
   - Sistem menulis dan memverifikasi integritas `task_checkpoints` (SHA-256) di database.
   - Setelah terverifikasi, status global berubah menjadi `PAUSED`.
2. **Menekan Tombol ON (`POST /api/power/on`):**
   - Status global berubah menjadi `RESUMING`.
   - Sistem memvalidasi database, dependensi, dan checkpoint terakhir.
   - Tugas yang sudah `completed` tidak pernah dijalankan ulang.
   - Tugas aman/idempoten yang terputus dipulihkan kembali ke antrean (`queued`).
   - Tugas berisiko tinggi atau operasi eksternal yang statusnya belum pasti ditandai sebagai `RecoveryItem` (`RECOVERY_REQUIRED`) agar CEO memilih tindakan manual (*Antre Ulang*, *Batalkan*, atau *Konfirmasi Sudah/Belum Terjadi*).
