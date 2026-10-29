# 5. API SPECIFICATION & WEBSOCKET CONTRACTS

**Nama Produk:** Roihan AI Office  
**Base URL Produksi (Backend):** `https://roihan-ai-office-api.onrender.com`  
**Base URL Lokal (Backend):** `http://127.0.0.1:8000`  
**Proxy Frontend (Next.js):** `/api/*` (Meneruskan request secara aman dari sisi server Next.js ke FastAPI Backend)  
**Format Pertukaran Data:** JSON (`application/json`, UTF-8)  

---

## 1. Standar Autentikasi, Keamanan & Error

### 1.1 Mekanisme Autentikasi
Seluruh endpoint `/api/*` **(kecuali `GET /api/health`, `GET /api/health/details` dan endpoint status publik `/api/auth/status`, `/api/auth/bootstrap`, `/api/auth/login`)** wajib terautentikasi melalui salah satu mekanisme berikut:
1. **Single-Owner Session Cookie (`HttpOnly`):** Cookie sesi `roihan_session` yang diterbitkan saat login/bootstrap pemilik. Token disimpan di database dalam bentuk digest SHA-256 (`session_token` di tabel `owner_sessions`), sehingga pencurian database tidak membocorkan token sesi mentah. Endpoint `/api/auth/login` dan `/api/auth/bootstrap` tidak mengembalikan token mentah di body respons JSON.
2. **Bearer Token (`Authorization: Bearer <APP_LOCAL_TOKEN>`):** Digunakan secara ketat untuk worker internal atau CLI administratif server-side, diverifikasi dengan perbandingan waktu-konstan (`secrets.compare_digest`). Token ini **tidak pernah** diinjeksi ke browser publik.

### 1.2 Kode Status HTTP Standar
| Kode HTTP | Arti | Contoh Kondisi |
| :--- | :--- | :--- |
| `200 OK` / `201 Created` | Permintaan berhasil diproses | Data berhasil dibaca, dibuat, atau diperbarui. |
| `400 Bad Request` / `422 Unprocessable Entity` | Input tidak valid atau melanggar aturan skema/kebijakan | Format URL salah, field wajib kosong, atau melanggar aturan PII/UU PDP. |
| `401 Unauthorized` | Belum terautentikasi | Sesi kedaluwarsa, cookie tidak ada, atau Bearer token salah. |
| `403 Forbidden` | Tindakan dilarang secara permanen oleh aturan sistem | Mencoba memanggil `/api/auth/bootstrap` setelah akun pemilik sudah terdaftar, atau agen mencoba menyetujui approval. |
| `404 Not Found` | Entitas tidak ditemukan | ID task, kampanye, prospek, atau produk tidak ditemukan. |
| `409 Conflict` | Konflik state atau gerbang kebijakan belum terpenuhi | Transisi status task tidak sah, *Product Release Gate* belum lulus, atau task aktif sudah berjalan di kampanye SEO yang sama. |
| `429 Too Many Requests` | Batas frekuensi terlampaui | Akun terkunci 15 menit setelah 5x berturut-turut gagal login. |

---

## 2. Spesifikasi Endpoint Berdasarkan Modul

### 2.1 Kesehatan Sistem & Autentikasi Single-Owner (`/api/health*` & `/api/auth/*`)

