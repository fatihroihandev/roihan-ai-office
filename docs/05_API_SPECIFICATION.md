# 5. API SPECIFICATION & WEBSOCKET CONTRACTS

**Nama Produk:** Roihan AI Office  
**Base URL Produksi (Backend):** `https://roihan-ai-office-api.onrender.com`  
**Base URL Lokal (Backend):** `http://127.0.0.1:8000`  
**Proxy Frontend (Next.js):** `/api/*` (Meneruskan request secara aman dari sisi server ke Backend)  
**Format Pertukaran Data:** JSON (`application/json`, UTF-8)  

---

## 1. Standar Autentikasi, Keamanan & Error

### 1.1 Mekanisme Autentikasi
Seluruh endpoint `/api/*` **(kecuali `GET /api/health` dan endpoint autentikasi publik `/api/auth/status`, `/api/auth/bootstrap`, `/api/auth/login`)** wajib terautentikasi melalui salah satu mekanisme berikut:
1. **Single-Owner Session Cookie (`HttpOnly`):** Cookie sesi yang diterbitkan saat login pemilik dan diverifikasi terhadap tabel `owner_sessions`.
2. **Bearer Token (`Authorization: Bearer <APP_LOCAL_TOKEN>`):** Digunakan oleh SSR Proxy Next.js atau CLI administratif internal, diverifikasi dengan perbandingan waktu-konstan (`secrets.compare_digest`).

### 1.2 Kode Status HTTP Standar
| Kode HTTP | Arti | Contoh Kondisi |
| :--- | :--- | :--- |
| `200 OK` / `201 Created` | Permintaan berhasil diproses | Data berhasil dibaca, dibuat, atau diperbarui. |
| `400 Bad Request` / `422 Unprocessable Entity` | Input tidak valid atau melanggar aturan skema/kebijakan | Format URL salah, field wajib kosong, atau melanggar aturan PII/UU PDP. |
| `401 Unauthorized` | Belum terautentikasi | Sesi kedaluwarsa, cookie tidak ada, atau Bearer token salah. |
| `403 Forbidden` | Tindakan dilarang secara permanen oleh aturan sistem | Mencoba memanggil `/api/auth/bootstrap` setelah akun pemilik sudah terdaftar, atau agen mencoba menyetujui approval. |
| `404 Not Found` | Entitas tidak ditemukan | ID task, kampanye, prospek, atau produk tidak ditemukan. |
| `409 Conflict` | Konflik state atau gerbang kebijakan belum terpenuhi | Transisi status task tidak sah, *Product Release Gate* belum lulus, atau task aktif sudah berjalan di kampanye SEO yang sama. |
| `429 Too Many Requests` | Batas frekuensi terlampaui | Akun terkunci 15 menit setelah 5x gagal login, atau batas kuota harian outreach/web terlampaui. |

---

## 2. Spesifikasi Endpoint Berdasarkan Modul

### 2.1 Kesehatan Sistem & Autentikasi Single-Owner (`/api/health` & `/api/auth/*`)

| Method | Endpoint | Deskripsi | Auth Wajib |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Memeriksa status kesehatan aplikasi, konektivitas database PostgreSQL, dan status konfigurasi AI provider (tanpa membocorkan data sensitif). | Tidak |
| `GET` | `/api/auth/status` | Memeriksa apakah akun pemilik sudah di-bootstrap (`bootstrapped: true/false`) dan apakah sesi saat ini terautentikasi. | Tidak |
| `POST` | `/api/auth/bootstrap` | **Sekali Pakai:** Membuat akun pemilik tunggal pertama kali. Membutuhkan `full_name`, `email` (wajib cocok dengan `OWNER_EMAIL`), `password` (min. 8 karakter), dan `bootstrap_token`. Otomatis terkunci (`403 Forbidden`) selamanya setelah 1 akun dibuat. | Tidak (Wajib `BOOTSTRAP_TOKEN`) |
| `POST` | `/api/auth/login` | Login pemilik tunggal dengan `email` dan `password`. Mengatur cookie sesi `HttpOnly`. Mengembalikan `429` jika gagal 5x berturut-turut (terkunci 15 menit). | Tidak |
| `POST` | `/api/auth/logout` | Mencabut (*revoke*) sesi aktif di tabel `owner_sessions` dan menghapus cookie sesi dari browser. | Ya |
| `GET` | `/api/auth/me` | Mengambil profil akun pemilik yang sedang login beserta informasi sesi aktif. | Ya |

---

