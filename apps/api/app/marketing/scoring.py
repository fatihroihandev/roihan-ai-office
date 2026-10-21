"""Skor kecocokan prospek 0-100. Deterministik dan transparan: setiap poin punya alasan (bukan angka dari model)."""
import re
from datetime import datetime

from app.marketing.privacy import is_consumer_email

STOP = {"yang", "dan", "atau", "untuk", "dengan", "dari", "pada", "dapat", "bisa", "akan", "adalah", "ini", "itu", "dalam", "serta",
        "the", "and", "for", "with", "that", "this", "from", "usaha", "perusahaan", "bisnis", "company", "business"}
SOURCE_POINTS = {"inbound": 15, "referral": 13, "event": 10, "public_registry": 8, "public_website": 7, "manual": 6}
SIZE_POINTS = {"small": 15, "medium": 15, "micro": 8, "large": 8, "unknown": 4}
DECISION_MAKER = re.compile(r"(?i)\b(direktur|director|owner|pemilik|founder|pendiri|ceo|cto|cio|coo|cfo|chief|manajer|manager|kepala|head|vp|general\s+manager)\b")


def _words(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 4 and w not in STOP}


def _row(factor: str, points: int, maximum: int, note: str) -> dict:
    return {"factor": factor, "points": points, "max": maximum, "note": note}


def score_lead(*, company: dict, lead: dict, source_type: str, product: dict | None, now: datetime) -> tuple[int, list[dict]]:
    rows: list[dict] = []

    # 1. Kecocokan dengan target pelanggan produk (30)
    if product and (product.get("target_customers") or product.get("description")):
        target = _words(product.get("target_customers")) | _words(product.get("description"))
        prospect = _words(company.get("industry")) | _words(company.get("description")) | _words(company.get("name"))
        overlap = target & prospect
        pts = min(30, len(overlap) * 10)
        rows.append(_row("kecocokan produk", pts, 30, f"kata yang sama dengan target pelanggan: {', '.join(sorted(overlap)) or 'tidak ada'}"))
    else:
        rows.append(_row("kecocokan produk", 0, 30, "produk atau target pelanggan belum ditentukan"))

    # 2. Ukuran perusahaan (15)
    band = company.get("size_band") or "unknown"
    rows.append(_row("ukuran perusahaan", SIZE_POINTS.get(band, 4), 15, band))

    # 3. Kualitas sumber (15)
    rows.append(_row("kualitas sumber", SOURCE_POINTS.get(source_type, 5), 15, source_type))

    # 4. Kualitas kontak (20)
    pts, notes = 0, []
    if lead.get("contact_name"):
        pts, notes = pts + 3, notes + ["ada nama"]
    title = lead.get("contact_title")
    if title and DECISION_MAKER.search(title):
        pts, notes = pts + 8, notes + [f"jabatan pengambil keputusan ({title})"]
    elif title:
        pts, notes = pts + 3, notes + ["ada jabatan"]
    email = lead.get("contact_email")
    if email and not is_consumer_email(email):
        pts, notes = pts + 6, notes + ["email kantor"]
    elif email:
        pts, notes = pts + 2, notes + ["email pribadi (prospek menghubungi lebih dulu)"]
    if lead.get("contact_phone"):
        pts, notes = pts + 3, notes + ["ada telepon"]
    rows.append(_row("kualitas kontak", min(20, pts), 20, ", ".join(notes) or "tidak ada kontak"))

    # 5. Kelengkapan data perusahaan (10)
    filled = [k for k in ("industry", "city", "website", "description") if company.get(k)] + (["domain"] if company.get("domain") else [])
    rows.append(_row("kelengkapan data", min(10, len(filled) * 3 if len(filled) < 4 else 10), 10, f"{len(filled)} kolom terisi"))

    # 6. Kesegaran data (10)
    collected = lead.get("collected_at")
    if collected:
        age = (now.replace(tzinfo=None) - collected.replace(tzinfo=None)).days
        fresh = 10 if age <= 30 else 6 if age <= 90 else 3 if age <= 180 else 0
        rows.append(_row("kesegaran data", fresh, 10, f"{max(age, 0)} hari sejak dikumpulkan"))
    else:
        rows.append(_row("kesegaran data", 0, 10, "tanggal pengumpulan tidak diketahui"))

    return min(100, sum(r["points"] for r in rows)), rows