| Method | Endpoint | Deskripsi | Auth Wajib |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Memeriksa status kesehatan aplikasi, konektivitas database PostgreSQL, dan status konfigurasi AI provider (tanpa membocorkan data sensitif). | Tidak |
| `GET` | `/api/health/details` | Pemeriksaan kesehatan mendalam untuk diagnostik operasional. | Tidak |
| `GET` | `/api/auth/status` | Memeriksa apakah akun pemilik sudah di-bootstrap (`initialized: true/false`) dan status autentikasi sesi (`authenticated: true/false`). | Tidak |
| `POST` | `/api/auth/bootstrap` | **Sekali Pakai:** Membuat akun pemilik tunggal pertama kali. Membutuhkan `full_name`, `email` (wajib cocok dengan `OWNER_EMAIL`), `password` (min. 8 karakter), dan `bootstrap_token`. Menerbitkan cookie `HttpOnly` dan terkunci permanen (`403 Forbidden`) setelahnya. | Tidak (Wajib `BOOTSTRAP_TOKEN`) |
| `POST` | `/api/auth/login` | Login pemilik tunggal dengan `email` dan `password`. Mengatur cookie sesi `HttpOnly` aman. Mengembalikan `429` jika gagal 5x berturut-turut (terkunci 15 menit). | Tidak |
| `POST` | `/api/auth/logout` | Mencabut (*revoke*) sesi aktif di tabel `owner_sessions` dan menghapus cookie sesi browser. | Ya |
| `GET` | `/api/auth/me` | Mengambil profil akun pemilik yang sedang login beserta status sesi. | Ya |
| `POST` | `/api/auth/change-password` | Mengubah kata sandi pemilik akun, memverifikasi kata sandi lama, dan otomatis mencabut seluruh sesi aktif lainnya. | Ya |

---

### 2.2 Dashboard Command Center & Real-Time Events (`/api/dashboard/*` & `/api/events/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/dashboard` | Mengambil potret konsisten seluruh sistem: status agen marketing, hitungan task per status, daftar keputusan yang menunggu CEO (approval, draf siap tinjau, outbox, retensi, recovery item), ringkasan KPI marketing, penggunaan AI 24 jam, dan status daya kantor (`power`). |
| `GET` | `/api/dashboard/insights` | Mengambil data analitik teragregasi untuk grafik Command Center (distribusi status task, tingkat keberhasilan 7 hari, corong konversi prospek, pemakaian AI per jam). |
| `GET` | `/api/events?since={seq}` | Mengambil daftar event berurutan sejak nomor `seq` tertentu untuk sinkronisasi *catch-up* setelah koneksi terputus. |
| `POST` | `/api/events/ticket` | Menerbitkan tiket sekali pakai (masa berlaku 30 detik) agar browser dapat membuka koneksi WebSocket tanpa mengekspos token utama. |
| `WS` | `/api/ws?ticket={ticket}` | Kanal WebSocket real-time terenkripsi (memvalidasi tiket sekali pakai dan header `Origin`). |

---

### 2.3 Website Growth & Autonomous SEO (`/api/marketing/seo/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/marketing/seo/campaigns` | Menampilkan daftar seluruh kampanye SEO atau membuat kampanye baru (terkunci domain target, default `READ_ONLY`). |
| `GET` / `PATCH` | `/api/marketing/seo/campaigns/{id}` | Mengambil detail kampanye SEO atau memperbarui konfigurasi kampanye (anggaran API, batas eksternal, transisi status). |
| `GET` | `/api/marketing/seo/campaigns/{id}/report` | Mengambil laporan audit & kinerja komprehensif kampanye SEO dalam format JSON terstruktur. |
| `POST` | `/api/marketing/seo/campaigns/{id}/tasks/audit` | Menjadwalkan tugas audit SEO teknis untuk domain kampanye (mencegah duplikasi task aktif). |
| `POST` | `/api/marketing/seo/campaigns/{id}/tasks/keywords` | Menjadwalkan tugas riset kata kunci dan ide konten berbasis bukti sitasi sumber. |
| `POST` | `/api/marketing/seo/campaigns/{id}/keywords` | Menambahkan kata kunci manual ke dalam kampanye SEO. |
| `POST` | `/api/marketing/seo/campaigns/{id}/keywords/decision` | Menyetujui atau menolak daftar kata kunci usulan agen SEO. |
| `POST` | `/api/marketing/seo/campaigns/{id}/recommendations/{rec_id}/decision` | Menyetujui atau menolak rekomendasi perbaikan teknis hasil audit. |
| `GET` | `/api/marketing/seo/artifacts` | Menampilkan seluruh artefak riset SEO dan laporan analitik (`marketing_artifacts`). |
| `GET` | `/api/marketing/seo/artifacts/{id}` | Mengambil data lengkap artefak SEO tertentu. |
| `POST` | `/api/marketing/seo/artifacts/{id}/handoff` | Menyerahterimakan artefak riset SEO ke agen Content/Product. |
| `GET` | `/api/marketing/seo/sites` | Menampilkan daftar website yang terdaftar untuk dikelola dan dipantau. |
| `GET` | `/api/marketing/seo/sites/{id}` | Mengambil profil dan metadata situs terdaftar. |
| `POST` | `/api/marketing/seo/audit` | Menjalankan audit deterministik terhadap HTML, `robots.txt`, dan `sitemap.xml`. |
| `POST` | `/api/marketing/seo/metrics` | Mencatat riwayat KPI performa pencarian organik (`seo_metrics`). |

