# 10. OPERATIONS, POWER CONTROL, BACKUP & DISASTER RECOVERY

**Nama Produk:** Roihan AI Office  
**Fokus Dokumen:** Panduan Operasional Harian CEO, Kontrol Daya Kantor (OFF/ON), Penyelesaian Masalah Manual, serta Prosedur Backup & Disaster Recovery  

---

## 1. Aturan Operasional Harian (Tiga Prinsip Kendali CEO)

Dalam mengoperasikan **Roihan AI Office** sehari-hari, sistem menegakkan tiga aturan keselamatan operasional:
1. **Agen Hanya Mengusulkan, CEO yang Memutuskan:** Tugas berisiko tinggi (publikasi konten, pengiriman pesan outreach ke prospek, perubahan konfigurasi produksi, atau pengeluaran anggaran) selalu berhenti di status `pending_approval` dan menunggu keputusan Anda di menu **Operations -> Approvals** (`/?view=approvals`).
2. **Pengiriman Terkendali Lewat Kotak Keluar (Outbox):** Konten dan pesan outreach yang telah Anda setujui masuk ke **Kotak Keluar (`queued_manual`)**. Anda meninjau pratinjau akhir, menekan tombol kirim ke kanal tujuan (Email / WhatsApp / Platform Sosial), lalu menandai **"Sudah Saya Kirim / Publikasikan"** agar tercatat di audit log dan riwayat interaksi prospek.
3. **Kejujuran Data (Anti-Fabrikasi):** Angka yang belum memiliki sumber data nyata selalu ditampilkan sebagai *"Belum ada data"* (`null`), bukan dipalsukan menjadi angka `0` atau estimasi karangan AI.

---

## 2. Manajemen Kontrol Daya Kantor (Office Power Control: OFF / ON)

Fitur **Office Power Control** memungkinkan CEO menghentikan sementara seluruh aktivitas agen AI secara aman, menyimpan state pekerjaan ke database, dan melanjutkannya kembali kapan saja tanpa kehilangan progres atau menggandakan tindakan eksternal.

### 2.1 Status Operasional Global (`power_state`)
| Status Global | Arti Operasional |
| :--- | :--- |
| `RUNNING` | Sistem aktif menerima dan mengeksekusi antrean tugas sesuai kebijakan. |
| `PAUSING` | Perintah OFF sedang berjalan: scheduler dihentikan, tugas aktif sedang menyimpan checkpoint dan berhenti secara terkontrol. |
| `PAUSED` | Seluruh pekerjaan agen telah berhenti dengan aman dan integritas checkpoint SHA-256 telah terverifikasi. |
| `RESUMING` | Perintah ON sedang berjalan: sistem sedang memvalidasi database, dependensi, dan memulihkan tugas yang terputus. |
| `RECOVERY_REQUIRED` | Terdapat satu atau lebih item pekerjaan (`RecoveryItem`) yang membutuhkan keputusan manual CEO. |
| `ERROR` | Terjadi kendala sistem saat transisi daya; lihat rincian error dan ulangi perintah ON/OFF. |

### 2.2 Prosedur Menjeda Pekerjaan (OFF)
1. Buka panel kontrol daya atau panggil `POST /api/power/off` lalu konfirmasi.
2. Tunggu hingga status berpindah dari `PAUSING` menjadi **`PAUSED`** (jangan mematikan server sebelum status terkonfirmasi `PAUSED`).
3. Seluruh antrean, urutan dependensi, penggunaan token, dan perubahan berkas tersimpan utuh di database.

### 2.3 Prosedur Melanjutkan Pekerjaan (ON)
1. Tekan tombol **ON** (`POST /api/power/on`).
2. Sistem memvalidasi keutuhan checkpoint:
   - Tugas yang sudah `completed` **tidak pernah dijalankan ulang**.
   - Tugas aman/idempoten yang terputus otomatis dikembalikan ke antrean (`queued`).
   - Tugas berisiko tinggi atau operasi eksternal yang tidak pasti akan ditahan sebagai item **`Butuh Tindakan Manual` (`RecoveryItem`)**.

---

