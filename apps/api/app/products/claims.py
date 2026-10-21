"""Linter klaim pemasaran. Memeriksa draf teks promosi terhadap ringkasan resmi (marketing_brief).

Deterministik dan konservatif: lebih baik menolak kalimat yang meragukan daripada meloloskan klaim yang belum terbukti.
Dipakai oleh konten Marketing (Phase 9) sebelum draf boleh keluar dari status draft.
"""
import re

STOPWORDS = {
    "yang", "dan", "atau", "untuk", "dengan", "dari", "pada", "dapat", "bisa", "akan", "sudah", "telah", "adalah", "ini", "itu",
    "dalam", "oleh", "juga", "serta", "agar", "karena", "tidak", "ada", "the", "and", "for", "with", "that", "this", "from",
    "fitur", "produk", "aplikasi", "sistem",
}

ABSOLUTE = re.compile(
    r"(?<!\w)(terbaik(?:nya)?|nomor\s*1|no\.?\s*1|100\s*%|tanpa\s+(bug|cacat|kesalahan|error)|bebas\s+(bug|cacat|error)|dijamin|garansi|"
    r"paling\s+(cepat|aman|murah|lengkap|canggih)|tidak\s+pernah\s+(gagal|error)|sempurna(?:nya)?|zero[\s-]?bug|"
    r"best|guaranteed|bulletproof|unhackable|risk[\s-]?free)(?!\w)", re.I)
RELEASED_CLAIM = re.compile(
    r"(?<!\w)(sudah\s+(dirilis|rilis|tersedia|launching|diluncurkan)|rilis\s+resmi|siap\s+(produksi|pakai|digunakan|dipakai)|"
    r"production[\s-]?ready|generally\s+available|launched|stabil|stable|versi\s+final|diluncurkan|telah\s+hadir|resmi\s+(hadir|meluncur)|"
    r"(peluncuran|meluncurkan)(?!\s+(versi\s+)?beta))(?!\w)", re.I)
PRICING = re.compile(r"(\brp\.?\s?\d|\bidr\b|\busd\b|\$\s?\d|\bharga\b|\bgratis\b|\bfree\b|\bdiskon\b|\bpromo\s+hemat\b|/\s?bulan|per\s+bulan)", re.I)


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 4 and w not in STOPWORDS}


def _finding(kind: str, detail: str, match: str = "", severity: str = "blocking") -> dict:
    return {"type": kind, "severity": severity, "detail": detail, "match": match}


def check_claims(text: str, brief: dict) -> dict:
    """Kembalikan {ok, findings}. `ok` hanya True jika tidak ada temuan berseverity blocking."""
    findings: list[dict] = []
    if not brief["usable_for_promotion"]:
        reasons = "; ".join(brief["blocked_reasons"]) or "izin pemasaran belum diberikan CEO"
        findings.append(_finding("not_cleared", f"Produk belum diizinkan dipromosikan: {reasons}"))

    text_words = _words(text)
    for c in brief["unverified_claims"]:
        words = _words(c["text"])
        if len(words) >= 2 and len(words & text_words) / len(words) >= 0.6:
            findings.append(_finding("unverified_feature", f"Teks menyinggung klaim yang belum terverifikasi ({c['status']}): {c['text']}", c["text"]))

    for m in ABSOLUTE.finditer(text):
        findings.append(_finding("absolute_claim", "Klaim mutlak tidak dapat dibuktikan", m.group(0)))

    status = brief["version"]["status"]
    if status != "released":
        for m in RELEASED_CLAIM.finditer(text):
            findings.append(_finding("status_misrepresentation", f"Teks menyiratkan produk sudah rilis, padahal statusnya '{status}'", m.group(0)))
    if brief["promotion_label"] == "BETA" and not re.search(r"\bbeta\b", text, re.I):
        findings.append(_finding("beta_not_disclosed", "Produk berstatus beta tetapi teks tidak menyebut bahwa ini beta"))

    if brief["pricing"] is None:
        for m in PRICING.finditer(text):
            findings.append(_finding("unapproved_pricing", "Teks menyebut harga atau penawaran padahal harga belum disetujui CEO", m.group(0)))

    return {"ok": not any(f["severity"] == "blocking" for f in findings), "findings": findings}