---

### 2.4 Leads, CRM, Pencarian Web & Kepatuhan UU PDP (`/api/marketing/*` & `/api/web/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/marketing/leads` | Membaca daftar prospek B2B (dengan PII disamarkan) atau mendaftarkan prospek baru dengan verifikasi *provenance* dan *suppression list*. |
| `GET` | `/api/marketing/leads/{id}` | Mengambil detail prospek. Jika query parameter `?reveal=true` disertakan oleh CEO, kontak asli dibuka dan event `lead.pii_viewed` dicatat di `audit_logs`. |
| `PATCH` / `DELETE`| `/api/marketing/leads/{id}` | Memperbarui atribut prospek atau menghapus prospek. |
| `POST` | `/api/marketing/leads/{id}/interactions` | Mencatat interaksi riil prospek (`note`, `email_out`, `email_in`, `call`, `meeting`). |
| `POST` | `/api/marketing/leads/{id}/status` | Mengubah status/stage prospek sesuai bukti interaksi yang valid. |
| `POST` | `/api/marketing/leads/{id}/forward` | Meneruskan prospek yang telah memenuhi kualifikasi (*qualified*) ke Sales Pipeline. |
| `POST` | `/api/marketing/leads/{id}/opt-out` | Menambahkan hash email/domain prospek ke `suppression_entries` dan membatalkan pesan antrean. |
| `POST` | `/api/marketing/leads/{id}/rescore` | Menghitung ulang skor kecocokan prospek deterministik secara on-demand. |
| `POST` | `/api/marketing/leads/{id}/convert` | Mengonversi prospek menjadi peluang penjualan (`sales_opportunities`). |
| `POST` | `/api/marketing/leads/{id}/erase` | Menghapus dan menganonimkan data prospek secara permanen atas permintaan pemilik data (hak penghapusan UU PDP). |
| `POST` | `/api/marketing/tasks/intake` | Menugaskan agen *Lead Intake* mengekstrak calon prospek dari teks sumber publik. |
| `GET` | `/api/marketing/opportunities` | Menampilkan seluruh peluang penjualan di Sales Pipeline. |
| `POST` | `/api/marketing/opportunities/{id}/stage` | Memperbarui tahap peluang penjualan (`qualification`, `proposal`, `negotiation`, `won`, `lost`). |
| `POST` | `/api/marketing/opportunities/{id}/requirements` | Menambahkan catatan kebutuhan klien pada peluang penjualan. |
| `POST` | `/api/marketing/opportunities/{id}/handoff` | Menyerahterimakan peluang yang dimenangkan (*won*) menjadi proyek internal. |
| `GET` | `/api/marketing/handoffs` | Menampilkan riwayat seluruh serah-terima peluang ke proyek. |
| `GET` | `/api/marketing/retention` | Memeriksa status retensi data prospek (jumlah prospek jatuh tempo). |
| `POST` | `/api/marketing/retention/run` | Menjalankan proses batch anonimisasi data prospek yang telah melampaui masa retensi UU PDP. |
| `GET` | `/api/marketing/research` | Membaca temuan riset pasar beserta bukti sitasinya. |
| `GET` | `/api/marketing/policy` | Membaca aturan dan kebijakan privasi pemasaran yang sedang aktif. |
| `POST` | `/api/web/search` | Mencari informasi di web publik via provider Tavily / Brave dengan SSRF Guard. |
| `POST` | `/api/web/fetch` | Mengambil konten halaman web publik dengan sanitasi keamanan. |
| `GET` | `/api/web/requests` | Menampilkan log audit seluruh panggilan web (`web_requests`). |
| `POST` | `/api/web/tasks/prospecting` | Menjadwalkan tugas pencarian prospek B2B dari web publik. |
| `POST` | `/api/web/tasks/research` | Menjadwalkan tugas riset pasar dan kompetitor dari web publik. |

