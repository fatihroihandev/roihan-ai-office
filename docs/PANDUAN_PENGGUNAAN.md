# Panduan Penggunaan Roihan Software House

Panduan ini untuk **Anda sebagai CEO**: cara menyalakan aplikasi, memakai tiap menu, dan menjalankan pekerjaan sehari-hari.
Bahasa antarmuka bawaan Indonesia; ganti ke Inggris lewat tombol **ID / EN** di menu melayang.

> Ingat tiga aturan dasar aplikasi ini:
> 1. **Agent hanya mengusulkan.** Hal berisiko (kirim pesan, publikasi, hapus data, biaya) selalu menunggu persetujuan Anda.
> 2. **Tidak ada pengiriman otomatis.** Pesan dan konten yang disetujui masuk **kotak keluar**; Anda yang mengirim sendiri.
> 3. **Data yang belum ada tampil "belum ada data" atau "?"**, bukan angka nol atau angka karangan.

---

## 1. Persiapan satu kali

### 1.1 Yang harus terpasang
- Python 3.10+ dan Node.js 20+, Git
- **Ollama** dengan model lokal: `ollama pull qwen2.5-coder:7b`
- (Opsional) WSL2 untuk **sandbox** agar Developer/QA dapat menjalankan kode — lihat bagian 9

### 1.2 Isi berkas `.env`
1. Salin `.env.example` menjadi `.env` di folder utama proyek.
2. Isi `APP_LOCAL_TOKEN` dengan teks acak minimal 16 karakter. Cara membuatnya:
   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. Biarkan pengaturan lain apa adanya. Yang penting diketahui:
   - API berbayar **mati** secara bawaan (`OPENAI_ENABLED=false`, dst.). Biarkan begitu kecuali Anda sengaja mengaktifkannya.
   - `WORKER_ENABLED=true` = agent boleh bekerja otomatis setelah task diantrekan.

> `.env` berisi rahasia. Jangan dibagikan dan jangan di-commit.

---

## 2. Menyalakan aplikasi

Buka **dua terminal**.

**Terminal 1 — Backend**
```
cd C:\xampp\htdocs\roihan-software-house\apps\api
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8000
```
(Perintah `venv` dibuat sekali di awal: `python -m venv .venv`.)

**Terminal 2 — Tampilan**
```
cd C:\xampp\htdocs\roihan-software-house\apps\web
npm install
npm run dev
```

Buka **http://localhost:3000** di peramban.

**Pastikan Ollama berjalan** (ikon Ollama di tray, atau `ollama serve`). Tanpa Ollama, agent tidak bisa berpikir.

### Setiap kali ada pembaruan kode
Jalankan lagi `pip install -r requirements.txt` dan `alembic upgrade head`, lalu restart backend dan frontend.

### Mematikan aplikasi
Tekan `Ctrl+C` di kedua terminal. Pekerjaan yang sedang berjalan akan ditandai terputus dan dipulihkan otomatis saat dinyalakan lagi.

---

## 3. Mengenal tampilan

Tidak ada bilah menu di atas agar layar penuh. Gunakan **tombol bulat berlogo R** yang melayang di tepi layar:

| Aksi | Hasil |
| --- | --- |
| Klik tombol, atau tekan **M** | Membuka menu: Beranda, Kantor, Proyek, Task, Produk, Marketing, Approval, AI Control Center |
| **Esc** atau klik di luar menu | Menutup menu |
| **Seret** tombol | Memindahkan ke tepi kiri/kanan (posisi diingat) |
| Tombol **ID / EN** di dalam menu | Ganti bahasa |

Di tiap halaman ada spanduk judul di atas; di bawahnya isi halaman. Tombol **← Kembali** ada di halaman turunan.

---

## 4. Alur kerja sehari-hari (versi singkat)

1. **Proyek** → buat proyek, unggah dokumen kebutuhan.
2. **Task** → tulis tujuan, biarkan Manager memecahnya menjadi task, lalu **antrekan**.
3. Agent bekerja (lihat di **Kantor** atau papan Task).
4. **Approval** → setujui/tolak hal berisiko.
5. Baca **laporan** di detail task/proyek.
6. **Produk** & **Marketing** → promosi hanya setelah produk lolos gerbang rilis.

