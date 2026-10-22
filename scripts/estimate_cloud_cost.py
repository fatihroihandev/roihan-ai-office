"""Estimasi biaya cloud (Phase 12) berbasis skenario. Jalankan: python scripts/estimate_cloud_cost.py

HARGA DI BAWAH ADALAH ASUMSI YANG HARUS DIVERIFIKASI di halaman harga resmi penyedia sebelum dipakai memutuskan (harga berubah dan
sumber sekunder saling bertentangan pada akhir Mei 2026). Ubah konstanta, jalankan ulang. Kurs diasumsikan; ganti sesuai kebutuhan.
"""
from __future__ import annotations

USD_IDR = 16_500  # asumsi; ganti dengan kurs terkini

# USD per 1 juta token (input, output). Sumber ringkasan Mei 2026; VERIFIKASI ke halaman resmi.
MODELS = {"haiku-class": (1.0, 5.0), "sonnet-class": (3.0, 15.0), "opus-class": (5.0, 25.0)}
BATCH_DISCOUNT = 0.5      # Batch API: diskon 50% bila hasil tidak perlu seketika (task latar belakang)

# USD per bulan, perkiraan kasar kelas harga publik; VERIFIKASI penyedia pilihan.
INFRA = {
    "VPS kecil (2 vCPU, 4 GB) untuk backend + SQLite": 20,
    "VPS + PostgreSQL terkelola kecil": 20 + 30,
    "Penyimpanan cadangan objek (50 GB)": 2,
    "Domain + TLS": 2,
}

# skenario: task per hari, token masuk dan keluar rata-rata per task (konteks dokumen + keluaran)
SCENARIOS = {"ringan": (20, 4000, 1500), "sedang": (100, 6000, 2000), "berat": (400, 8000, 2500)}


def monthly_llm(tasks_per_day: int, tin: int, tout: int, price: tuple[float, float], batch: bool = False) -> float:
    m = 30 * tasks_per_day
    usd = (m * tin / 1e6) * price[0] + (m * tout / 1e6) * price[1]
    return usd * (BATCH_DISCOUNT if batch else 1)


def main() -> None:
    print(f"Asumsi kurs: 1 USD = Rp{USD_IDR:,}\n")
    print("Biaya model berbayar per bulan (USD / Rupiah juta)")
    print(f"{'skenario':10}{'task/hr':>8}  " + "".join(f"{k:>34}" for k in MODELS))
    for name, (n, tin, tout) in SCENARIOS.items():
        cells = []
        for price in MODELS.values():
            full, b = monthly_llm(n, tin, tout, price), monthly_llm(n, tin, tout, price, True)
            cells.append(f"${full:7.0f} (batch ${b:5.0f}) Rp{full * USD_IDR / 1e6:5.1f}jt")
        print(f"{name:10}{n:>8}  " + "".join(f"{c:>34}" for c in cells))
    print("\nInfrastruktur tetap per bulan (USD):")
    for k, v in INFRA.items():
        print(f"  {k}: ${v}")
    base = INFRA["VPS kecil (2 vCPU, 4 GB) untuk backend + SQLite"] + INFRA["Penyimpanan cadangan objek (50 GB)"] + INFRA["Domain + TLS"]
    pg = INFRA["VPS + PostgreSQL terkelola kecil"] + INFRA["Penyimpanan cadangan objek (50 GB)"] + INFRA["Domain + TLS"]
    print(f"\nTotal infrastruktur: cloud sederhana ${base}/bln (~Rp{base * USD_IDR / 1e6:.1f} jt); dengan PostgreSQL terkelola ${pg}/bln (~Rp{pg * USD_IDR / 1e6:.1f} jt)")
    print("Model lokal (qwen2.5-coder:7b, ~6,6 token/dtk): biaya tambahan ~0 selain listrik; kapasitas keluaran maksimal ~570 ribu token/hari bila penuh 24 jam.")
    cap = 6.6 * 86400
    for name, (n, tin, tout) in SCENARIOS.items():
        need = n * tout
        print(f"  skenario {name}: butuh ~{need:,} token keluaran/hari = {need / cap * 100:.0f}% waktu GPU/CPU lokal (hanya generasi, belum termasuk memproses konteks)")


if __name__ == "__main__":
    main()