---

### 2.5 Katalog Produk, Content Studio & Outbox (`/api/products/*` & `/api/marketing/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/products` | Membaca katalog produk atau mendaftarkan produk baru (`owned_product` / `service`). |
| `GET` / `PATCH` / `DELETE` | `/api/products/{id}` | Mengambil detail, memperbarui, atau menghapus produk dari katalog. |
| `POST` | `/api/products/{id}/approve-pricing` | Menyetujui harga resmi produk oleh CEO dan mengikat hash persetujuan. |
| `GET` | `/api/products/{id}/evidence-candidates` | Mengambil daftar tugas yang berpotensi menjadi bukti verifikasi klaim fitur. |
| `POST` | `/api/products/{id}/versions` | Menambahkan versi produk baru (`draft` s/d `released`). |
| `PATCH` | `/api/products/{id}/versions/{vid}` | Memperbarui status versi produk. |
| `POST` | `/api/products/{id}/versions/{vid}/features` | Mendaftarkan klaim fitur produk pada versi terkait. |
| `POST` | `/api/products/{id}/versions/{vid}/features/{fid}/attest` | Memberikan atestasi resmi CEO atas klaim fitur yang belum memiliki bukti automated task. |
| `POST` | `/api/products/{id}/versions/{vid}/features/{fid}/evidence` | Menautkan task ID sebagai bukti pengujian fitur. |
| `POST` | `/api/products/{id}/versions/{vid}/features/{fid}/reverify` | Menjalankan ulang verifikasi klaim fitur. |
| `POST` | `/api/products/{id}/versions/{vid}/features/{fid}/{state}` | Mengubah state klaim fitur (`verified`, `disputed`, `withdrawn`). |
| `POST` | `/api/products/{id}/versions/{vid}/check-claims` | Menjalankan validasi ketat teks pemasaran terhadap klaim fitur versi produk. |
| `GET` | `/api/products/{id}/versions/{vid}/marketing-brief` | Mengambil Marketing Brief resmi yang menjadi acuan tunggal konten pemasaran. |
| `POST` | `/api/products/{id}/versions/{vid}/marketing-permission` | Mengajukan atau mengubah izin pemasaran produk (`not_allowed`, `beta_only`, `allowed`). |
| `POST` | `/api/products/{id}/versions/{vid}/pin-commit` | Mengunci (*pin*) commit git spesifik sebagai acuan versi rilis. |
| `GET` | `/api/products/{id}/versions/{vid}/release-checks` | Membaca riwayat evaluasi 10 syarat gerbang rilis produk (*release gate*). |
| `GET` | `/api/products/{id}/versions/{vid}/release-gate` | Menguji kesiapan versi produk terhadap 10 kriteria rilis saat ini. |
| `GET` / `POST` | `/api/marketing/content` | Menampilkan daftar aset konten atau menugaskan pembuatan draf materi konten baru. |
| `GET` / `PATCH` | `/api/marketing/content/{id}` | Mengambil atau memperbarui draf materi konten pemasaran. |
| `POST` | `/api/marketing/content/{id}/request-publish` | Mengajukan draf konten yang telah lolos uji klaim ke Approval Center. |
| `GET` | `/api/marketing/outreach` | Menampilkan draf outreach B2B. |
| `POST` | `/api/marketing/outreach/{id}/request-send` | Mengajukan draf pesan outreach ke Approval Center untuk dikirim. |
| `POST` | `/api/marketing/outreach/{id}/mark-sent` | Mencatat bahwa pesan outreach telah dikirimkan secara manual. |
| `POST` | `/api/marketing/outreach/{id}/cancel` | Membatalkan draf outreach yang belum dikirim. |
| `GET` | `/api/marketing/outbox` | Menampilkan seluruh item di kotak keluar yang telah disetujui CEO (`queued_manual`). |
| `POST` | `/api/marketing/outbox/{id}/dispatch` | Menandai item outbox telah dikirimkan atau dipublikasikan secara manual oleh CEO. |
| `POST` | `/api/marketing/outbox/{id}/cancel` | Membatalkan item outbox yang belum dikirim. |
| `GET` / `POST` | `/api/marketing/campaigns` | Menampilkan daftar kampanye atau membuat kampanye pemasaran baru. |
| `GET` | `/api/marketing/campaigns/{id}` | Mengambil detail kampanye pemasaran beserta metrik kinerjanya. |
| `POST` | `/api/marketing/campaigns/{id}/metrics` | Mencatat metrik performa kampanye pemasaran baru. |
| `POST` | `/api/marketing/campaigns/{id}/status` | Mengubah status aktif/jeda/selesai kampanye pemasaran. |
| `GET` | `/api/marketing/analytics` | Mengambil laporan analitik komprehensif performa pemasaran. |