## 3. Penanganan Item "Butuh Tindakan Manual" (`RecoveryItem`)

Jika sistem mengalami interupsi mendadak (*crash*, *cold-start* di tengah tugas berisiko, atau kegagalan berulang), sistem tidak akan menebak-nebak, melainkan menampilkan daftar item pemulihan kepada CEO:

| Jenis Item (`item_type`) | Penyebab | Tindakan Resolusi yang Tersedia bagi CEO |
| :--- | :--- | :--- |
| `risky_task_interrupted` | Tugas berisiko tinggi/kritis terputus saat sedang berjalan; sistem menolak mengulangnya secara otomatis. | **Antre Ulang (`requeue`)** *(meminta approval baru)* atau **Batalkan (`cancel`)**. |
| `uncertain_external_op` | Sistem tidak dapat memastikan apakah tindakan keluar (outreach/publikasi) sempat terkirim sebelum proses terputus. | Periksa di kanal tujuan terlebih dahulu, lalu pilih **Sudah Terjadi (`confirmed_done`)** atau **Belum Terjadi (`confirmed_not_done`)**. |
| `missing_project_files` | Berkas kerja atau state Git pada salinan proyek tidak cocok dengan hash di checkpoint terakhir. | Periksa berkas proyek, lalu pilih **Antre Ulang (`requeue`)** atau **Batalkan (`cancel`)**. |
| `stop_unconfirmed` | Tugas aktif tidak memberikan konfirmasi berhenti dalam batas waktu tenggang saat perintah OFF dijalankan. | Pilih **Tandai Dilihat (`acknowledged`)**, **Antre Ulang (`requeue`)**, atau **Batalkan (`cancel`)**. |
| `invalid_checkpoint` | Checksum SHA-256 pada salinan checkpoint tidak cocok atau korup. | Pilih **Antre Ulang (`requeue`)** dari awal atau **Batalkan (`cancel`)**. |
| `retries_exhausted` | Tugas gagal melampaui batas percobaan otomatis (`max_retries = 2`). | Periksa pesan error (mis. kuota Gemini habis), lalu pilih **Antre Ulang (`requeue`)** atau **Batalkan (`cancel`)**. |

> [!NOTE]
> Resolusi item dikirimkan ke endpoint `POST /api/power/recovery/{id}/resolve`. Begitu seluruh item pemulihan diselesaikan oleh CEO, status global kantor otomatis kembali ke **`RUNNING`**.

---

## 4. Prosedur Backup & Disaster Recovery

Roihan AI Office menyediakan perlindungan cadangan data bertingkat:

### 4.1 Backup & Verifikasi Mandiri melalui CLI (`app.backup`)
Utilitas CLI backend mencadangkan seluruh **49 tabel database PostgreSQL** ke dalam berkas terkompresi `database.jsonl.gz` beserta `manifest.json` (berisi checksum SHA-256 dan jumlah baris per tabel) serta opsional `projects.tar.gz`.

```powershell
# Masuk ke lingkungan Python backend
$env:PYTHONPATH="apps/api"

# 1. Membuat snapshot cadangan baru di data/backups/<timestamp>-manual/
& apps\api\.venv\Scripts\python.exe -m app.backup create

# 2. Melihat daftar seluruh cadangan yang tersedia
& apps\api\.venv\Scripts\python.exe -m app.backup list

# 3. Memverifikasi integritas SHA-256 & kelengkapan tabel pada cadangan
& apps\api\.venv\Scripts\python.exe -m app.backup verify <NAMA_FOLDER_BACKUP>
```

### 4.2 Pemulihan Database (Restore) dari Snapshot CLI
Jika terjadi kerusakan data dan Anda ingin mengembalikan database ke snapshot tertentu:
1. Hentikan proses backend sementara (agar tidak ada transaksi tulis yang berjalan paralel).
2. Jalankan perintah restore dengan flag `--force`:
   ```powershell
   $env:PYTHONPATH="apps/api"
   & apps\api\.venv\Scripts\python.exe -m app.backup restore <NAMA_FOLDER_BACKUP> --force
   ```
   > **Catatan Keselamatan:** Jika database target telah berisi data, flag `--force` wajib disertakan. Sebelum menimpa data, CLI secara otomatis membuat cadangan penyelamatan bernama `...-pre-restore` yang tidak pernah dihapus oleh proses *pruning*, memverifikasi hash SHA-256 setiap berkas di `manifest.json`, membersihkan tabel, memasukkan ulang seluruh baris 49 tabel, menyetel ulang sequence identity PostgreSQL, dan mengekstrak berkas proyek.
