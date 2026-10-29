# 1. PRODUCT REQUIREMENTS DOCUMENT (PRD)

**Nama Produk:** Roihan AI Office  
**Direktori Repositori:** `roihan-ai-office`  
**Versi Spesifikasi:** 2.1 (Konsolidasi Master Addendum v1.0, v1.1, v2.0, dan v2.1)  
**Fokus Produk:** AI Marketing Operations, Autonomous Website Growth & Modern Minimalist SaaS Platform  
**Mode Akses:** Single-Owner (1 Akun Pemilik / CEO) — Online Cloud (Rp0 Free-Tier) & Local-Ready  

---

## 1. Visi & Tujuan Produk

**Roihan AI Office** adalah platform komando operasional pemasaran berbasis AI (*AI Marketing Command Center*) dan pertumbuhan website otonom (*Autonomous Website Growth*) yang dirancang khusus untuk pemilik bisnis tunggal (CEO / Single-Owner).

Produk ini **bukan** sekadar chatbot, generator teks biasa, atau dashboard mock statis, melainkan sistem eksekusi terukur yang mampu:
1. Menerima target pemasaran dan pertumbuhan website dari pemilik bisnis.
2. Menganalisis website (audit SEO teknis & on-page), data prospek, produk, audiens, dan konteks pasar.
3. Menyusun strategi pemasaran serta memecahnya menjadi tugas (*tasks*) terukur dengan dependensi yang jelas.
4. Menjalankan pekerjaan melalui tim agen AI spesialis pemasaran dan integrasi yang diizinkan.
5. Memverifikasi bukti hasil kerja secara deterministik (linter klaim produk, source grounding, validasi skema).
6. Mengukur perubahan performa nyata (impresi, klik, CTR, posisi, konversi, pipeline, revenue).
7. Menahan setiap tindakan berisiko tinggi atau eksternal melalui **Approval Gate** manusia (CEO) yang terikat pada hash isi (*payload SHA-256*).
8. Menyajikan progres, kendala, penggunaan kuota/anggaran AI, dan hasil aktual melalui antarmuka **Modern Minimalist SaaS** yang bersih dan responsif lintas perangkat (HP, tablet, laptop).

---

## 2. Prinsip Utama Produk (Core Principles)

1. **Marketing-Only AI Organization:** Seluruh organisasi kerja AI di dalam aplikasi berfokus 100% pada operasional pemasaran dan pertumbuhan website. Modul *software engineering* lama dinonaktifkan dari antarmuka operasional pengguna.
2. **Human-in-the-Loop (CEO sebagai Pengambil Keputusan Akhir):** Agen AI hanya mengusulkan, menganalisis, dan menyiapkan draf. Tindakan eksternal atau berisiko (publikasi, pengiriman outreach, perubahan produksi, pemakaian API berbayar) wajib melewati persetujuan eksplisit CEO.
3. **Zero Unverified Claims & Anti-Hallucination:**
   - Produk hanya boleh dipromosikan jika lolos **Product Release Gate** dan hanya menggunakan klaim fitur yang terverifikasi (`marketing_brief` + `check_claims`).
   - Riset pasar, ekstraksi prospek, dan riset kata kunci wajib memiliki bukti kutipan (*source grounding*) dari materi sumber.
   - Metrik yang belum tersedia wajib ditampilkan sebagai `null` / *"Belum ada data"*, bukan dipalsukan menjadi angka `0` atau angka karangan.
4. **Gemini-Powered & Budget-Safe:** Menggunakan **Google Gemini API** (`gemini-2.5-flash` untuk tugas rutin dan `gemini-2.5-pro` untuk analisis strategis/kompleks) melalui adapter terpusat, dilengkapi pengaman anggaran bulanan (`BUDGET_MONTHLY_LIMIT`), saklar `BUDGET_ALLOW_PAID_CALLS`, serta batas anggaran per kampanye SEO.
5. **Single-Owner Security:** Hanya mengizinkan tepat satu akun pemilik sah di dalam sistem. Pendaftaran publik ditutup permanen setelah proses *bootstrap* perdana selesai.
6. **Modern Minimalist SaaS UI/UX:** Desain bersih, kontras tinggi (standar WCAG 2.2 AA), bebas dari elemen dekoratif cyberpunk/neon yang mengganggu keterbacaan data analitik.

---

## 3. Struktur Organisasi Agen AI (Marketing-Only)

Sistem menggunakan **6 peran logis agen pemasaran** yang dikoordinasikan oleh satu orchestrator (tidak mengharuskan 6 model berjalan terus-menerus, melainkan dipanggil *on-demand* melalui *Task Engine*):

