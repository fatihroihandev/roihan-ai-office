"""Kebijakan sumber dan retensi data prospek. Nilai bawaan berasal dari konfigurasi (usulan yang dapat diubah CEO)."""
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import Settings
from app.marketing.privacy import PolicyError

# source_type -> aturan. `needs_url`: sumber publik harus dapat ditelusuri lewat URL.
SOURCE_RULES: dict[str, dict] = {
    "public_website": {"needs_url": True, "basis": "legitimate_interest_b2b", "label": "Situs web publik perusahaan"},
    "public_registry": {"needs_url": True, "basis": "legitimate_interest_b2b", "label": "Registri bisnis publik"},
    "referral": {"needs_url": False, "basis": "legitimate_interest_b2b", "label": "Rujukan dari pihak yang dikenal"},
    "inbound": {"needs_url": False, "basis": "inbound_inquiry", "label": "Prospek menghubungi kami lebih dulu"},
    "event": {"needs_url": False, "basis": "legitimate_interest_b2b", "label": "Pertemuan atau acara bisnis"},
    "manual": {"needs_url": False, "basis": "legitimate_interest_b2b", "label": "Dimasukkan langsung oleh CEO"},
}
# Sumber yang SENGAJA tidak didukung (ditampilkan pada kebijakan agar jelas mengapa ditolak)
FORBIDDEN_SOURCES = {
    "purchased_list": "Daftar yang dibeli tidak memiliki dasar pemrosesan yang sah",
    "social_media_scraping": "Menyalin data pribadi dari media sosial dilarang",
    "leaked_data": "Data bocor atau hasil peretasan dilarang",
    "private_group": "Grup atau forum privat tidak boleh diambil datanya",
}
SIZE_BANDS = ("micro", "small", "medium", "large", "unknown")
CONTACT_KINDS = ("note", "email_out", "email_in", "call", "meeting")


@dataclass(frozen=True)
class Policy:
    allowed_sources: frozenset[str]
    retention_no_interaction_days: int
    retention_after_interaction_days: int
    retention_auto_apply: bool
    min_score_for_sales: int
    outreach_channels: frozenset[str] = frozenset({"email"})
    outreach_min_days_between: int = 14
    outreach_max_per_day: int = 10
    content_channels: frozenset[str] = frozenset({"blog", "website", "linkedin", "instagram", "newsletter"})
    content_max_per_day: int = 5

    @classmethod
    def from_settings(cls, s: Settings) -> "Policy":
        return cls(frozenset(x.strip() for x in s.lead_allowed_sources.split(",") if x.strip()), s.lead_retention_no_interaction_days,
                   s.lead_retention_after_interaction_days, s.lead_retention_auto_apply, s.lead_min_score_for_sales,
                   frozenset(x.strip() for x in s.outreach_allowed_channels.split(",") if x.strip()), s.outreach_min_days_between_contacts,
                   s.outreach_max_per_day, frozenset(x.strip() for x in s.content_allowed_channels.split(",") if x.strip()),
                   s.content_max_publish_per_day)

    def describe(self) -> dict:
        return {
            "allowed_sources": [{"type": t, "label": SOURCE_RULES[t]["label"], "needs_url": SOURCE_RULES[t]["needs_url"],
                                 "basis": SOURCE_RULES[t]["basis"]} for t in SOURCE_RULES if t in self.allowed_sources],
            "forbidden_sources": [{"type": k, "reason": v} for k, v in FORBIDDEN_SOURCES.items()],
            "retention": {"no_interaction_days": self.retention_no_interaction_days,
                          "after_last_interaction_days": self.retention_after_interaction_days,
                          "auto_apply": self.retention_auto_apply, "action": "anonimisasi data pribadi (data perusahaan dipertahankan)"},
            "min_score_for_sales": self.min_score_for_sales,
            "external": {
                "outreach_channels": sorted(self.outreach_channels), "outreach_min_days_between_contacts": self.outreach_min_days_between,
                "outreach_max_per_day": self.outreach_max_per_day, "content_channels": sorted(self.content_channels),
                "content_max_publish_per_day": self.content_max_per_day,
                "rule": "Setiap pengiriman atau publikasi memerlukan approval CEO atas isi yang persis sama; tidak ada konektor yang mengirim sendiri.",
                "paid_ads": "belum didukung (memerlukan approval eksplisit dan batas biaya)",
            },
            "data_minimisation": {
                "stored": ["nama perusahaan", "industri", "ukuran", "kota", "website/domain", "nama kontak bisnis", "jabatan", "email kantor", "telepon kantor"],
                "rejected": ["NIK/KTP", "NPWP", "nomor kartu", "tanggal lahir", "alamat rumah", "agama", "kesehatan", "afiliasi politik",
                             "email pribadi (gmail/yahoo/dll) kecuali prospek menghubungi kami lebih dulu"],
            },
            "opt_out": "Daftar jangan-hubungi menyimpan hash (bukan data asli) secara permanen; prospek yang menolak tidak dapat didaftarkan ulang.",
        }


def validate_source_type(policy: Policy, source_type: str) -> dict:
    if source_type in FORBIDDEN_SOURCES:
        raise PolicyError("source_forbidden", f"Sumber '{source_type}' dilarang: {FORBIDDEN_SOURCES[source_type]}")
    if source_type not in SOURCE_RULES:
        raise PolicyError("source_unknown", f"Jenis sumber tidak dikenal: {source_type}")
    if source_type not in policy.allowed_sources:
        raise PolicyError("source_not_allowed", f"Jenis sumber '{source_type}' tidak diizinkan oleh kebijakan saat ini")
    return SOURCE_RULES[source_type]


def validate_url(url: str | None, required: bool) -> str | None:
    if not url or not url.strip():
        if required:
            raise PolicyError("source_url_required", "Sumber publik wajib mencantumkan URL agar dapat ditelusuri")
        return None
    u = url.strip()
    p = urlparse(u)
    host = (p.hostname or "").lower()
    if p.scheme not in {"http", "https"} or not host or "." not in host or host == "localhost":
        raise PolicyError("source_url_invalid", "URL sumber tidak valid (harus http/https dengan host publik)")
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip:      # (PolicyError turunan ValueError: jangan dilempar di dalam try di atas)
        raise PolicyError("source_url_invalid", "URL sumber tidak boleh berupa alamat IP")
    if len(u) > 2000 or re.search(r"\s", u):
        raise PolicyError("source_url_invalid", "URL sumber terlalu panjang atau mengandung spasi")
    return u