### 2.2 Dashboard Command Center & Real-Time Events (`/api/dashboard/*` & `/api/events/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/dashboard` | Mengambil potret konsisten seluruh sistem: status 6 peran agen marketing, hitungan task per status, daftar keputusan yang menunggu CEO (approval, draf siap tinjau, kotak keluar, retensi, recovery item), ringkasan KPI marketing, penggunaan AI 24 jam, dan status `power`. |
| `GET` | `/api/dashboard/insights` | Mengambil data analitik teragregasi untuk grafik Command Center (distribusi status task, tingkat keberhasilan 7 hari, alur tugas 14 hari, corong konversi prospek, penggunaan AI per jam). |
| `GET` | `/api/events?since={seq}` | Mengambil daftar event berurutan sejak nomor `seq` tertentu untuk sinkronisasi *catch-up* setelah koneksi terputus. |
| `POST` | `/api/ws/ticket` | Menerbitkan tiket sekali pakai (masa berlaku 30 detik) agar browser dapat membuka koneksi WebSocket tanpa mengekspos token utama. |
| `WS` | `/api/ws?ticket={ticket}` | Kanal WebSocket real-time (memvalidasi tiket sekali pakai dan header `Origin`). |

---

### 2.3 Website & Growth / Autonomous SEO (`/api/marketing/seo/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/marketing/seo/campaigns` | Menampilkan daftar seluruh kampanye SEO (`SeoCampaign`) beserta status, target domain, penggunaan anggaran API, dan ringkasan keyword/rekomendasi. |
| `POST` | `/api/marketing/seo/campaigns` | Membuat kampanye SEO baru (default `autonomy_level: READ_ONLY`, website terkunci pada domain yang ditentukan). |
| `GET` | `/api/marketing/seo/campaigns/{id}` | Mengambil detail kampanye SEO, daftar kata kunci (`SeoKeyword`), rekomendasi (`SeoRecommendation`), riwayat audit, dan event log (`SeoCampaignEvent`). |
| `PATCH` | `/api/marketing/seo/campaigns/{id}` | Memperbarui konfigurasi kampanye, anggaran API, atau transisi status (`draft`, `active`, `paused`, `completed`, `archived`). |
| `POST` | `/api/marketing/seo/campaigns/{id}/tasks/audit` | Menjalankan tugas audit SEO teknis pada situs kampanye (mencegah duplikasi jika sudah ada task aktif pada kampanye tersebut). |
| `POST` | `/api/marketing/seo/campaigns/{id}/tasks/keywords` | Menjalankan tugas riset kata kunci & rencana konten berbasis bukti sumber (memeriksa kecukupan anggaran kampanye & global sebelum memanggil Gemini API). |
| `POST` | `/api/marketing/seo/campaigns/{id}/keywords` | Menambahkan kata kunci manual ke dalam kampanye SEO. |
| `POST` | `/api/marketing/seo/campaigns/{id}/keywords/approve` | Menyetujui atau menolak kata kunci yang diusulkan (mendukung persetujuan tunggal maupun massal/*bulk*). |
| `POST` | `/api/marketing/seo/recommendations/{rec_id}/decision` | Menyetujui atau menolak rekomendasi perbaikan SEO dari hasil audit. |
| `GET` | `/api/marketing/seo/campaigns/{id}/export` | Mengekspor laporan lengkap kampanye SEO (audit, keyword, rekomendasi, riwayat) dalam format JSON. |
| `GET` | `/api/marketing/seo/sites` | Menampilkan daftar situs terdaftar (`Site`, termasuk portofolio/website bisnis) dan riwayat artefak auditnya. |
| `POST` | `/api/marketing/seo/audit` | Menjalankan audit SEO teknis deterministik atas HTML, `robots.txt`, dan `sitemap.xml` yang dikirimkan. |
| `POST` | `/api/marketing/seo/metrics` | Mencatat KPI pencarian organik manual (`impressions`, `clicks`, `organic_sessions`, `conversions`, `avg_position`) untuk periode `YYYY-MM`. |

---

### 2.4 Leads, CRM, Pencarian Web & Kepatuhan UU PDP (`/api/marketing/*` & `/api/web/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/marketing/leads` | Menampilkan daftar prospek B2B beserta skor kecocokan (`fit_score`), tahap pipeline, sumber *provenance*, dan kontak yang disamarkan (*masked*). |
| `POST` | `/api/marketing/leads` | Menambahkan prospek B2B baru (memvalidasi sumber yang diizinkan, menolak PII sensitif/email pribadi non-inbound, memeriksa *suppression list*, dan menghitung skor deterministik 0–100). |
| `GET` | `/api/marketing/leads/{id}` | Mengambil rincian lengkap prospek, rincian komponen skor, riwayat interaksi, peluang terkait, dan draf outreach. |
| `POST` | `/api/marketing/leads/{id}/reveal-pii` | Membuka kontak bisnis asli (email/telepon lengkap) untuk CEO/Sales dan otomatis mencatat event `lead.pii_viewed` di `audit_logs`. |
| `POST` | `/api/marketing/leads/{id}/interactions` | Mencatat interaksi nyata (`note`, `email_out`, `email_in`, `call`, `meeting`) sebagai syarat bukti kenaikan tahap prospek. |
| `POST` | `/api/marketing/leads/{id}/stage` | Mengubah tahap prospek (`new -> qualified -> contacted -> meeting`, `disqualified`) berdasarkan bukti interaksi yang tercatat. |
| `POST` | `/api/marketing/leads/{id}/handoff-sales` | Meneruskan prospek yang memenuhi syarat (`qualified`, skor >= 40, provenance sah) ke Sales Pipeline. |
| `POST` | `/api/marketing/leads/{id}/opt-out` | Memasukkan hash email/domain prospek ke `suppression_entries` (daftar jangan-hubungi permanen) dan membatalkan seluruh pesan keluar yang tertunda. |
| `POST` | `/api/marketing/leads/extract` | Menjalankan agen *Lead Generation* untuk mengekstrak prospek dari teks sumber publik yang ditempel (wajib *source grounding*). |
| `POST` | `/api/web/prospect-search` | Mencari prospek B2B langsung dari web publik menggunakan **Tavily / Brave Search API** (melalui SSRF-guard), mengekstrak kontak yang tertulis, dan menyiapkan draf outreach. |
| `GET` | `/api/marketing/opportunities` | Menampilkan daftar peluang penjualan (`sales_opportunities`) di pipeline (`qualification -> proposal -> negotiation -> won/lost`). |
| `POST` | `/api/marketing/retention/apply` | Menjalankan anonimisasi data pribadi prospek yang telah melewati batas retensi (180 hari tanpa interaksi / 730 hari pasca-interaksi). |

---

### 2.5 Katalog Produk, Content Studio, Kampanye & Outbox (`/api/products/*` & `/api/marketing/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/products` | Membaca daftar produk atau membuat produk baru (`owned_product` / `service`). |
| `POST` | `/api/products/{id}/versions` | Menambahkan versi produk baru beserta status pengembangannya (`draft` s/d `released`). |
| `POST` | `/api/products/{id}/features` | Menambahkan klaim fitur produk dan menautkan bukti verifikasi atau atestasi CEO. |
| `POST` | `/api/products/{id}/permission` | Mengevaluasi 10 syarat *Product Release Gate* dan menetapkan izin pemasaran (`not_allowed`, `beta_only`, `allowed`). |
| `GET` | `/api/products/{id}/brief` | Mengambil `marketing_brief` resmi yang menjadi satu-satunya acuan fakta bagi agen pemasaran. |
| `POST` | `/api/products/{id}/check-claims` | Menjalankan linter klaim (`check_claims`) terhadap teks draf promosi. |
| `GET` / `POST` | `/api/marketing/content` | Menampilkan daftar aset konten atau menugaskan *Content Marketing Agent* membuat draf konten baru (`social_post`, `article`, `landing_page`, `demo_script`, `newsletter`). |
| `POST` | `/api/marketing/content/{id}/request-publish` | Mengajukan draf konten yang sudah lolos `check_claims` (`ready_for_review`) ke **Approval Center** dengan mengikat `body_hash`. |
| `GET` / `POST` | `/api/marketing/outreach` | Menampilkan atau membuat draf pesan outreach B2B melalui agen Sales (otomatis menyertakan kalimat *unsubscribe*). |
| `POST` | `/api/marketing/outreach/{id}/request-send` | Mengajukan draf outreach ke **Approval Center** untuk masuk ke kotak keluar. |
| `GET` | `/api/marketing/outbox` | Menampilkan daftar pesan outreach dan publikasi konten yang sudah disetujui (`queued_manual`). |
| `POST` | `/api/marketing/outbox/{id}/dispatch` | Mencatat bahwa pesan/konten di kotak keluar telah dikirim/dipublikasikan oleh CEO (`dispatched_manual` / `published_manual`). |
| `GET` / `POST` | `/api/marketing/campaigns` | Membaca atau membuat kampanye pemasaran dan mencatat metrik kinerja kampanye (`campaign_metrics`). |
| `GET` | `/api/marketing/analytics` | Mengambil laporan metrik pemasaran komprehensif (pipeline, win rate, kampanye, ROI jika biaya & pendapatan tercatat). |

---

### 2.6 Task Engine, Approval Center & Office Power Control (`/api/tasks/*`, `/api/approvals/*`, `/api/power/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/tasks` | Membaca daftar tugas (dengan filter status/proyek/role) atau membuat tugas baru. |
| `POST` | `/api/tasks/plan` | Menugaskan *Marketing Orchestrator* memecah tujuan bisnis/marketing menjadi daftar *draft tasks* beserta dependensinya. |
| `POST` | `/api/tasks/{id}/queue` | Mengantrekan task berstatus `draft` (otomatis masuk `pending_approval` jika berisiko `High`/`Critical`). |
| `POST` | `/api/tasks/{id}/cancel` | Membatalkan task yang sedang antre atau menghentikan task yang sedang berjalan secara aman. |
| `POST` | `/api/tasks/{id}/retry` | Mencoba ulang task yang `failed` atau `blocked` (meminta approval baru jika berisiko tinggi). |
| `GET` | `/api/tasks/{id}/report` | Mengambil laporan terstruktur 15 bagian untuk task terkait. |
| `GET` | `/api/approvals` | Menampilkan daftar permintaan persetujuan (`pending`, `approved`, `rejected`, `expired`, `cancelled`) beserta rincian payload dan hash SHA-256. |
| `POST` | `/api/approvals/{id}/approve` | Menyetujui tindakan berisiko (hanya dapat dipanggil oleh CEO; memindahkan task ke `queued`). |
| `POST` | `/api/approvals/{id}/reject` | Menolak tindakan berisiko (membatalkan task terkait dan mencatat alasan di `audit_logs`). |
| `GET` | `/api/power` | Membaca status daya global kantor (`RUNNING`, `PAUSING`, `PAUSED`, `RESUMING`, `RECOVERY_REQUIRED`, `ERROR`), progres perintah, checkpoint, dan daftar `RecoveryItem`. |
| `POST` | `/api/power/off` | Menjeda seluruh penjadwalan tugas baru, menyimpan checkpoint tugas aktif, dan menghentikan worker secara terkontrol (idempoten). |
| `POST` | `/api/power/on` | Memvalidasi integritas sistem & checkpoint, memulihkan tugas yang terputus secara aman, dan mengaktifkan kembali scheduler (idempoten). |
| `POST` | `/api/power/recovery/{id}/resolve` | Menyelesaikan item pemulihan manual oleh CEO (`requeue`, `cancel`, `confirm_occurred`, `confirm_not_occurred`, `acknowledge`). |

---

### 2.7 AI Control Center, Budget & Backup (`/api/ai/*`, `/api/models/*`, `/api/backups/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` / `PATCH` | `/api/providers` | Membaca status kesehatan provider AI (Google Gemini API) atau memperbarui konfigurasi runtime dan kunci API secara aman. |
| `GET` | `/api/models` | Menampilkan daftar model yang terdaftar di *Model Capability Registry* (`gemini-2.5-flash`, `gemini-2.5-pro`) beserta batas konteks dan estimasi biaya. |
| `GET` / `PATCH` | `/api/budgets` | Membaca atau mengubah kebijakan anggaran bulanan (`monthly_limit`, `allow_paid_calls`, `max_tokens_cap`). |
| `GET` | `/api/usage` | Menampilkan riwayat pemakaian model AI (`model_usage`: token masuk/keluar, durasi, biaya tercatat, tanpa isi prompt). |
| `GET` / `PATCH` | `/api/web/settings` | Membaca atau mengatur saklar akses web agen (`web_access_enabled`), provider pencarian (`tavily` / `brave`), dan batas harian (`web_daily_limit`). |
| `GET` / `POST` | `/api/backups` | Menampilkan daftar snapshot cadangan di `data/backups/` atau memicu pembuatan snapshot baru (`database.jsonl.gz` + `manifest.json`). |
| `POST` | `/api/backups/{name}/verify` | Memverifikasi keutuhan checksum SHA-256 dan jumlah baris seluruh tabel pada snapshot cadangan. |

---

## 3. Kontrak Envelope Event WebSocket (`/api/ws`)

Setiap pesan yang dikirim melalui WebSocket mengikuti struktur JSON terstandar berikut:

```json
{
  "event_id": "01JAWG9X8Z...",
  "type": "task.started",
  "entity_type": "task",
  "entity_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "project_id": "eb9b0943-0bb9-43de-8cec-54ff2de468d2",
  "occurred_at": "2026-10-27T08:15:30Z",
  "sequence": 1042,
  "payload": {
    "role": "seo_specialist",
    "attempt": 1,
    "status": "running"
  }
}
```

### Daftar Tipe Event (`type`):
- **Task Lifecycle:** `task.created`, `task.queued`, `task.started`, `task.progress`, `task.blocked`, `task.completed`, `task.failed`, `task.cancelled`, `task.interrupted`
- **Approval Lifecycle:** `approval.required`, `approval.resolved`
- **Power Control:** `power.state_changed`, `power.progress`, `power.recovery_item`, `power.recovery_item_resolved`
- **AI & Marketing:** `provider.health_changed`, `usage.updated`, `marketing.lead_updated`, `campaign.status_changed`