Detail tiap langkah ada di bagian berikut.

---

## 5. Menu Proyek (`/projects`)

**Membuat proyek**
1. Isi **nama** (dan deskripsi bila perlu), klik buat.
2. Masuk ke detail proyek, **unggah berkas** dan pilih jenisnya:
   - `master` = dokumen acuan utama (spesifikasi/visi)
   - `requirement` = kebutuhan
   - `reference` = bahan rujukan
   - `asset` = aset (gambar dll.)
3. Berkas tersimpan aman di `data/projects/<id>/`. Berkas yang diunggah **tidak pernah dijalankan otomatis**.

**Di detail proyek** Anda juga bisa melihat isi workspace kode (hasil kerja Developer) dan laporan proyek.

---

## 6. Menu Task (`/tasks`) — pusat pekerjaan agent

### 6.1 Membuat rencana otomatis
1. Pilih proyek, tulis **tujuan** dalam bahasa biasa (contoh: *"Buat kalkulator sederhana dengan tes"*).
2. Klik **Rencana**. Agent **Manager** memecahnya menjadi beberapa task (status **draft**) lengkap dengan dependensi.
3. Periksa daftarnya. Ubah/batalkan yang tidak perlu.
4. Klik **Antrekan** (satu per satu atau **antrekan semua draft**).

### 6.2 Status task
| Status | Arti |
| --- | --- |
| draft | Belum diantrekan |
| queued | Menunggu giliran |
| running | Sedang dikerjakan |
| pending_approval | Menunggu persetujuan Anda |
| blocked | Terhambat (mis. dependensi gagal, sandbox belum siap) — alasannya tertulis |
| completed | Selesai dan terverifikasi |
| failed | Gagal (alasan tertulis); dicoba ulang otomatis bila memungkinkan |
| interrupted | Terputus (restart/OFF); akan dipulihkan |
| cancelled | Dibatalkan |

### 6.3 Yang bisa Anda lakukan pada sebuah task
- **Buka detail**: lihat percobaan, riwayat status, log eksekusi, hasil tes, keputusan pemilihan model, dan **laporan**.
- **Batalkan** (task berjalan dihentikan dengan aman).
- **Coba ulang** task gagal/terblokir. Task berisiko minta approval baru.

### 6.4 Para agent
| Agent | Tugas |
| --- | --- |
| Manager | Memecah tujuan jadi task |
| Analyst | Analisis kebutuhan |
| Developer | Menulis kode di workspace (butuh sandbox untuk menjalankannya) |
| QA/Tester | Menjalankan tes |
| Reviewer | Menilai hasil berdasarkan bukti (tes dijalankan ulang) |
| Reporter | Menyusun laporan proyek |
| Market Research, Lead Generation, Content & Promotion, Sales | Marketing (bagian 8) |
| SEO Specialist, Marketing Analytics | SEO & analitik (bagian 8.6) |

Model AI bisa lambat di laptop biasa (sekitar 6–7 token/detik). Task panjang butuh waktu; ini normal.

---

## 7. Menu Approval (`/approvals`) — keputusan Anda

Task berisiko tinggi/kritis (kirim pesan, publikasi, hapus data, instal paket, biaya) **berhenti** menunggu Anda.

1. Buka kartu approval: baca **isi persis** yang akan dilakukan.
2. Klik **Setujui** atau **Tolak** (alasan boleh diisi).
3. Aturan penting:
   - Persetujuan hanya untuk **satu kali** eksekusi.
   - **Kedaluwarsa otomatis** (bawaan 24 jam).
   - Jika isi task berubah setelah disetujui, persetujuan **batal** dan harus diajukan lagi.
   - Hanya Anda yang dapat menyetujui; agent tidak bisa.
4. Setiap keputusan tercatat di audit log.

Kartu approval juga muncul di panel **Ringkasan CEO** di halaman Kantor.

---

## 8. Menu Produk dan Marketing

### 8.1 Produk (`/products`) — gerbang rilis
Marketing **hanya boleh** mempromosikan produk yang lolos gerbang.