| No | Peran Agen (`Role`) | Tanggung Jawab Utama | Batas Kewenangan (Deny-by-Default) |
| :--- | :--- | :--- | :--- |
| 1 | **Marketing Manager / Orchestrator** | Memahami tujuan bisnis/marketing, memecah tujuan menjadi *draft tasks* beserta dependensi, memilih agen spesialis, mengevaluasi hasil, dan menyusun laporan eksekutif. | Tidak boleh melewati approval, mengubah anggaran, atau mengklaim tugas selesai tanpa bukti. |
| 2 | **SEO & Website Growth Agent** (`seo_specialist`) | Audit SEO teknis & on-page deterministik, pengelolaan kampanye SEO, riset & pengelompokan keyword berbasis bukti, penyusunan *SEO content brief*, dan rekomendasi prioritas optimasi. | Tidak boleh menjanjikan peringkat/trafik, tidak boleh mengarang volume/kompetisi keyword, dan tidak boleh mengubah produksi tanpa approval. |
| 3 | **Content Marketing Agent** | Menyusun strategi konten, kalender editorial, dan draf konten (artikel, landing page, sosial media, newsletter, FAQ, naskah demo) berdasarkan `marketing_brief`. | Wajib lolos linter klaim (`check_claims`); tidak boleh mengklaim draf sebagai sudah dipublikasikan. |
| 4 | **Lead Generation & CRM Agent** | Mencari dan mengekstrak prospek B2B dari sumber publik sah (input manual atau pencarian web terkendali via Tavily/Brave), mencatat *provenance*, memvalidasi kepatuhan UU PDP, dan menilai skor kecocokan. | Dilarang mengambil email pribadi (kecuali inbound), NIK/data sensitif, atau menghubungi prospek di *suppression list*. |
| 5 | **Campaign & Social Media Agent** | Merencanakan kampanye lintas kanal, menyiapkan jadwal distribusi, menyusun draf outreach B2B yang dipersonalisasi, serta melacak performa kampanye. | Tidak boleh mengirim pesan/publikasi otomatis tanpa approval CEO dan *outbox dispatch*. |
| 6 | **Marketing Analytics Agent** (`marketing_analytics`) | Mengumpulkan metrik aktual (impresi, klik, CTR, posisi, konversi, pipeline, biaya, revenue), membandingkan dengan baseline, dan mengevaluasi efektivitas tindakan. | Hanya menghitung ROI/CAC jika data biaya dan atribusi pendapatan benar-benar tercatat. |

> [!NOTE]
> Selain 6 peran logis pemasaran di atas, Task Engine backend juga menyediakan 5 peran pendukung Engineering (`analyst`, `developer`, `qa`, `reviewer`, `reporter`) yang dapat dijadwalkan untuk pemeliharaan teknis internal, integrasi API, dan verifikasi otomatis. Total terdapat **12 peran spesialis terdaftar** di Task Engine.

---

## 4. Cakupan Modul Fungsional (Functional Scope)

Seluruh fitur diakses melalui satu **Unified Command Center Workspace** (`/`) dengan navigasi *dock* vertikal dan tampilan modular (`/?view=...`):

### 4.1 Overview (`/?view=overview`)
- Ringkasan KPI pemasaran aktual, kampanye aktif, tugas yang sedang berjalan, serta item yang membutuhkan keputusan CEO (approval tertunda, draf siap tinjau, kotak keluar, item pemulihan).
- Pantauan pemakaian kuota/anggaran AI (24 jam terakhir & bulanan) dan status kesehatan sistem/worker secara real-time.

### 4.2 Website & Growth / Autonomous SEO (`/?view=seo`)
- **Manajemen Kampanye SEO (`SeoCampaign`):** Konfigurasi website terkunci domain (*domain-locked*), target marketing, anggaran API per kampanye, dan status akses (`READ_ONLY`, `STAGING_WRITE`, `APPROVED_PRODUCTION_WRITE`).
- **Audit SEO Teknis & On-Page:** Pemeriksaan deterministik atas `title`, `meta description`, `h1`, `canonical`, `noindex`, `lang`, `viewport`, `img alt`, `Open Graph`, `JSON-LD`, tautan internal, `robots.txt`, `sitemap.xml`, dan `hreflang` (baik lewat unggahan HTML, situs proyek terdaftar `Site`, maupun crawler aman berpelindung SSRF).
- **Keyword Research & Rekomendasi (`SeoKeyword` & `SeoRecommendation`):** Penyimpanan kata kunci beserta bukti sumber (*provenance*), persetujuan kata kunci (manual/massal), daftar rekomendasi perbaikan berurut tingkat keparahan (*severity*), dan ekspor laporan JSON.

