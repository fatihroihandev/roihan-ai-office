# Roihan Software House

Platform software house lokal berbasis AI: tim agent Engineering dan Marketing, model router, approval center, dan kantor virtual 3D.

Sumber acuan utama: [`docs/MASTER_DEVELOPMENT.md`](docs/MASTER_DEVELOPMENT.md). Baca dokumen itu sebelum mengubah kode.

## Status

Phase 0 (Hardware & Environment) sedang berjalan. Belum ada aplikasi yang dapat dijalankan.

## Prasyarat Phase 0

- Python 3.10+
- Git
- [Ollama](https://ollama.com) dengan model `qwen2.5-coder:7b` (`ollama pull qwen2.5-coder:7b`)

## Benchmark model lokal

```
python scripts/benchmark_ollama.py --model qwen2.5-coder:7b
```

Opsi: `--runs-json 20`, `--skip-json`, `--skip-code`, `--skip-bugfix`. Hasil mentah disimpan di `data/benchmarks/` (struktur, prompt, versi model, dan output).

Kode hasil model dijalankan sebagai subprocess lokal dengan timeout dan filter impor berbahaya. Ini **bukan sandbox**; sandbox sebenarnya dikerjakan di Phase 5.

## Konfigurasi

Salin `.env.example` ke `.env`. Secret tidak boleh di-commit.