3. Nyalakan kembali proses backend.

### 4.3 Point-in-Time Recovery di Cloud (Neon PostgreSQL)
Untuk deployment online di Neon Serverless PostgreSQL:
1. Buka dashboard [console.neon.tech](https://console.neon.tech) -> pilih project `roihan-ai-office-db`.
2. Masuk ke menu **Branches / Restore**.
3. Pilih titik waktu (*Point-in-Time Restore*) hingga menit mana pun dalam 7 hari terakhir untuk memulihkan database secara instan tanpa kehilangan transaksi terbaru.

> [!WARNING]
> Pada deployment Render Free, penyimpanan container bersifat *ephemeral*. Jika snapshot backup dibuat di dalam container (`data/backups/`), berkas tersebut akan hilang jika container mengalami restart. Segera unduh file snapshot via UI (`/api/backups`) atau andalkan Point-in-Time Restore pada Neon PostgreSQL untuk perlindungan bencana data cloud.

---

## 5. Panduan Pemecahan Masalah Operasional (Troubleshooting)

| Gejala / Masalah | Penyebab Umum | Solusi Operasional |
| :--- | :--- | :--- |
| **Loading awal memakan waktu ~30 detik (Mode Online)** | Layanan Render Free sedang bangun dari *idle spin-down* (15 menit tanpa trafik). | Tunggu hingga indikator sinkronisasi selesai; seluruh data tetap aman di Neon PostgreSQL. |
| **Gagal Login dengan `HTTP 429 Too Many Requests`** | Terjadi 5 kali kesalahan input kata sandi berturut-turut (proteksi *brute-force* aktif). | Tunggu selama **15 menit** hingga kunci sementara terbuka otomatis, lalu login kembali. |
| **Tugas (`Task`) tetap berstatus `queued` dan tidak berjalan** | Status daya kantor sedang `PAUSED`, atau `WORKER_ENABLED=false`, atau tugas hulu (*dependency*) belum selesai. | Pastikan status daya **ON (`RUNNING`)**, `WORKER_ENABLED=true`, dan periksa status dependensi tugas. |
| **Tugas AI gagal dengan error kuota / anggaran (`budget_exceeded`)** | Panggilan berbayar dikunci (`BUDGET_ALLOW_PAID_CALLS=false`) atau batas anggaran kampanye SEO / bulanan tercapai. | Periksa pengaturan di **Settings -> AI Control Center** (`/?view=ai`) atau sesuaikan anggaran kampanye SEO. |
| **Draf Konten / Outreach ditolak oleh sistem (`blocked_by_claim_check`)** | Teks menyebut fitur produk yang belum `verified`, menggunakan klaim mutlak (*"100%"*, *"terbaik"*), menyebut harga yang belum disetujui, atau lupa menyertakan label `beta`. | Revisi draf agar hanya menggunakan fakta dari `marketing_brief`, atau verifikasi/atestasi klaim fitur di halaman **Produk** (`/products`). |
| **Produk tidak dapat diberikan izin pemasaran (`HTTP 409`)** | Belum memenuhi seluruh 10 syarat **Product Release Gate**. | Buka detail produk (`/products/[id]`), lihat butir gerbang yang belum centang (mis. versi masih `draft` atau batasan produk belum diisi), dan lengkapi. |
| **Pencarian prospek dari web tidak dapat dijalankan** | Saklar `web_access_enabled` masih mati atau kunci API Tavily/Brave belum diisi. | Buka **Settings -> AI Control Center**, aktifkan **Izinkan agen memakai web**, masukkan API key Tavily/Brave, dan klik **Uji Pencarian**. |
