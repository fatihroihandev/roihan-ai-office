# Keamanan — model ancaman dan hasil audit (Phase 11)

Aplikasi berjalan lokal untuk satu CEO. Ancaman utamanya bukan penyerang internet, melainkan: halaman web jahat di peramban yang sama, proses lokal lain,
kebocoran rahasia lewat git/log, serta agent AI yang bertindak di luar wewenangnya.

## Kontrol yang ada

| Ancaman | Kontrol | Bukti |
|---|---|---|
| Akses API tanpa izin | Semua rute `/api` (kecuali `GET /api/health`, tanpa data) wajib token Bearer; perbandingan `secrets.compare_digest` | `tests/test_security_audit.py` menyisir seluruh skema OpenAPI: tanpa token dan token salah harus 401 |
| Halaman web lain memanggil API | CORS hanya `cors_origins`; token tidak ada di bundel peramban (proxy Next menambahkannya di server); WebSocket memakai tiket sekali pakai + cek Origin | tes CORS, tes tiket, `audit_security.py` memindai `.next/static` |
| Clickjacking, MIME sniffing, referrer | API: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, CSP ketat. Frontend: header yang sama + CSP (`default-src 'self'`, tanpa `object`/`frame`), Permissions-Policy | `tests/test_backup.py::test_security_headers_on_api`; `next.config.ts` |
| Rahasia bocor | `.env` tidak dilacak git; pemindai pola kunci API/token/kunci privat; log menyamarkan rahasia; cadangan tidak memuat `.env` | `scripts/audit_security.py` |
| Biaya tak terduga | API berbayar nonaktif secara bawaan; anggaran; verifikasi bawaan di `.env.example` | `audit_security.py`, `test_secure_defaults` |
| Agent bertindak sendiri | Tindakan berisiko tinggi/kritis butuh persetujuan CEO terikat hash isi; agent tidak bisa menyetujui; tidak ada pengiriman otomatis | tes Phase 6/8/9 |
| Kode AI menyerang host | Eksekusi hanya di sandbox WSL terpisah | Phase 5 |
| Arsip cadangan berbahaya | Verifikasi hash, tolak nama berkas di manifest yang keluar folder, tolak entri tar absolut/`..`/tautan, `filter="data"` | `tests/test_backup.py` |

## Hasil audit

- **Dependensi Python**: `pip-audit` terhadap seluruh paket terpasang — tidak ada kerentanan diketahui.
- **Dependensi npm produksi**: `npm audit --omit=dev` — 0 kerentanan.
- **Dependensi npm pengembangan**: 5 temuan tingkat tinggi pada rantai `eslint-config-next → fast-glob → micromatch` (ReDoS pada tooling lint).
  Tidak ikut ke produksi dan hanya memproses berkas milik sendiri; perbaikannya (`npm audit fix --force`) mengubah versi besar `eslint-config-next`,
  jadi ditunda sampai ada versi perbaikan yang kompatibel.
- **Pemindai rahasia**: bersih. Satu pengecualian disengaja: `apps/api/tests/test_reviewer.py` berisi pola kunci palsu untuk menguji pemindai milik Reviewer.

## Batasan yang diketahui

- CSP frontend memakai `'unsafe-inline'` pada `script-src` karena Next menyisipkan skrip hidrasi inline dan tidak memakai nonce per permintaan.
  Dampaknya kecil (tidak ada konten pihak ketiga atau masukan pengguna yang dirender sebagai HTML), tetapi bukan CSP terketat.
- Tidak ada login pengguna: kepemilikan token lokal adalah satu-satunya autentikasi. Cocok untuk mode lokal; **wajib diganti** sebelum mode cloud (Phase 12).
- Token berada di `.env` tanpa enkripsi disk; lindungi dengan enkripsi disk sistem operasi.
- Backend harus tetap terikat ke `127.0.0.1`; jangan diekspos ke jaringan tanpa autentikasi tambahan dan TLS.

## Menjalankan audit

```
python scripts/audit_security.py --deps      # rahasia, .gitignore, nilai bawaan, bundel klien, npm audit produksi
cd apps/api && .venv/Scripts/python -m pytest tests/test_security_audit.py
```
