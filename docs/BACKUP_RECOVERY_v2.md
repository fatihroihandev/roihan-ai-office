# PROSEDUR BACKUP DAN PEMULIHAN (PHASE 0 - MASTER ADDENDUM v2.0)
**Produk:** Roihan AI Office  
**Dokumen Acuan:** MASTER ADDENDUM v2.0  
**Tanggal:** 2026-10-27  
**Status:** TERVERIFIKASI & AKTIF

---

## 1. Lokasi dan Data Backup

### 1.1 Arsip Repositori Kode
- **Lokasi Arsip:** `D:\workspace\roihan-ai-office-addendum-v2-backup.zip`
- **Total Berkas:** 363 file (kode sumber, konfigurasi, migrasi, modul)
- **Ukuran:** 4.821.026 bytes
- **Integritas:** 100% OK (`zipfile.testzip()` valid, tanpa korupsi)
- **Checksum SHA-256:** `4006637494ae04595e844d0fb3293f414424c5e9ed689f8566b98aa82c6533cc`

### 1.2 Git Checkpoint
- **Branch:** `main`
- **Tag Checkpoint:** `checkpoint-pre-addendum-v2`
- **Commit:** `d40b0ef` (`feat(checkpoint): preserve user working tree UI refinements prior to Addendum v2.0`)
- **Status Tree:** Clean

### 1.3 Snapshot Database PostgreSQL
- **Lokasi Cadangan:** `data/backups/20261027T135542-manual/`
- **Komponen:**
  - `database.jsonl.gz` (Snapshot seluruh 48 tabel database)
  - `manifest.json` (Metadata, checksum SHA-256, dan Alembic revision)
  - `projects.tar.gz` (Folder proyek)
  - `.env.backup` (Konfigurasi lingkungan)
- **Hasil Verifikasi CLI:**
  `python -m app.backup verify 20261027T135542-manual` -> **VALID**

---

## 2. Prosedur Pemulihan (Disaster Recovery)

Jika terjadi kendala kritis atau kegagalan yang tidak dapat dibatalkan secara normal:

### 2.1 Pemulihan Kode Repositori
1. Jika git history masih utuh:
   ```bash
   git reset --hard checkpoint-pre-addendum-v2
   ```
2. Jika repositori rusak:
   Ekstrak `D:\workspace\roihan-ai-office-addendum-v2-backup.zip` ke direktori baru atau timpa direktori kerja setelah membersihkan file yang korup.

### 2.2 Pemulihan Database PostgreSQL
Jalankan perintah pemulihan snapshot menggunakan CLI backend:
```bash
$env:PYTHONPATH="apps/api"
& apps\api\.venv\Scripts\python.exe -m app.backup restore 20261027T135542-manual --yes
```
Perintah ini akan membaca `manifest.json`, memverifikasi SHA-256 tiap komponen, memulihkan seluruh tabel database, dan merestorasi folder proyek.
