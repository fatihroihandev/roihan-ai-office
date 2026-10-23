# Evaluasi Cloud, PostgreSQL, Provider Berbayar, dan Integrasi (Phase 12)

Tanggal: 2026-10-22. Status: **evaluasi selesai, tidak ada migrasi dilakukan.**

## Rekomendasi

**Tetap lokal (SQLite + Ollama).** Tidak ada bukti kebutuhan yang mendesak untuk pindah. Migrasi hanya dijalankan bila salah satu **pemicu** di bawah terpenuhi
**dan** CEO menyetujui **dan** rencana pemulihan (bagian "Rencana migrasi") siap. Hasil uji menunjukkan jalur ke PostgreSQL sudah terbuka (kode portabel),
sehingga menunda keputusan tidak menutup pilihan.

## Pemicu (migrasi hanya jika salah satu benar, terukur)

| Pemicu | Ambang | Cara mengukur |
|---|---|---|
| Lebih dari satu orang atau perangkat mengakses | >= 2 pengguna aktif harian | kebutuhan bisnis; butuh login pengguna (belum ada, lihat `docs/SECURITY.md`) |
| Konkurensi tulis tinggi | penulis bersamaan rutin > 8, atau p99 tulis SQLite > 500 ms | `scripts/evaluate_db.py` dan log permintaan |
| Data besar | database > 5 GB atau kueri dashboard p95 > 1 detik | ukuran `data/database/`, `evaluate_db.py` |
| Kapasitas model lokal tidak cukup | antrean task rata-rata menunggu > 30 menit karena model lokal, atau kualitas keluaran lokal gagal acceptance berulang | statistik task + Dasbor |
| Ketersediaan | CEO butuh sistem hidup saat laptop mati | keputusan bisnis |
| Kebutuhan integrasi dua arah | webhook masuk dari layanan luar | kebutuhan bisnis |

Saat ini: 0,4 MB data, 1 proyek, 1 pengguna, worker 1 task bersamaan. **Tidak ada pemicu terpenuhi.**

## 1. Kebutuhan cloud

Cloud memberi: ketersediaan 24/7, akses jauh, model yang lebih kuat, cadangan di luar perangkat. Cloud menambah: biaya tetap, permukaan serangan,
kewajiban autentikasi pengguna, kepatuhan data prospek (UU PDP) untuk data yang berpindah penyedia. Karena aplikasi dirancang "modular monolith" dan
hybrid-ready, pilihan bertahap yang paling murah adalah:

1. **Tahap A (sekarang):** lokal penuh, tambah salinan `data/backups/` ke disk lain/penyimpanan objek (hanya cadangan, tanpa menjalankan aplikasi di cloud).
2. **Tahap B (jika pemicu ketersediaan/akses):** backend + frontend di satu VPS, SQLite tetap, login pengguna ditambahkan, model tetap lokal lewat tunnel atau provider berbayar.
3. **Tahap C (jika pemicu konkurensi/data):** PostgreSQL, lalu pemisahan worker.

## 2. PostgreSQL — hasil uji nyata

Dijalankan PostgreSQL 17 (Docker, sementara) dengan migrasi dan seluruh suite tes proyek:

- **Migrasi Alembic**: `upgrade head` berhasil tanpa perubahan kode (34 tabel, revisi 0009).
- **Suite tes pada PostgreSQL**: **795 lulus**, 1 dilewati, **20 tidak berlaku**: seluruhnya sengaja khusus SQLite — modul cadangan berbasis berkas
  (`test_backup.py`, 2 tes di `test_recovery.py`) dan `test_sqlite_pragmas`. Tidak ada kegagalan logika aplikasi (antrean, approval, marketing, dashboard, dsb).
  Fixture `tests/conftest.py` kini mendukung `TEST_POSTGRES_URL` (database per tes dikloning dari templat) agar uji ini dapat diulang.
- **Yang perlu diganti saat evaluasi awal**: (1) cadangan/pemulihan PostgreSQL, (2) tes pragma,
  (3) `sqlite_autoincrement` pada `task_events` (diabaikan PostgreSQL; `seq` tetap monoton lewat identity), (4) pengelolaan kata sandi/URL koneksi di `.env`,
  (5) ukuran pool koneksi (bawaan 15; lihat catatan benchmark), (6) bila worker dijadikan banyak proses: klaim task dengan `SELECT ... FOR UPDATE SKIP LOCKED`
  (sekarang worker satu proses dalam satu pemroses).

### Benchmark (`scripts/evaluate_db.py`; 1 penulis = jalur nyata aplikasi; mesin pengembangan, PostgreSQL di Docker lokal)