---

### 2.6 Project Workspace, Task Engine & Power Control (`/api/projects/*`, `/api/tasks/*`, `/api/approvals/*`, `/api/power/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` / `POST` | `/api/projects` | Menampilkan daftar proyek kerja atau membuat proyek baru. |
| `GET` / `PATCH` / `DELETE` | `/api/projects/{id}` | Mengambil detail, memperbarui informasi, atau menghapus proyek kerja. |
| `GET` / `POST` | `/api/projects/{id}/files` | Melihat daftar berkas atau mengunggah berkas baru ke direktori proyek. |
| `GET` / `DELETE` | `/api/projects/{id}/files/{fid}` | Mengunduh berkas (`/download`) atau menghapus berkas proyek. |
| `POST` | `/api/projects/{id}/plan` | Menugaskan Orchestrator memecah tujuan proyek menjadi daftar *draft tasks* & dependensi. |
| `POST` | `/api/projects/{id}/tasks/queue-drafts` | Mengantrekan seluruh *draft tasks* pada proyek secara massal. |
| `GET` | `/api/projects/{id}/report` | Mengambil laporan status dan kemajuan proyek lengkap. |
| `GET` | `/api/projects/{id}/workspace` | Melihat ringkasan struktur dan integritas berkas pada workspace proyek. |
| `GET` | `/api/projects/{id}/workspace/file` | Membaca isi berkas tertentu dari workspace proyek secara aman. |
| `GET` / `POST` | `/api/tasks` | Membaca daftar tugas (dengan filter status/proyek/role) atau membuat tugas manual baru. |
| `GET` | `/api/tasks/{id}` | Mengambil rincian tugas, riwayat percobaan, dependensi, dan hasil eksekusi. |
| `POST` | `/api/tasks/{id}/queue` | Mengantrekan tugas berstatus `draft` (otomatis meminta approval jika risiko `High`/`Critical`). |
| `POST` | `/api/tasks/{id}/cancel` | Membatalkan tugas yang sedang antre atau menghentikan eksekusi tugas secara aman. |
| `POST` | `/api/tasks/{id}/retry` | Mencoba ulang tugas yang gagal atau terblokir. |
| `GET` | `/api/tasks/{id}/report` | Mengambil laporan komprehensif 15-bagian atas pelaksanaan tugas. |
| `GET` | `/api/approvals` | Menampilkan daftar permintaan persetujuan tindakan berisiko tinggi. |
| `GET` | `/api/approvals/{id}` | Mengambil detail permintaan persetujuan beserta preview payload dan hash SHA-256. |
| `POST` | `/api/approvals/{id}/approve` | Menyetujui tindakan berisiko (hanya CEO sah; tugas otomatis dialihkan ke status `queued`). |
| `POST` | `/api/approvals/{id}/reject` | Menolak tindakan berisiko (membatalkan tugas dan mencatat alasan penolakan di audit log). |
| `GET` | `/api/power` | Membaca status daya kantor global (`RUNNING`, `PAUSING`, `PAUSED`, `RESUMING`, `RECOVERY_REQUIRED`, `ERROR`). |
| `POST` | `/api/power/off` | Menjeda antrean tugas baru, membuat checkpoint tugas aktif, dan mematikan worker secara terkontrol. |
| `POST` | `/api/power/on` | Memvalidasi checkpoint, melanjutkan tugas yang terputus, dan menyalakan kembali worker. |
| `GET` | `/api/power/commands` | Menampilkan riwayat perintah operasional daya (`power_commands`). |
| `GET` | `/api/power/commands/{id}` | Mengambil rincian eksekusi dan langkah-langkah perintah daya tertentu. |
| `GET` | `/api/power/checkpoints` | Menampilkan daftar seluruh checkpoint tugas tersimpan (`task_checkpoints`). |
| `GET` | `/api/power/tasks/{task_id}/checkpoints` | Mengambil riwayat checkpoint spesifik untuk satu tugas. |
| `GET` | `/api/power/recovery` | Menampilkan daftar item anomali yang membutuhkan intervensi manual CEO (`recovery_items`). |
| `GET` | `/api/power/recovery/log` | Membaca log audit proses pemulihan pasca insiden (**append-only**). |
| `POST` | `/api/power/recovery/{id}/resolve` | Menyelesaikan item pemulihan oleh CEO (`requeue`, `cancel`, `confirmed_done`, `confirmed_not_done`, `acknowledged`). |