1. Buat produk (produk sendiri atau layanan).
2. Tambahkan **versi** dan status pengembangan (draft … released).
3. Tambahkan **klaim fitur** (apa yang Anda janjikan ke pelanggan). Klaim **terverifikasi** hanya bila ada bukti nyata (task implementasi selesai, tes lulus, tidak ditolak review). Tanpa bukti = ditandai **BELUM TERVERIFIKASI**.
   Anda boleh menyatakan klaim secara manual dengan alasan tertulis; ini dicatat dan dibedakan dari bukti sistem.
4. Beri **izin pemasaran**: `not_allowed` / `beta_only` / `allowed`. Hanya bisa jika gerbang lulus, dan **dicek ulang setiap dibaca**: jika bukti berubah, izin otomatis gugur.
5. Produk beta wajib disebut beta dalam materi; harga hanya yang sudah disetujui.

### 8.2 Marketing (`/marketing`)
Isinya: kebijakan data prospek, metrik, pipeline, peluang, draf outreach, intake prospek, dan riset pasar.

**Menambah prospek**
- Manual: isi formulir (perusahaan, kontak bisnis, sumber).
- Intake dari teks: tempel teks sumber publik; agent **hanya mengekstrak yang benar-benar tertulis**, yang tidak ada di teks dibuang.
- Hanya sumber yang diizinkan (situs publik, registri publik, rujukan, inbound, acara, input manual). Daftar beli, scraping, dan data bocor **ditolak**.
- Email pribadi/data sensitif ditolak. Kontak **disamarkan** secara bawaan; membukanya tercatat.

**Riset pasar**: tempel materi sumber → hasil menandai temuan **terverifikasi** (ada kutipan bukti) vs **asumsi**.

**Memindahkan prospek antar tahap** perlu interaksi nyata yang Anda catat (catatan, email, telepon, pertemuan).

**Prospek menolak (opt-out)**: klik opt-out → masuk daftar jangan-hubungi (disimpan sebagai hash), pesan keluar yang tertunda dibatalkan, dan tidak bisa didaftarkan lagi.

### 8.3 Draf outreach
Agent Sales menyusun draf dari **ringkasan resmi produk** dan wajib lolos pemeriksaan klaim. Anda tinjau draf; **tidak ada yang terkirim otomatis**.

### 8.4 Konten, kampanye, kotak keluar (`/marketing/content`)
1. **Buat draf konten** (media sosial, artikel, landing page, naskah demo, newsletter) untuk produk yang sudah diizinkan.
2. Konten lolos pemeriksaan klaim, atau ditolak dengan alasan.
3. **Ajukan publikasi/pengiriman** → muncul di **Approval** dengan isi persis. Setujui.
4. Hasil yang disetujui masuk **kotak keluar** (`queued_manual`).
5. **Anda kirim/publikasikan sendiri** di platform tujuan, lalu tekan **"Sudah saya kirim/publikasikan"** agar tercatat.
6. **Kampanye**: tanpa iklan berbayar (anggaran 0). Catat angka (impresi, klik, biaya, pendapatan) **secara manual**. ROI baru muncul bila biaya dan pendapatan sama-sama tercatat.

Tindakan gagal tanpa efek bila: isi berubah, izin produk dicabut, prospek menolak, atau batas harian/jeda antar pesan terlampaui.

### 8.5 Serah-terima klien ke Engineering
Pada peluang yang **menang**, klik **Serahkan ke Engineering**: otomatis dibuat proyek, dokumen kebutuhan, dan task draft. Task baru jalan setelah **Anda antrekan**.

### 8.6 SEO & Digital Marketing (`/marketing/seo`)
Buka dari halaman Marketing → tombol **SEO & Digital Marketing**.

| Fitur | Cara pakai | Catatan |
| --- | --- | --- |
| **Audit SEO teknis** | Isi URL, **tempel HTML halaman** (dari "View page source"), opsional robots.txt dan sitemap.xml → **Jalankan audit** | Tanpa internet. Mengecek title, deskripsi, h1, noindex, canonical, gambar tanpa alt, dll. Tautan rusak dan kecepatan **tidak** diperiksa |
| **Riset kata kunci** | Isi topik + **materi sumber** (catatan/data Anda) → **Riset kata kunci** | Volume/persaingan hanya muncul bila ada di materi Anda; selain itu "belum ada data" |
| **Brief konten** | Isi topik (materi opsional), pilih produk bila perlu → **Buat brief konten** | Ditolak bila menjanjikan peringkat atau memuat klaim produk belum terverifikasi |
| **Laporan analitik** | Klik **Buat laporan analitik** | Dihitung dari data yang tercatat |
| **Catat metrik** | Pilih metrik (impresi, klik, sesi organik, konversi, posisi), nilai, periode `YYYY-MM` → **Catat** | Salin angkanya dari Search Console/Analytics Anda |

