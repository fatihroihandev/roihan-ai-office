"""SEO & Digital Marketing (Phase 14, Bagian 29.B): audit teknis deterministik, pemeriksaan klaim SEO, dan KPI.

Prinsip: tidak ada akses internet dan tidak ada angka karangan. Audit hanya memeriksa HTML/robots/sitemap yang DIBERIKAN;
volume dan persaingan kata kunci hanya dipakai bila ada pada materi sumber; KPI yang datanya belum ada bernilai None (bukan nol).
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CampaignMetric, Lead, LeadSource, SeoMetric
from app.marketing import service

MAX_HTML = 200_000
SEO_METRICS = ("impressions", "clicks", "organic_sessions", "conversions", "position")

# Klaim yang tidak boleh dibuat SEO: tidak ada yang dapat menjamin peringkat atau pendapatan.
_GUARANTEE = [re.compile(p, re.I) for p in (
    r"\bdijamin\b", r"\bjaminan\s+(?:peringkat|ranking|posisi|trafik|pendapatan)", r"\bpasti\s+(?:naik|peringkat|ranking|laris|banjir)",
    r"\b(?:peringkat|ranking|posisi)\s+(?:1|satu|pertama)\b", r"\b(?:no\.?|nomor)\s*(?:1|satu)\s+di\s+google", r"\bhalaman\s+pertama\s+google\b",
    r"\bguarantee[d]?\b", r"\b#1\s+(?:on|di)\s+google\b", r"\btop\s*1\b", r"\b100\s*%\s*(?:naik|sukses|berhasil|peringkat)",
)]


def lint_seo_claims(text: str) -> list[str]:
    """Frasa jaminan peringkat/pendapatan yang ditemukan pada teks (kosong = bersih)."""
    return [m.group(0) for p in _GUARANTEE for m in [p.search(text or "")] if m]


# ------------------------------------------------------------------ audit teknis

class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title, self._in_title = "", False
        self.meta: dict[str, str] = {}
        self.canonical: str | None = None
        self.lang: str | None = None
        self.h1 = self.h2 = 0
        self.imgs = self.imgs_no_alt = 0
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang") or None
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "link" and "canonical" in a.get("rel", "").lower():
            self.canonical = a.get("href", "")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "h2":
            self.h2 += 1
        elif tag == "img":
            self.imgs += 1
            if not a.get("alt", "").strip():
                self.imgs_no_alt += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True
            self.jsonld.append("")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_jsonld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_jsonld and self.jsonld:
            self.jsonld[-1] += data


def _f(fid: str, severity: str, message: str, recommendation: str = "", evidence: str = "") -> dict:
    return {"id": fid, "severity": severity, "message": message, "recommendation": recommendation, "evidence": evidence[:200]}


def _robots_blocks_all(robots: str) -> bool:
    agent_all = False
    for raw in robots.splitlines():
        line = raw.split("#", 1)[0].strip().lower()
        if line.startswith("user-agent:"):
            agent_all = line.split(":", 1)[1].strip() == "*"
        elif agent_all and re.fullmatch(r"disallow:\s*/", line):
            return True
    return False


def audit_html(url: str, html: str, robots_txt: str = "", sitemap_xml: str = "") -> dict:
    """Audit SEO teknis dari HTML yang diberikan. Tanpa jaringan: tautan rusak dan performa TIDAK dapat diperiksa dan dinyatakan begitu."""
    p = _Page()
    p.feed(html[:MAX_HTML])
    findings: list[dict] = []
    title = re.sub(r"\s+", " ", p.title).strip()
    desc = p.meta.get("description", "").strip()
    robots_meta = p.meta.get("robots", "").lower()

    if not title:
        findings.append(_f("title_missing", "critical", "Elemen <title> tidak ada atau kosong.", "Tambahkan judul unik 30-60 karakter yang memuat topik utama halaman."))
    elif not 30 <= len(title) <= 60:
        findings.append(_f("title_length", "warning", f"Panjang judul {len(title)} karakter (disarankan 30-60).", "Ringkas atau lengkapi judul agar tidak terpotong di hasil pencarian.", title))
    if not desc:
        findings.append(_f("description_missing", "warning", "Meta description tidak ada.", "Tulis ringkasan akurat 70-160 karakter; jangan memuat klaim yang belum terbukti."))
    elif not 70 <= len(desc) <= 160:
        findings.append(_f("description_length", "info", f"Panjang meta description {len(desc)} karakter (disarankan 70-160).", "", desc))
    if p.h1 == 0:
        findings.append(_f("h1_missing", "warning", "Tidak ada <h1>.", "Gunakan tepat satu <h1> yang menjelaskan inti halaman."))
    elif p.h1 > 1:
        findings.append(_f("h1_multiple", "info", f"Ada {p.h1} elemen <h1>.", "Pertahankan satu <h1> dan gunakan <h2> untuk subbagian."))
    if "noindex" in robots_meta:
        findings.append(_f("noindex", "critical", "Halaman menandai noindex: tidak akan muncul di hasil pencarian.", "Hapus noindex bila halaman memang ingin ditemukan.", robots_meta))
    if p.canonical is None:
        findings.append(_f("canonical_missing", "warning", "Tidak ada tautan canonical.", "Tambahkan <link rel=\"canonical\"> ke URL utama halaman."))
    elif url and p.canonical and urlparse(p.canonical).netloc and urlparse(p.canonical).netloc != urlparse(url).netloc:
        findings.append(_f("canonical_other_domain", "warning", "Canonical menunjuk domain lain.", "Pastikan memang disengaja.", p.canonical))
    if not p.lang:
        findings.append(_f("lang_missing", "info", "Atribut lang pada <html> tidak ada.", "Tambahkan lang=\"id\" atau sesuai bahasa halaman."))
    if "viewport" not in p.meta:
        findings.append(_f("viewport_missing", "warning", "Meta viewport tidak ada (tampilan seluler terdampak).", "Tambahkan <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."))
    if p.imgs_no_alt:
        findings.append(_f("img_alt_missing", "warning", f"{p.imgs_no_alt} dari {p.imgs} gambar tanpa teks alt.", "Beri alt yang deskriptif (aksesibilitas dan SEO gambar)."))
    if not any(k.startswith("og:") for k in p.meta):
        findings.append(_f("og_missing", "info", "Tag Open Graph tidak ada.", "Tambahkan og:title, og:description, og:image untuk pratinjau berbagi."))
    ld_bad = 0
    for blob in p.jsonld:
        try:
            json.loads(blob)
        except ValueError:
            ld_bad += 1
    if ld_bad:
        findings.append(_f("jsonld_invalid", "warning", f"{ld_bad} blok JSON-LD tidak valid.", "Perbaiki sintaks JSON-LD."))
    host = urlparse(url).netloc
    internal = sum(1 for h in p.links if h.startswith("/") or (host and urlparse(h).netloc == host))
    if p.links and internal == 0:
        findings.append(_f("no_internal_links", "info", "Tidak ada tautan internal.", "Tautkan ke halaman layanan/artikel terkait."))
    if robots_txt.strip() and _robots_blocks_all(robots_txt):
        findings.append(_f("robots_blocks_all", "critical", "robots.txt memblokir seluruh situs untuk semua crawler.", "Hapus 'Disallow: /' pada User-agent: * bila situs harus terindeks."))
    sitemap_urls = 0
    if sitemap_xml.strip():
        try:
            root = ElementTree.fromstring(sitemap_xml)
            locs = [(e.text or "").strip().rstrip("/") for e in root.iter() if e.tag.endswith("}loc") or e.tag == "loc"]
            sitemap_urls = len(locs)
            if url and url.rstrip("/") not in locs:
                findings.append(_f("url_not_in_sitemap", "info", "URL halaman tidak ada di sitemap yang diberikan.", "Tambahkan URL kanonik ke sitemap.xml."))
        except ElementTree.ParseError:
            findings.append(_f("sitemap_invalid", "warning", "sitemap.xml tidak valid (XML rusak).", "Perbaiki format sitemap."))
    else:
        findings.append(_f("sitemap_not_provided", "info", "Sitemap tidak diberikan; tidak diperiksa.", ""))
    if not robots_txt.strip():
        findings.append(_f("robots_not_provided", "info", "robots.txt tidak diberikan; tidak diperiksa.", ""))
    not_checked = ["tautan rusak (butuh jaringan)", "kecepatan dan Core Web Vitals (butuh pengukuran nyata)", "peringkat pencarian (butuh data Search Console)"]
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("critical", "warning", "info")}
    return {"url": url, "page": {"title": title, "description": desc, "h1": p.h1, "h2": p.h2, "images": p.imgs, "internal_links": internal,
                                 "external_links": len(p.links) - internal, "jsonld_blocks": len(p.jsonld), "sitemap_urls": sitemap_urls},
            "findings": findings, "counts": counts, "not_checked": not_checked}


# ------------------------------------------------------------------ pemeriksaan keyword

INTENTS = {"informational", "commercial", "transactional", "navigational"}


def _digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def ground_keywords(items: list[dict], material: str) -> list[dict]:
    """Volume dan persaingan hanya dipertahankan bila kutipan bukti ada pada materi dan memuat kata kunci serta angkanya; selain itu None."""
    norm = re.sub(r"\s+", " ", material or "").casefold()
    out = []
    for it in items:
        kw = re.sub(r"\s+", " ", str(it.get("keyword", ""))).strip()
        if len(kw) < 2:
            continue
        quote = re.sub(r"\s+", " ", str(it.get("evidence_quote", ""))).strip()
        backed = len(quote) >= 3 and quote.casefold() in norm and kw.casefold() in quote.casefold()
        volume = it.get("volume")
        if not (backed and isinstance(volume, (int, float)) and not isinstance(volume, bool) and volume >= 0 and _digits(str(int(volume))) in _digits(quote)):
            volume = None
        comp = str(it.get("competition") or "").strip()
        if not (backed and comp and comp.casefold() in quote.casefold()):
            comp = None
        rationale = str(it.get("rationale", ""))[:400]
        flagged = lint_seo_claims(rationale)
        out.append({"keyword": kw, "intent": it.get("intent") if it.get("intent") in INTENTS else "informational",
                    "priority": it.get("priority") if it.get("priority") in {"high", "medium", "low"} else "medium",
                    "rationale": "" if flagged else rationale, "volume": volume, "competition": comp,
                    "data_available": volume is not None or comp is not None, "evidence_quote": quote if backed else "",
                    "flagged_claims": flagged})
    return out


# ------------------------------------------------------------------ KPI

def record_metric(session: Session, metric: str, value: float, *, page: str | None, period: str, recorded_by: str, note: str | None = None) -> SeoMetric:
    if metric not in SEO_METRICS:
        raise service.MarketingError("invalid_metric", f"Metrik SEO tidak dikenal: {metric}")
    if value < 0 or (metric == "position" and value < 1):
        raise service.MarketingError("invalid_value", "Nilai metrik tidak valid")
    row = SeoMetric(metric=metric, value=float(value), page=(page or None), period=period, recorded_by=recorded_by, note=note)
    session.add(row)
    session.flush()
    return row


def kpis(session: Session) -> dict:
    """KPI pemasaran dan SEO. None = belum ada data (bukan nol). ROI hanya bila biaya dan pendapatan kampanye tercatat."""
    rows = list(session.scalars(select(SeoMetric)))

    def total(name: str):
        v = [r.value for r in rows if r.metric == name]
        return sum(v) if v else None

    pos = [r.value for r in rows if r.metric == "position"]
    imp, clk = total("impressions"), total("clicks")
    camp = list(session.scalars(select(CampaignMetric)))
    cost = sum(m.value for m in camp if m.metric == "cost_idr") if any(m.metric == "cost_idr" for m in camp) else None
    revenue = sum(m.value for m in camp if m.metric == "revenue_idr") if any(m.metric == "revenue_idr" for m in camp) else None
    inbound = [s.id for s in session.scalars(select(LeadSource).where(LeadSource.source_type == "inbound"))]
    inbound_leads = len(list(session.scalars(select(Lead).where(Lead.source_id.in_(inbound))))) if inbound else 0
    a = service.analytics(session)
    organic = {"impressions": imp, "clicks": clk, "ctr": round(clk / imp, 4) if imp and clk is not None else None,
               "avg_position": round(sum(pos) / len(pos), 1) if pos else None, "organic_sessions": total("organic_sessions"),
               "page_conversions": total("conversions")}
    notes = []
    if not rows:
        notes.append("Belum ada data pencarian organik yang dicatat; angka kosong berarti belum diketahui, bukan nol.")
    if cost is None or revenue is None:
        notes.append("ROI belum dihitung: biaya dan pendapatan kampanye belum keduanya tercatat.")
    notes.append("Atribusi lead ke kanal organik belum dapat dipastikan; 'lead inbound' hanya perkiraan atas sumber inbound.")
    return {
        "organic": organic,
        "leads": {"total": a["leads_total"], "qualified": a["qualified_leads"], "inbound": inbound_leads, "by_source": a["by_source"]},
        "funnel": {"lead_to_meeting_rate": a["lead_to_meeting_rate"], "opportunity_conversion_rate": a["opportunity_conversion_rate"], "win_rate": a["win_rate"],
                   "avg_hours_to_first_interaction": a["avg_hours_to_first_interaction"]},
        "money": {"cost_idr": cost, "revenue_idr": revenue, "roi": round((revenue - cost) / cost, 4) if cost and revenue is not None else None,
                  "revenue_recorded_idr": a["revenue_recorded_idr"]},
        "notes": notes,
    }