| Skenario | SQLite WAL | PostgreSQL 17 |
|---|---|---|
| 1 penulis: tulis/dtk — p95 | 666 — 2,1 ms | 202 — 5,9 ms |
| 4 penulis: tulis/dtk — p99 | 647 — 80 ms | 725 — 8,4 ms |
| 8 penulis: tulis/dtk — p99 | 645 — 146 ms | 967 — 13,6 ms |
| Kegagalan "database terkunci" | 0 | 0 |
| Kueri dashboard pada 200.000 baris event (p95) | 100 ms | 111 ms |

Pembacaan jujur: untuk beban aplikasi ini (satu worker + beberapa permintaan UI) SQLite **lebih cepat** daripada PostgreSQL lokal karena tanpa jaringan.
SQLite baru menunjukkan ekor latensi (p99 ratusan ms) mulai 4–8 penulis bersamaan, sedangkan PostgreSQL stabil dan naik throughput-nya. Tidak ada galat
terkunci pada `busy_timeout` 5 detik. Percobaan awal dengan 16 penulis menghasilkan latensi baca ~6 detik di **kedua** database; penyebabnya antrean pool koneksi
(15), bukan basis data, sehingga skenario dibatasi 8. Angka dari satu mesin dan satu jalan; PostgreSQL terkelola jarak jauh akan menambah latensi jaringan per transaksi.

## 3. Provider berbayar (evaluasi)

Arsitektur sudah siap: provider terdaftar, tetapi tanpa adapter dan terkunci oleh anggaran dan approval CEO (Phase 3/6). Rekomendasi bila dibutuhkan:

- Pakai **hanya untuk kelas tugas yang gagal acceptance di model lokal** (mis. penalaran panjang, kode kompleks), bukan sebagai bawaan; router sudah memilih lokal dulu.
- Task latar belakang memakai **Batch API** (diskon 50% pada asumsi di bawah) dan cache prompt untuk konteks berulang.
- Wajib: batas bulanan di `BUDGET_MONTHLY_LIMIT`, `BUDGET_ALLOW_PAID_CALLS=true` hanya setelah keputusan CEO, kunci API di `.env` (tidak pernah di git/bundel).
- Data prospek/klien tidak dikirim ke penyedia tanpa tinjauan kepatuhan (minimasi data, anonimisasi).

### Estimasi biaya (`scripts/estimate_cloud_cost.py`)

**Harga adalah asumsi, harus diverifikasi** di halaman harga penyedia (sumber sekunder Mei 2026 saling bertentangan untuk model terbaru). Pada asumsi
Haiku-class $1/$5, Sonnet-class $3/$15, Opus-class $5/$25 per juta token masuk/keluar, kurs Rp16.500:

| Skenario (task/hari) | Haiku-class | Sonnet-class | Opus-class |
|---|---|---|---|
| Ringan (20) | $7 (~Rp0,1 jt) | $21 (~Rp0,3 jt) | $34 (~Rp0,6 jt) |
| Sedang (100) | $48 (~Rp0,8 jt) | $144 (~Rp2,4 jt) | $240 (~Rp4,0 jt) |
| Berat (400) | $246 (~Rp4,1 jt) | $738 (~Rp12,2 jt) | $1.230 (~Rp20,3 jt) |

Infrastruktur kasar: cloud sederhana (VPS + cadangan + domain) ~$24/bln (~Rp0,4 jt); dengan PostgreSQL terkelola ~$54/bln (~Rp0,9 jt).
Model lokal: ~6,6 token/detik → kapasitas keluaran maks ~570 ribu token/hari; skenario "ringan" memakai ~5% waktu, "sedang" ~35%, "berat" **melebihi** kapasitas lokal
(pemicu kapasitas). Biaya riil bergantung volume nyata, yang saat ini hampir nol (belum ada task di basis data).

## 4. Integrasi eksternal (evaluasi)

Prinsip tetap: **tidak ada pengiriman otomatis**; semua tindakan keluar lewat outbox dan approval CEO terikat hash isi. Konektor hanya mengganti "CEO mengirim manual" menjadi
"sistem mengirim setelah approval", tidak menghapus persetujuan.