Hasil muncul di daftar **Artefak** (klik **Buka**). Pada audit, pilih proyek lalu **Buat task draft** untuk menyerahkan perbaikan ke Engineering (Anda yang mengantrekan). SEO **tidak** menjamin peringkat.

---

## 9. Sandbox untuk menjalankan kode (opsional tapi disarankan)

Kode buatan AI **tidak pernah dijalankan di Windows Anda**. Tanpa sandbox, task Developer/QA berstatus `blocked (sandbox_disabled)`.

Menyiapkan (sekali saja):
```
wsl --install -d Ubuntu
powershell -ExecutionPolicy Bypass -File scripts\setup_sandbox_wsl.ps1
```
Lalu di `.env`: `SANDBOX_BACKEND=wsl` dan `SANDBOX_WSL_DISTRO=roihan-sandbox`, restart backend. Buka halaman **Task** untuk melihat status sandbox dan hasil uji isolasi (harus lulus).

---

## 10. Menu Kantor (`/office`)

Kantor 3D cyberpunk yang **mencerminkan keadaan nyata**: agent yang bekerja duduk di meja ruang kerjanya; yang menganggur di **Lounge**.

**Kontrol di atas layar**
| Tombol | Fungsi |
| --- | --- |
| Lencana status + **OFF/ON** | Jeda/lanjutkan seluruh pekerjaan agent (bagian 11) |
| **Masuk Kantor** | Mode jalan: Anda berjalan sebagai avatar CEO |
| Otomatis / 3D / 2D | Mode tampilan (2D otomatis bila 3D tak didukung) |
| **Efek visual** Tinggi/Rendah | Kurangi efek bila laptop berat (turun otomatis bila lambat) |
| **Panel CEO** | Ringkasan: proyek, task aktif, approval, masalah, prospek, kotak keluar, pemakaian AI |
| **Layar penuh** | Memperbesar kantor |

**Kontrol 3D**: seret = putar, gulir = zoom, klik avatar = lihat detail agent (status, task, antrean).

**Mode jalan**: `W A S D` berjalan, `Shift` berlari, `V` ganti sudut pandang, `E` berinteraksi (bicara dengan agent, buka halaman), `Esc` keluar.

Lencana **Tautan live** = tersambung real-time; bila putus, data dimuat berkala dan ditandai usang.

---

## 11. Jeda dan lanjutkan pekerjaan (OFF / ON)

Gunakan saat ingin menutup aplikasi, mengistirahatkan laptop, atau menghentikan agent sebentar.

### OFF
1. Klik **OFF** di halaman Kantor → konfirmasi **Ya, jeda**.
2. Status berubah **MENJEDA** (spanduk menampilkan langkah: scheduler dihentikan → task dihentikan → checkpoint disimpan → diverifikasi).
3. Setelah **DIJEDA**: semua keadaan tersimpan; antrean dan dependensi utuh; avatar beristirahat. **Jangan** anggap sudah jeda sebelum lencana berubah **DIJEDA**.

### ON
1. Klik **ON**. Status **MELANJUTKAN** → sistem memeriksa database, workspace, dan dependensi.
2. Task yang terputus dipulihkan dari checkpoint terakhir yang valid. Task yang sudah selesai **tidak** dijalankan ulang.
3. Status kembali **BERJALAN**.

### Status lain
| Lencana | Arti dan tindakan |
| --- | --- |
| **BUTUH PEMULIHAN** | Ada item di panel CEO bagian **Butuh tindakan manual** (bagian 12) |
| **ERROR** | Terjadi kegagalan; coba **ON** atau **OFF** lagi, lihat detail |

Menekan OFF/ON berulang aman (tidak menggandakan pekerjaan).