### 4.3 Content Studio (`/?view=content`)
- Pembuatan dan pengelolaan aset konten (`social_post`, `article`, `landing_page`, `demo_script`, `newsletter`) yang terikat pada produk di **Product Catalog** (`/products`).
- **Product Release Gate & Claim Linter:** Memastikan hanya produk berizin (`beta_only` atau `allowed`) dan fitur terverifikasi yang dapat dijadikan bahan promosi.
- Siklus status konten: `draft` -> `ready_for_review` (setelah lolos `check_claims`) -> `pending_approval` -> `queued_manual` (di kotak keluar) -> `published_manual`.

### 4.4 Social Media (`/?view=social`)
- Kalender publikasi sosial media, manajemen kesiapan konten lintas kanal (LinkedIn, Instagram, Blog, Website), status koneksi kanal yang jujur (`not_connected` hingga terverifikasi), dan pelacakan engagement.

### 4.5 Campaigns & Advertising (`/?view=campaigns` & `/marketing/campaigns/[id]`)
- Perencanaan kampanye pemasaran per produk, penetapan jadwal, target, anggaran (default Rp0 untuk organik; iklan berbayar terkunci approval), dan pencatatan metrik kampanye (`impressions`, `clicks`, `conversions`, `cost`, `revenue`, perhitungan `ROI` otomatis jika syarat terpenuhi).

### 4.6 Leads & CRM (`/?view=leads` & `/marketing/leads/[id]`)
- **Akuisisi Prospek B2B:** Input manual, ekstraksi teks sumber publik, atau pencarian web terkendali (integrasi **Tavily / Brave Search API** dengan SSRF-guard dan kepatuhan `robots.txt`).
- **Skor Deterministik (0–100):** Penilaian otomatis transparan berdasarkan kecocokan produk (30), ukuran perusahaan (15), kualitas sumber (15), kualitas kontak (20), kelengkapan (10), dan kesegaran data (10).
- **Kepatuhan Privasi (UU PDP No. 27/2022):** Penolakan otomatis data sensitif (NIK, kartu kredit, email pribadi non-inbound), penyamaran kontak (*PII masking*) secara default dengan audit log (`lead.pii_viewed`) saat dibuka, daftar jangan-hubungi (*suppression list* berbasis hash SHA-256), serta kebijakan retensi/anonimisasi (180 hari tanpa interaksi / 730 hari pasca-interaksi).
- **Sales Pipeline:** Transisi tahap prospek berbasis bukti interaksi nyata (`new -> qualified -> contacted -> meeting -> opportunity -> won/lost`) dan pengelolaan peluang penjualan (`sales_opportunities`).

### 4.7 Email & Automation (`/?view=email`)
- Penyusunan draf outreach B2B oleh agen Sales berdasarkan `marketing_brief` dengan kalimat *opt-out/unsubscribe* wajib.
- Manajemen **Kotak Keluar (`outbound_messages`):** Pesan yang telah disetujui CEO masuk ke antrean siap kirim (terintegrasi pintasan kirim via Email/WhatsApp) dengan batas frekuensi harian (maks. 10 outreach/hari, jeda 14 hari ke prospek yang sama).

### 4.8 Analytics & Intelligence (`/?view=analytics`)
- Laporan analitik pemasaran deterministik yang merangkum corong konversi prospek (*lead funnel*), win rate peluang, performa kampanye, dan metrik pencarian organik (`seo_metrics`: impresi, klik, CTR, sesi organik, posisi rata-rata).