| Integrasi | Nilai | Risiko | Rekomendasi |
|---|---|---|---|
| Email keluar (SMTP/API) | Menghemat salin-tempel dari outbox | Spam, reputasi domain, opt-out | Tahap awal: **tetap manual**. Jika dibangun: kirim hanya pesan berstatus approved, batas harian, daftar jangan-hubungi dicek ulang saat kirim, header unsubscribe |
| Publikasi konten (blog/LinkedIn) | Hemat waktu | Ketentuan platform terhadap otomasi, klaim produk | Manual dulu; konektor per kanal diuji satu per satu |
| CRM/spreadsheet (ekspor) | Pelaporan | Kebocoran data prospek | Ekspor satu arah berkas, tanpa kredensial CRM |
| Kalender/rapat | Jadwal klien | Cakupan izin OAuth | Tunda |
| Webhook masuk (form situs) | Prospek dengan persetujuan jelas | Butuh endpoint publik + autentikasi | Hanya setelah Tahap B |
| Pembayaran | Di luar lingkup MVP | Kepatuhan, uang | Tidak dievaluasi |

Setiap konektor wajib: uji dengan layanan palsu, penanganan galat dan retry terbatas, pencatatan, dan tidak mengendurkan pemeriksaan klaim/suppression yang ada.

## Rencana migrasi (bila pemicu terpenuhi dan CEO menyetujui)

**Prasyarat:** persetujuan tertulis CEO; cadangan baru terverifikasi (`python -m app.backup create` + `verify`) **dan salinan di luar perangkat**; login pengguna sudah ada
(Phase 12 tidak membangunnya); jendela perawatan; anggaran bulanan disetujui.

1. **Persiapan (tanpa dampak):** sediakan PostgreSQL (versi 17), buat peran khusus dengan hak minimum, TLS wajib; `TEST_POSTGRES_URL=... pytest` harus hijau (kecuali tes khusus SQLite).
2. **Ganti yang khusus SQLite:** modul cadangan untuk PostgreSQL (`pg_dump` terjadwal + verifikasi restore ke database uji), tes pragma bersyarat, ukuran pool.
3. **Latihan migrasi di salinan:** ekspor data SQLite → impor ke PostgreSQL (skrip berurutan menurut kunci asing; `seq` task_events diteruskan dan identity di-set ke max+1),
   bandingkan jumlah baris per tabel dan hash isi kolom penting; jalankan game day (`scripts/gameday_restart.py` versi PostgreSQL).
4. **Hari-H:** hentikan backend → cadangan terakhir → impor → verifikasi hitungan → jalankan backend dengan `DATABASE_URL` baru → pantau 24 jam.
5. **Rencana pemulihan (rollback):** `DATABASE_URL` dikembalikan ke SQLite dan cadangan pra-migrasi dipulihkan (`app.backup restore`); simpan SQLite lama minimal 30 hari. Data yang ditulis di PostgreSQL
   setelah migrasi tidak ikut kembali — karena itu rollback hanya dalam 24 jam pertama dan jendela tulis dibatasi.
6. **Kriteria sukses:** seluruh tes hijau pada PostgreSQL, p95 kueri dashboard < 1 detik, tidak ada galat kunci, restore uji berhasil dari cadangan PostgreSQL.

### Pembaruan 2026-10-22

Backup aplikasi kini mendukung PostgreSQL: snapshot konsisten JSONL gzip, verifikasi hash dan jumlah baris, serta pemulihan CLI dengan perlindungan `pre-restore`. Arsip folder proyek tetap opsional. Backup dan verifikasi nyata berhasil pada PostgreSQL lokal; restore belum diuji pada database terisolasi.

Estimasi usaha (kasar): persiapan + penggantian cadangan + latihan = beberapa hari kerja pengembang; tanpa login pengguna, migrasi basis data saja tidak cukup untuk cloud multi-pengguna.

## Keputusan yang dibutuhkan dari CEO

1. Apakah ada kebutuhan akses jauh/multi-pengguna/24-7 dalam 6 bulan ke depan? (Bila tidak: berhenti di Tahap A.)
2. Anggaran bulanan maksimum untuk provider berbayar (bawaan 0).
3. Kebijakan data prospek ke penyedia luar (boleh/tidak, dianonimkan atau tidak).
4. Apakah salinan cadangan keluar perangkat disetujui, dan ke mana (disk eksternal/penyimpanan objek).

## Cara mengulang evaluasi

```
# SQLite saja
cd apps/api && .venv/Scripts/python ../../scripts/evaluate_db.py
# + PostgreSQL (Docker): docker run -d --name pg -e POSTGRES_PASSWORD=x -e POSTGRES_DB=roihan -p 127.0.0.1:55432:5432 postgres:17-alpine
#   venv terpisah dengan "psycopg[binary]", lalu: python ../../scripts/evaluate_db.py --postgres postgresql+psycopg://postgres:x@127.0.0.1:55432/roihan
# Suite tes pada PostgreSQL
TEST_POSTGRES_URL=postgresql+psycopg://postgres:x@127.0.0.1:55432 python -m pytest
python scripts/estimate_cloud_cost.py
```