### Jika laptop/aplikasi mati mendadak
Tidak perlu berbuat apa-apa selain **menyalakan backend lagi**. Sistem mendeteksi matinya proses sebelumnya dan memulihkan pekerjaan otomatis. Perubahan file Anda yang belum di-commit **tidak pernah dihapus**.

> Laptop mati = pekerjaan berhenti. Pekerjaan lanjut setelah laptop dan aplikasi dinyalakan lagi.

---

## 12. Item "Butuh tindakan manual"

Muncul di panel CEO saat sistem **tidak mau menebak**. Pilih tindakan pada tiap item:

| Jenis | Artinya | Pilihan |
| --- | --- | --- |
| Task berisiko terputus | Task berisiko tidak diulang otomatis | **Antre ulang** (minta approval baru) / **Batalkan** |
| Operasi eksternal tidak pasti | Tidak diketahui apakah pengiriman/publikasi sempat terjadi | **Sudah terjadi** / **Belum terjadi** (cek dulu di tujuan!) |
| File proyek hilang | File atau riwayat Git tidak sesuai checkpoint | Periksa folder, lalu **Antre ulang** / **Batalkan** |
| Penghentian tak terkonfirmasi | Task tidak terbukti berhenti saat OFF | **Tandai dilihat** / **Antre ulang** / **Batalkan** |
| Checkpoint tidak valid | Salinan keadaan rusak | **Antre ulang** / **Batalkan** / **Tandai dilihat** |
| Retry habis | Jatah percobaan otomatis habis | **Antre ulang** / **Batalkan** |

Setelah semua item selesai, status kembali **BERJALAN** otomatis.

---

## 13. AI Control Center (`/ai`)

- **Provider**: Ollama (lokal, gratis) aktif. OpenAI/Gemini/Anthropic berbayar **mati** dan panggilan berbayar **selalu diblokir** kecuali Anda mengatur dan menyetujuinya.
- **Registri model**: klik **Sinkronkan model** setelah mengunduh model baru di Ollama.
- **Kebijakan biaya**: batas bulanan, total biaya tercatat, kewajiban approval.
- **Uji model lokal**: tulis prompt → **Jalankan** untuk mencoba.
- **Penggunaan model**: tabel pemanggilan (isi prompt tidak disimpan, hanya hash dan panjang).

---

## 14. Cadangan dan pemulihan data

**Otomatis**: setiap 24 jam dan saat backend mulai, tersimpan di `data/backups/` (14 terbaru). Pengaturan: `BACKUP_*` di `.env`.

**Manual** (dari folder `apps/api`):
```
.venv\Scripts\python -m app.backup create          # buat cadangan sekarang
.venv\Scripts\python -m app.backup list            # daftar cadangan
.venv\Scripts\python -m app.backup verify NAMA     # periksa keutuhan
```

**Memulihkan** (backend harus dimatikan dulu):
```
.venv\Scripts\python -m app.backup restore NAMA --force
```
Keadaan sebelum dipulihkan otomatis diselamatkan sebagai cadangan `...-pre-restore`. Nyalakan backend lagi setelahnya.

> **Salin folder `data/backups/` ke disk lain secara berkala.** Cadangan masih di disk yang sama dan tidak dienkripsi.

---

## 15. Keamanan — yang perlu Anda jaga

- Jaga kerahasiaan `.env` dan token. Aplikasi hanya melayani `127.0.0.1` (komputer ini saja); **jangan** membukanya ke jaringan/internet.
- Token tidak pernah dikirim ke peramban; hanya dipakai di sisi server Next.js.
- Pemeriksaan keamanan otomatis: `python scripts\audit_security.py --deps`. Ringkasan ancaman: `docs/SECURITY.md`.
- Jangan mengaktifkan API berbayar tanpa mengisi batas bulanan dan memahami biayanya.

---

## 16. Pemecahan masalah