---

### 2.7 AI Control Center, Runtime Settings & Engineering (`/api/ai/*`, `/api/providers/*`, `/api/backups/*`, `/api/engineering/*`)

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `POST` | `/api/ai/generate` | Menjalankan pemanggilan AI langsung terkelola melalui Model Gateway. |
| `POST` | `/api/ai/requests/{id}/cancel` | Membatalkan proses generasi model AI yang sedang berjalan. |
| `GET` | `/api/models` | Menampilkan daftar seluruh model terdaftar beserta batas token konteks dan status pricing. |
| `POST` | `/api/models/sync` | Mensinkronkan daftar kemampuan model dengan status penyedia AI aktif. |
| `GET` | `/api/providers` | Menampilkan status dan konfigurasi penyedia AI (Gemini, OpenAI, Anthropic, Ollama, Fake). |
| `PATCH` | `/api/providers/{name}` | Memperbarui kunci API dan status aktif penyedia secara runtime aman di `data/ai-provider-settings.json`. |
| `GET` | `/api/providers/{name}/health` | Menguji konektivitas langsung ke endpoint API penyedia terkait. |
| `GET` | `/api/budgets` | Membaca kebijakan batas anggaran pemakaian token bulanan dan kontrol panggilan berbayar. |
| `GET` | `/api/usage` | Menampilkan ledger pemakaian model AI (**append-only**, tanpa teks prompt asli). |
| `GET` / `PATCH` | `/api/web` | Membaca atau mengatur saklar akses web eksternal, search provider, dan kuota harian di `data/web-access.json`. |
| `GET` / `POST` | `/api/backups` | Menampilkan daftar berkas snapshot cadangan atau membuat cadangan baru (`.jsonl.gz` + `.json`). |
| `POST` | `/api/backups/{name}/verify` | Memverifikasi integritas checksum SHA-256 dan konsistensi baris snapshot cadangan. |
| `GET` | `/api/engineering/executions` | Menampilkan riwayat eksekusi command sandbox (`executions`). |
| `GET` | `/api/engineering/reviews` | Menampilkan riwayat code review deterministik (`code_reviews`). |
| `GET` | `/api/engineering/runs` | Menampilkan riwayat test suite execution (`test_runs`). |
| `GET` | `/api/engineering/runs/{id}` | Mengambil ringkasan hasil uji test suite tertentu. |
| `GET` | `/api/engineering/runs/{id}/results` | Mengambil detail kasus uji individu pada test run (`test_results`). |
| `GET` | `/api/sandbox` | Memeriksa status dan kapabilitas runtime sandbox lokal. |
| `POST` | `/api/sandbox/selftest` | Menjalankan uji mandiri eksekusi sandbox terisolasi. |
| `GET` | `/api/worker` | Menampilkan status operasional loop worker eksekusi tugas. |
| `GET` | `/api/agents` | Menampilkan katalog peran agen AI spesialis yang terdaftar di sistem. |

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
