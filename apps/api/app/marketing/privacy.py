"""Kontrol privasi data prospek (Bagian 4.4 B, 15, dan UU PDP No. 27/2022).

Prinsip: kumpulkan seminimal mungkin. Hanya data perusahaan dan kontak BISNIS (nama, jabatan, email kantor, telepon kantor).
Data pribadi sensitif, identitas, dan data finansial pribadi ditolak di setiap kolom teks bebas.
"""
import hashlib
import re


class PolicyError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


CONSUMER_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.id", "ymail.com", "hotmail.com", "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "proton.me", "protonmail.com", "aol.com", "mail.com", "gmx.com", "yandex.com", "zoho.com",
}

_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}$")
_LEGAL_PREFIX = re.compile(r"^(pt|cv|ud|pd|yayasan|koperasi)\b\.?\s*", re.I)
_LEGAL_SUFFIX = re.compile(r"\b(tbk|ltd|llc|inc|corp|co)\b\.?\s*$", re.I)

# (label, pola) — dipakai pada semua kolom teks bebas
_SENSITIVE = [
    ("nomor identitas (NIK/KTP 16 digit)", re.compile(r"(?<![\d.])\d{16}(?![\d])")),
    ("NPWP", re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b")),
    ("kata kunci data sensitif", re.compile(
        r"(?i)\b(agama|orientasi\s+seksual|riwayat\s+(kesehatan|penyakit)|penyakit|afiliasi\s+politik|alamat\s+rumah|tanggal\s+lahir|"
        r"tgl\.?\s+lahir|nomor\s+ktp|nik|npwp|kartu\s+kredit|rekening\s+pribadi|kata\s+sandi|password)\b")),
]


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total, alt = total + d, not alt
    return total % 10 == 0


def scan_sensitive(text: str | None) -> list[str]:
    """Kembalikan label temuan data sensitif pada teks (daftar kosong jika bersih)."""
    if not text:
        return []
    found = [label for label, rx in _SENSITIVE if rx.search(text)]
    for m in re.finditer(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", text):    # kandidat nomor kartu (13-19 digit, boleh dipisah)
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits) and "nomor kartu pembayaran" not in found:
            found.append("nomor kartu pembayaran")
    return found


def assert_clean(**fields: str | None) -> None:
    """Tolak jika ada kolom teks yang memuat data sensitif. Pesan menyebut kolom dan jenis temuan, bukan isinya."""
    bad = {name: scan_sensitive(value) for name, value in fields.items() if value}
    bad = {k: v for k, v in bad.items() if v}
    if bad:
        detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in bad.items())
        raise PolicyError("sensitive_data", f"Data sensitif tidak boleh disimpan ({detail})", {"fields": sorted(bad)})


def normalize_email(email: str | None) -> str | None:
    if email is None or not email.strip():
        return None
    e = email.strip().lower()
    if len(e) > 254 or not _EMAIL.match(e):
        raise PolicyError("invalid_email", "Format email tidak valid")
    return e


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[1]


def is_consumer_email(email: str) -> bool:
    return email_domain(email) in CONSUMER_EMAIL_DOMAINS


def normalize_domain(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    d = re.sub(r"^https?://", "", value.strip().lower()).split("/")[0].split("?")[0]
    d = re.sub(r"^www\.", "", d)
    if not re.fullmatch(r"([a-z0-9-]+\.)+[a-z]{2,}", d):
        raise PolicyError("invalid_domain", "Domain tidak valid")
    return d


def normalize_phone(phone: str | None) -> str | None:
    if phone is None or not phone.strip():
        return None
    p = re.sub(r"[^\d+]", "", phone)
    digits = p.lstrip("+")
    if not (8 <= len(digits) <= 15):
        raise PolicyError("invalid_phone", "Nomor telepon tidak valid")
    return p


def normalize_company_name(name: str) -> str:
    n = name.strip().casefold()
    n = _LEGAL_PREFIX.sub("", n)
    n = _LEGAL_SUFFIX.sub("", n)
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def hash_value(value: str) -> str:
    """SHA-256 dari nilai yang sudah dinormalisasi. Dipakai untuk daftar jangan-hubungi tanpa menyimpan data aslinya."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    return f"{phone[:3]}***{phone[-2:]}" if len(phone) > 5 else "***"


def mask_name(name: str | None) -> str | None:
    if not name:
        return name
    return " ".join(f"{part[:1]}***" for part in name.split())