| Gejala | Penyebab umum | Solusi |
| --- | --- | --- |
| Halaman menampilkan error/tak ada data | Backend mati | Nyalakan backend (bagian 2), cek `http://127.0.0.1:8000/api/health` |
| Task tak pernah jalan, tetap `queued` | Lencana **DIJEDA**, atau `WORKER_ENABLED=false` | Tekan **ON**; cek `.env` |
| Task `failed` dengan galat model/koneksi | Ollama tidak berjalan atau model belum diunduh | Jalankan Ollama, `ollama pull qwen2.5-coder:7b` |
| Task Developer/QA `blocked: sandbox_disabled` | Sandbox belum disiapkan | Ikuti bagian 9 |
| Task `failed: output_truncated` | Jawaban model terpotong (tugas terlalu panjang) | Pecah menjadi tugas lebih kecil |
| Task `pending_approval` tak bergerak | Menunggu Anda | Buka **Approval** |
| Approval hilang/kedaluwarsa | Lewat 24 jam atau isi berubah | Antrekan/ajukan ulang untuk approval baru |
| Konten/pesan ditolak pemeriksaan klaim | Menyinggung klaim belum terverifikasi, klaim mutlak ("terbaik", "100%"), atau tak menyebut beta | Revisi teks, atau verifikasi klaim di **Produk** |
| Produk tak bisa diberi izin pemasaran | Gerbang rilis belum lulus | Lihat alasan di halaman produk (klaim/versi/harga) |
| Kantor 3D lambat | Laptop tanpa GPU kuat | **Efek visual: Rendah**, atau mode **2D** |
| Layar 3D kosong | WebGL tidak tersedia | Pakai mode **2D** |
| Setelah update muncul galat database | Migrasi belum dijalankan | `alembic upgrade head`, restart backend |
| Port 8000/3000 dipakai | Aplikasi lain | Matikan yang lama atau ganti port (`--port`, `NEXT_PUBLIC_API_WS_URL`) |

---

## 17. Cara kerja singkat: contoh alur lengkap

**Contoh A — Membuat program kecil**
1. **Proyek** → buat "Kalkulator" → unggah dokumen kebutuhan sebagai `requirement`.
2. **Task** → tujuan: *"Buat modul kalkulator dengan fungsi tambah-kurang dan tes pytest"* → **Rencana** → **Antrekan semua**.
3. Pantau di **Kantor**; baca detail task dan **laporan** begitu selesai.
4. Reviewer menilai berdasarkan tes yang dijalankan ulang di sandbox. Hasil "approved" = bukti lengkap.

**Contoh B — Mempromosikan produk**
1. **Produk** → buat produk + versi + klaim; tunggu klaim terverifikasi; beri izin `beta_only`/`allowed`.
2. **Marketing → Konten** → buat draf; lolos pemeriksaan klaim.
3. Ajukan publikasi → **Approval** → setujui → **kotak keluar**.
4. Publikasikan sendiri di platform → tekan **Sudah saya publikasikan**.
5. Catat kinerja di **Kampanye**; lihat KPI di **SEO & Digital Marketing**.

**Contoh C — Mendapat klien**
1. **Marketing** → tambah prospek dari sumber publik → catat interaksi nyata → naikkan tahap.
2. Minta draf outreach → tinjau → approval → kirim **sendiri** dari email Anda → catat.
3. Peluang **menang** → **Serahkan ke Engineering** → antrekan task draft yang dibuat.

---

## 18. Daftar istilah singkat

| Istilah | Arti |
| --- | --- |
| Agent | Peran AI dengan tugas dan batas akses tertentu |
| Task | Satu unit pekerjaan terukur |
| Approval | Persetujuan manusia untuk tindakan berisiko |
| Sandbox | Ruang terisolasi untuk menjalankan kode AI |
| Checkpoint | Salinan keadaan kerja untuk melanjutkan setelah jeda/crash |
| Gerbang rilis | Pemeriksaan produk sebelum boleh dipromosikan |
| Kotak keluar | Daftar pesan/konten disetujui yang Anda kirim sendiri |
| Opt-out | Prospek menolak dihubungi; tidak bisa didaftarkan ulang |
| Worker | Proses yang mengerjakan antrean task di dalam backend |

---

## 19. Pustaka dokumen lain
- `README.md` — ringkasan teknis dan perintah per fase
- `docs/MASTER_DEVELOPMENT.md` — spesifikasi lengkap, status tiap fase, dan batasan yang diketahui
- `docs/SECURITY.md` — model ancaman dan hasil audit keamanan
- `docs/CLOUD_EVALUATION.md` — evaluasi cloud/PostgreSQL dan rencana migrasi (tidak dijalankan)