### 4.9 Operations: Approvals, Tasks & Power Control (`/?view=operations`, `/?view=approvals`, `/?view=tasks`)
- **Approval Center:** Peninjauan tindakan berisiko tinggi/kritis lengkap dengan pratinjau payload, hash SHA-256, masa berlaku (TTL 24 jam), dan pemakaian sekali pakai (*single-use*).
- **Task Board & Detail (`/tasks/[id]`):** Pemantauan siklus hidup tugas (`draft`, `pending_approval`, `queued`, `running`, `blocked`, `completed`, `failed`, `cancelled`, `interrupted`), log percobaan, keputusan *Model Router*, dan laporan 15 bagian.
- **Office Power Control (OFF/ON & Recovery):** Kontrol penghentian sementara seluruh aktivitas agen secara aman (`RUNNING`, `PAUSING`, `PAUSED`, `RESUMING`, `RECOVERY_REQUIRED`, `ERROR`) dengan penyimpanan *checkpoint* persisten dan pemulihan otomatis pasca-*restart*/*crash*.

### 4.10 Settings & AI Control Center (`/?view=settings` & `/?view=ai`)
- Konfigurasi provider **Google Gemini API**, pemilihan model (`gemini-2.5-flash` / `gemini-2.5-pro`), pengaturan batas anggaran bulanan (`BUDGET_MONTHLY_LIMIT`), saklar akses web agen (Tavily/Brave Search + kuota harian), manajemen backup snapshot database, dan pengelolaan sesi akun pemilik.

### 4.11 Mode Visualisasi Ruang Kerja Virtual (Opsional: `/office`)
- Selain tampilan antarmuka utama Modern Minimalist SaaS Command Center, sistem menyediakan rute visualisasi ruang kerja kantor virtual (`/office`) berbasis **Three.js** (3D) dengan fallback Canvas (2D).
- Menampilkan denah kantor tempat representasi avatar setiap agen spesialis berada di mejanya masing-masing dan mencerminkan status tugas backend secara jujur (`idle`, `working`, `awaiting_approval`, `paused`, `error`).
- Dilengkapi mode interaktif penjelajahan kantor (*walk mode* orang ketiga dan orang pertama), pemilihan level kualitas rendering (low, med, high), serta panel kendali daya kantor (*Office Power Control*).

---

## 5. Kebutuhan Non-Fungsional (Non-Functional Requirements)

1. **Desain Visual & Aksesibilitas:**
   - Menggunakan sistem desain **Modern Minimalist SaaS**: latar belakang *warm charcoal* (`#131517`), kartu permukaan (`#1e2226` / `#ffffff`), aksen oranye energik (`#ff6b35` / `#ff5722`), sudut membulat (`14px–18px`), dan font **Montserrat**.
   - Memenuhi standar kontras dan navigasi keyboard **WCAG 2.2 AA** serta responsif penuh di layar mobile, tablet, dan desktop tanpa *horizontal overflow*.
2. **Keamanan & Privasi:**
   - Autentikasi **Single-Owner** berbasis sesi `HttpOnly` cookie dan `PBKDF2-HMAC-SHA256` (600.000 iterasi), dilengkapi kunci *brute-force* (15 menit setelah 5x gagal login).
   - Kunci API (`GEMINI_API_KEY`, `APP_LOCAL_TOKEN`, kunci Tavily/Brave) hanya disimpan di sisi server/environment, disamarkan di seluruh log/checkpoint (`redact_secrets_in_logs`), dan tidak pernah dikirim ke bundel browser.
3. **Reliabilitas & Ketersediaan (Zero-Cost Cloud Ready):**
   - Berjalan di infrastruktur cloud gratis (**Vercel Free + Render Free + Neon Serverless PostgreSQL**) maupun lingkungan lokal tanpa perubahan kode.
   - Tahan terhadap *cold-start* dan *ephemeral filesystem* karena seluruh state tugas, sesi, dan checkpoint disimpan 100% secara transaksional di database PostgreSQL.

---

## 6. Kriteria Penerimaan Akhir Produk (Acceptance Criteria)

1. Identitas produk konsisten menggunakan nama **Roihan AI Office** dan direktori `roihan-ai-office`.
2. Seluruh navigasi dan organisasi agen AI berfokus 100% pada operasional **Marketing & Website Growth**.
3. Runtime tidak lagi bergantung pada instalasi lokal Ollama; **Google Gemini API** dan **FakeProvider** (untuk pengujian) berfungsi penuh melalui adapter terpusat.
4. Sistem **Single-Owner Authentication** aktif: bootstrap akun pemilik otomatis terkunci permanen setelah 1 akun terdaftar.
5. Seluruh halaman aktif menggunakan **Modern Minimalist SaaS Design System**, responsif, dan bebas dari gaya cyberpunk lama.
6. Tidak ada data mock yang disajikan sebagai data produksi; nilai `0`, `null`, dan *belum tersedia* dibedakan secara tegas.
7. Seluruh tindakan berisiko tinggi/eksternal tertahan di **Approval Center** dan terikat pada hash isi.
8. **Office Power Control (OFF/ON)** dan **Backup/Restore** database terverifikasi mampu memulihkan state kerja tanpa kehilangan data atau duplikasi tindakan eksternal.
