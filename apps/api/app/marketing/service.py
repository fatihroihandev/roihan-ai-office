"""Lead Management, Sales Pipeline, dan retensi data prospek (Bagian 5 dan 15).

Aturan utama:
  - sumber harus lolos kebijakan dan tercatat (provenance); data sensitif dan email pribadi ditolak
  - prospek yang menolak (opt-out) tidak dapat didaftarkan ulang (daftar jangan-hubungi berisi hash)
  - perpindahan tahap penjualan didasarkan pada interaksi NYATA yang dicatat manusia, bukan klaim agent
  - data pribadi disimpan seminimal mungkin dan dianonimkan sesuai retensi
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.db.models import (
    AuditLog, ClientRequirement, Company, Lead, LeadInteraction, LeadSource, OutreachRecord, Product, SalesOpportunity,
    SuppressionEntry,
)
from app.marketing import access
from app.marketing.access import AccessDenied
from app.marketing.policy import CONTACT_KINDS, SIZE_BANDS, Policy, validate_source_type, validate_url
from app.marketing.privacy import (
    PolicyError, assert_clean, email_domain, hash_value, is_consumer_email, normalize_company_name, normalize_domain,
    normalize_email, normalize_phone,
)
from app.marketing.scoring import score_lead

__all__ = ["MarketingError", "PolicyError", "AccessDenied"]


class MarketingError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


LEAD_TRANSITIONS: dict[str, set[str]] = {
    "new": {"qualified", "disqualified"},
    "qualified": {"contacted", "disqualified"},
    "contacted": {"meeting", "disqualified"},
    "meeting": {"disqualified"},
    "opportunity": set(),                 # hanya lewat tahap peluang (won/lost)
    "won": set(), "lost": set(),
    "disqualified": {"new"},
    "do_not_contact": set(),
}
SETTABLE_STATUSES = {"qualified", "contacted", "meeting", "disqualified", "new"}
OPP_STAGES = ["qualification", "proposal", "negotiation", "won", "lost"]
OPP_TRANSITIONS: dict[str, set[str]] = {
    "qualification": {"proposal", "lost"}, "proposal": {"negotiation", "won", "lost"}, "negotiation": {"won", "lost"},
    "won": set(), "lost": set(),
}
OPEN_STAGES = {"qualification", "proposal", "negotiation"}
OUTREACH_OPEN = {"draft", "blocked_by_claim_check", "ready_for_review"}


def _naive(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo else dt


def _audit(session: Session, action: str, entity_type: str, entity_id: str, actor: str, details: dict | None = None) -> None:
    """Audit TANPA data pribadi: hanya ID dan metadata."""
    session.add(AuditLog(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, details=details or {}))


def _human(actor: str) -> None:
    if not access.is_human(actor):
        raise AccessDenied(actor, "keputusan manusia")


def _lead_open(lead: Lead) -> None:
    if lead.anonymized_at is not None:
        raise MarketingError("anonymized", "Data prospek sudah dianonimkan")
    if lead.do_not_contact:
        raise MarketingError("do_not_contact", "Prospek ini menolak dihubungi (opt-out)")


# ------------------------------------------------------------------ suppression

def is_suppressed(session: Session, *, email: str | None = None, domain: str | None = None) -> str | None:
    """Kembalikan alasan jika email atau domain ada di daftar jangan-hubungi."""
    probes = []
    if email:
        probes += [("email", hash_value(email)), ("domain", hash_value(email_domain(email)))]
    if domain:
        probes.append(("domain", hash_value(domain)))
    for kind, h in probes:
        row = session.scalar(select(SuppressionEntry).where(SuppressionEntry.kind == kind, SuppressionEntry.value_hash == h))
        if row is not None:
            return f"{kind}:{row.reason}"
    return None


def add_suppression(session: Session, *, kind: str, value: str, reason: str, actor: str) -> SuppressionEntry:
    access.require(actor, "suppression.write") if not access.is_human(actor) else None
    if kind not in {"email", "domain"}:
        raise MarketingError("invalid_kind", "Jenis harus email atau domain")
    if reason not in {"opt_out", "erasure", "bounce", "complaint"}:
        raise MarketingError("invalid_reason", "Alasan tidak dikenal")
    norm = normalize_email(value) if kind == "email" else normalize_domain(value)
    if not norm:
        raise PolicyError("invalid_value", "Nilai kosong")
    h = hash_value(norm)
    existing = session.scalar(select(SuppressionEntry).where(SuppressionEntry.kind == kind, SuppressionEntry.value_hash == h))
    if existing:
        return existing
    row = SuppressionEntry(kind=kind, value_hash=h, reason=reason)
    session.add(row)
    session.flush()
    _audit(session, "suppression.add", "suppression", row.id, actor, {"kind": kind, "reason": reason})
    return row


# ------------------------------------------------------------------ sumber, perusahaan, prospek

def create_source(session: Session, policy: Policy, *, actor: str, source_type: str, url: str | None = None, title: str | None = None,
                  collected_at: datetime | None = None, method: str | None = None, note: str | None = None,
                  now: datetime | None = None) -> LeadSource:
    access.require(actor, "source.create")
    rule = validate_source_type(policy, source_type)
    clean_url = validate_url(url, rule["needs_url"])
    assert_clean(title=title, note=note)
    now = now or utcnow()
    when = collected_at or now
    if _naive(when) > _naive(now) + timedelta(minutes=5):
        raise PolicyError("collected_in_future", "Tanggal pengumpulan tidak boleh di masa depan")
    src = LeadSource(source_type=source_type, url=clean_url, title=title, collected_at=when, collected_by=actor,
                     method=method or ("manual" if access.is_human(actor) else "agent_extraction"), note=note)
    session.add(src)
    session.flush()
    return src


def get_or_create_company(session: Session, *, actor: str, name: str, domain: str | None = None, industry: str | None = None,
                          size_band: str | None = None, city: str | None = None, website: str | None = None,
                          description: str | None = None) -> tuple[Company, bool]:
    access.require(actor, "company.write")
    name = (name or "").strip()
    norm = normalize_company_name(name)
    if not norm:
        raise PolicyError("company_name_required", "Nama perusahaan wajib diisi")
    assert_clean(company_name=name, industry=industry, city=city, description=description)
    size = size_band or "unknown"
    if size not in SIZE_BANDS:
        raise PolicyError("invalid_size_band", f"Ukuran harus salah satu dari {SIZE_BANDS}")
    site = validate_url(website, False)
    dom = normalize_domain(domain or site)
    existing = None
    if dom:
        existing = session.scalar(select(Company).where(Company.domain == dom))
    if existing is None:
        existing = session.scalar(select(Company).where(Company.normalized_name == norm))
    if existing is not None:     # lengkapi kolom yang masih kosong, jangan menimpa data yang ada
        for field, value in (("industry", industry), ("city", city), ("website", site), ("description", description), ("domain", dom)):
            if value and not getattr(existing, field):
                setattr(existing, field, value)
        if size != "unknown" and existing.size_band == "unknown":
            existing.size_band = size
        return existing, False
    company = Company(name=name, normalized_name=norm, domain=dom, industry=industry, size_band=size, city=city, website=site, description=description)
    session.add(company)
    session.flush()
    return company, True


def _company_dict(c: Company) -> dict:
    return {"name": c.name, "industry": c.industry, "size_band": c.size_band, "city": c.city, "website": c.website,
            "domain": c.domain, "description": c.description}


def _product_dict(session: Session, product_id: str | None) -> dict | None:
    p = session.get(Product, product_id) if product_id else None
    return {"target_customers": p.target_customers, "description": p.description} if p else None


def recompute_score(session: Session, policy: Policy, lead: Lead, now: datetime | None = None) -> Lead:
    company, source = session.get(Company, lead.company_id), session.get(LeadSource, lead.source_id)
    lead.score, lead.score_breakdown = score_lead(
        company=_company_dict(company),
        lead={"contact_name": lead.contact_name, "contact_title": lead.contact_title, "contact_email": lead.contact_email,
              "contact_phone": lead.contact_phone, "collected_at": lead.collected_at},
        source_type=source.source_type, product=_product_dict(session, lead.product_id), now=now or utcnow())
    return lead


def _clean_contact(contact: dict | None, source_type: str) -> dict:
    c = contact or {}
    name, title = (c.get("name") or "").strip() or None, (c.get("title") or "").strip() or None
    email, phone = normalize_email(c.get("email")), normalize_phone(c.get("phone"))
    for label, v, limit in (("nama kontak", name, 120), ("jabatan", title, 120)):
        if v and len(v) > limit:
            raise PolicyError("field_too_long", f"{label} maksimal {limit} karakter")
    assert_clean(contact_name=name, contact_title=title)
    if email and is_consumer_email(email) and source_type != "inbound":
        raise PolicyError("personal_email_not_allowed",
                          "Email pribadi (gmail/yahoo/dll) tidak diizinkan untuk prospek B2B, kecuali prospek menghubungi kami lebih dulu")
    return {"contact_name": name, "contact_title": title, "contact_email": email, "contact_phone": phone}


def create_lead(session: Session, policy: Policy, *, actor: str, company: dict, contact: dict | None, source: dict | str,
                product_id: str | None = None, now: datetime | None = None) -> Lead:
    access.require(actor, "lead.create")
    now = now or utcnow()
    src = session.get(LeadSource, source) if isinstance(source, str) else create_source(session, policy, actor=actor, now=now, **source)
    if src is None:
        raise MarketingError("source_not_found", "Sumber tidak ditemukan")
    rule = validate_source_type(policy, src.source_type)
    cc = _clean_contact(contact, src.source_type)
    if product_id and session.get(Product, product_id) is None:
        raise MarketingError("product_not_found", "Produk tidak ditemukan")

    dom_probe = normalize_domain(company.get("domain") or company.get("website"))
    reason = is_suppressed(session, email=cc["contact_email"], domain=dom_probe)
    if reason:
        raise MarketingError("suppressed", "Prospek ada di daftar jangan-hubungi; tidak dapat didaftarkan", {"reason": reason})

    comp, _ = get_or_create_company(session, actor=actor, **company)
    email_hash = hash_value(cc["contact_email"]) if cc["contact_email"] else None
    if email_hash:
        dup = session.scalar(select(Lead).where(Lead.email_hash == email_hash))
        if dup:
            raise MarketingError("duplicate_lead", "Prospek dengan email ini sudah ada", {"lead_id": dup.id})
    if cc["contact_name"]:
        dup = session.scalar(select(Lead).where(Lead.company_id == comp.id, func.lower(Lead.contact_name) == cc["contact_name"].lower()))
        if dup:
            raise MarketingError("duplicate_lead", "Kontak dengan nama ini pada perusahaan yang sama sudah ada", {"lead_id": dup.id})

    lead = Lead(company_id=comp.id, source_id=src.id, product_id=product_id, status="new", basis=rule["basis"], owner="lead_generation",
                email_hash=email_hash, collected_at=src.collected_at, created_by=actor, **cc)
    session.add(lead)
    session.flush()
    recompute_score(session, policy, lead, now)
    _audit(session, "lead.create", "lead", lead.id, actor, {"company_id": comp.id, "source_type": src.source_type, "score": lead.score})
    return lead


def update_contact(session: Session, policy: Policy, lead: Lead, *, actor: str, **fields) -> Lead:
    access.require(actor, "lead.update_enrichment")
    _lead_open(lead)
    source = session.get(LeadSource, lead.source_id)
    cc = _clean_contact({"name": fields.get("contact_name", lead.contact_name), "title": fields.get("contact_title", lead.contact_title),
                         "email": fields.get("contact_email", lead.contact_email), "phone": fields.get("contact_phone", lead.contact_phone)},
                        source.source_type)
    if cc["contact_email"] and cc["contact_email"] != lead.contact_email:
        if is_suppressed(session, email=cc["contact_email"]):
            raise MarketingError("suppressed", "Email ini ada di daftar jangan-hubungi")
        h = hash_value(cc["contact_email"])
        dup = session.scalar(select(Lead).where(Lead.email_hash == h, Lead.id != lead.id))
        if dup:
            raise MarketingError("duplicate_lead", "Prospek dengan email ini sudah ada", {"lead_id": dup.id})
        lead.email_hash = h
    for k, v in cc.items():
        setattr(lead, k, v)
    recompute_score(session, policy, lead)
    _audit(session, "lead.update", "lead", lead.id, actor, {"fields": sorted(fields)})
    return lead


# ------------------------------------------------------------------ tahap prospek (berdasarkan interaksi nyata)

def _interactions(session: Session, lead: Lead) -> list[LeadInteraction]:
    return list(session.scalars(select(LeadInteraction).where(LeadInteraction.lead_id == lead.id).order_by(LeadInteraction.occurred_at)))


def add_interaction(session: Session, lead: Lead, *, actor: str, kind: str, summary: str, occurred_at: datetime | None = None,
                    now: datetime | None = None) -> LeadInteraction:
    _human(actor)       # interaksi nyata hanya dicatat manusia; agent tidak dapat memalsukan bukti perpindahan tahap
    if lead.anonymized_at is not None:
        raise MarketingError("anonymized", "Data prospek sudah dianonimkan")
    if kind not in CONTACT_KINDS:
        raise MarketingError("invalid_kind", f"Jenis interaksi harus salah satu dari {CONTACT_KINDS}")
    if kind == "email_out" and lead.do_not_contact:
        raise MarketingError("do_not_contact", "Prospek menolak dihubungi; tidak boleh mencatat kontak keluar")
    summary = (summary or "").strip()
    if not summary or len(summary) > 4000:
        raise MarketingError("invalid_summary", "Ringkasan wajib diisi (maks. 4000 karakter)")
    assert_clean(summary=summary)
    now = now or utcnow()
    when = occurred_at or now
    if _naive(when) > _naive(now) + timedelta(minutes=5):
        raise PolicyError("occurred_in_future", "Waktu interaksi tidak boleh di masa depan")
    row = LeadInteraction(lead_id=lead.id, kind=kind, occurred_at=when, summary=summary, recorded_by=actor)
    session.add(row)
    if lead.last_interaction_at is None or _naive(when) > _naive(lead.last_interaction_at):
        lead.last_interaction_at = when
    session.flush()
    _audit(session, "lead.interaction", "lead", lead.id, actor, {"kind": kind})
    return row


def set_status(session: Session, policy: Policy, lead: Lead, new_status: str, *, actor: str, reason: str | None = None,
               override_reason: str | None = None) -> Lead:
    _human(actor)
    _lead_open(lead)
    if new_status not in SETTABLE_STATUSES:
        raise MarketingError("status_not_settable", "Status ini ditetapkan lewat konversi peluang atau opt-out, bukan diubah langsung")
    if new_status not in LEAD_TRANSITIONS.get(lead.status, set()):
        raise MarketingError("invalid_transition", f"Perpindahan {lead.status} -> {new_status} tidak diizinkan")
    kinds = {i.kind for i in _interactions(session, lead)}
    if new_status == "qualified":
        if (lead.score or 0) < policy.min_score_for_sales and len((override_reason or "").strip()) < 10:
            raise MarketingError("score_too_low", f"Skor {lead.score} di bawah batas {policy.min_score_for_sales}; berikan alasan pengecualian (min. 10 karakter)")
    if new_status == "contacted" and not kinds & {"email_out", "call", "meeting"}:
        raise MarketingError("evidence_required", "Status 'contacted' memerlukan minimal satu interaksi keluar nyata (email_out, call, atau meeting)")
    if new_status == "meeting" and "meeting" not in kinds:
        raise MarketingError("evidence_required", "Status 'meeting' memerlukan interaksi bertipe meeting yang sudah dicatat")
    if new_status == "disqualified" and len((reason or "").strip()) < 3:
        raise MarketingError("reason_required", "Alasan diskualifikasi wajib diisi")
    old = lead.status
    lead.status = new_status
    _audit(session, "lead.status", "lead", lead.id, actor, {"from": old, "to": new_status, "reason": reason, "override": bool(override_reason)})
    return lead


def forward_to_sales(session: Session, policy: Policy, lead: Lead, *, actor: str, override_reason: str | None = None,
                     now: datetime | None = None) -> Lead:
    """Teruskan prospek ke Sales & Client Relations. Syarat: provenance lengkap, tidak menolak dihubungi, dan lolos skor."""
    _human(actor)
    _lead_open(lead)
    if lead.status not in {"qualified", "contacted", "meeting"}:
        raise MarketingError("not_qualified", "Hanya prospek berstatus qualified, contacted, atau meeting yang dapat diteruskan ke Sales")
    src = session.get(LeadSource, lead.source_id)
    if src is None or not src.collected_by or not src.collected_at or (validate_source_type_safe(policy, src) is False):
        raise MarketingError("provenance_incomplete", "Provenance prospek tidak lengkap atau tidak lagi diizinkan")
    if (lead.score or 0) < policy.min_score_for_sales and len((override_reason or "").strip()) < 10:
        raise MarketingError("score_too_low", f"Skor {lead.score} di bawah batas {policy.min_score_for_sales}; berikan alasan pengecualian")
    if lead.contact_email and is_suppressed(session, email=lead.contact_email):
        raise MarketingError("suppressed", "Kontak ada di daftar jangan-hubungi")
    lead.owner, lead.forwarded_at = "sales_client_relations", now or utcnow()
    _audit(session, "lead.forwarded_to_sales", "lead", lead.id, actor, {"score": lead.score, "override": bool(override_reason)})
    return lead


def validate_source_type_safe(policy: Policy, src: LeadSource) -> bool:
    try:
        validate_source_type(policy, src.source_type)
        return True
    except PolicyError:
        return False


# ------------------------------------------------------------------ opt-out, penghapusan, retensi

def _anonymize(session: Session, lead: Lead, *, reason: str, now: datetime) -> None:
    lead.contact_name = lead.contact_title = lead.contact_email = lead.contact_phone = lead.email_hash = None
    lead.anonymized_at = now
    for i in _interactions(session, lead):
        i.summary = f"[dihapus: {reason}]"
    for o in session.scalars(select(OutreachRecord).where(OutreachRecord.lead_id == lead.id)):
        o.subject, o.body = "[dihapus]", f"[dihapus: {reason}]"
        if o.status in OUTREACH_OPEN:
            o.status = "cancelled"


def opt_out(session: Session, lead: Lead, *, actor: str, reason: str | None = None, now: datetime | None = None) -> Lead:
    _human(actor)
    if lead.contact_email:
        add_suppression(session, kind="email", value=lead.contact_email, reason="opt_out", actor=actor)
    lead.do_not_contact, lead.status = True, "do_not_contact"
    for o in session.scalars(select(OutreachRecord).where(OutreachRecord.lead_id == lead.id, OutreachRecord.status.in_(OUTREACH_OPEN))):
        o.status = "cancelled"
    _audit(session, "lead.opt_out", "lead", lead.id, actor, {"reason": reason})
    return lead


def erase(session: Session, lead: Lead, *, actor: str, reason: str | None = None, now: datetime | None = None) -> Lead:
    """Penghapusan atas permintaan subjek data: anonimkan seketika dan daftarkan ke jangan-hubungi agar tidak terkumpul lagi."""
    _human(actor)
    now = now or utcnow()
    if lead.contact_email:
        add_suppression(session, kind="email", value=lead.contact_email, reason="erasure", actor=actor)
    _anonymize(session, lead, reason="permintaan penghapusan", now=now)
    lead.do_not_contact, lead.status = True, "do_not_contact"
    _audit(session, "lead.erase", "lead", lead.id, actor, {"reason": reason})
    return lead


def _has_pii(lead: Lead) -> bool:
    return any([lead.contact_name, lead.contact_title, lead.contact_email, lead.contact_phone])


def retention_due(session: Session, policy: Policy, now: datetime | None = None) -> list[dict]:
    """Prospek yang data pribadinya sudah melewati masa simpan. Prospek dengan peluang yang masih terbuka dikecualikan."""
    now = _naive(now or utcnow())
    open_leads = {o.lead_id for o in session.scalars(select(SalesOpportunity).where(SalesOpportunity.stage.in_(OPEN_STAGES)))}
    out = []
    for lead in session.scalars(select(Lead).where(Lead.anonymized_at.is_(None))).all():
        if not _has_pii(lead) or lead.id in open_leads:
            continue
        if lead.last_interaction_at is None:
            age, limit, why = (now - _naive(lead.collected_at)).days, policy.retention_no_interaction_days, "tanpa interaksi sejak dikumpulkan"
        else:
            age, limit, why = (now - _naive(lead.last_interaction_at)).days, policy.retention_after_interaction_days, "tanpa interaksi sejak interaksi terakhir"
        if age >= limit:
            out.append({"lead_id": lead.id, "age_days": age, "limit_days": limit, "reason": f"{why} ({age} hari, batas {limit})"})
    return out


def apply_retention(session: Session, policy: Policy, *, actor: str, now: datetime | None = None) -> int:
    _human(actor)
    now = now or utcnow()
    due = retention_due(session, policy, now)
    for d in due:
        _anonymize(session, session.get(Lead, d["lead_id"]), reason="retensi data", now=now)
    _audit(session, "retention.apply", "retention", "sweep", actor, {"anonymized": len(due)})
    return len(due)


# ------------------------------------------------------------------ akses data pribadi

def pii_for_actor(session: Session, lead: Lead, actor: str) -> dict:
    """Kontak lengkap hanya untuk pelaku yang berwenang; setiap pembacaan tercatat di audit."""
    access.require(actor, "lead.read_pii")
    _audit(session, "lead.pii_viewed", "lead", lead.id, actor, {})
    return {"name": lead.contact_name, "title": lead.contact_title, "email": lead.contact_email, "phone": lead.contact_phone}


# ------------------------------------------------------------------ peluang penjualan

def convert_to_opportunity(session: Session, lead: Lead, *, actor: str, title: str, value_estimate_idr: int | None = None,
                           summary: str | None = None) -> SalesOpportunity:
    _human(actor)
    _lead_open(lead)
    if lead.status not in {"qualified", "contacted", "meeting"}:
        raise MarketingError("not_qualified", "Hanya prospek qualified, contacted, atau meeting yang dapat dikonversi")
    if not (title or "").strip():
        raise MarketingError("title_required", "Judul peluang wajib diisi")
    if value_estimate_idr is not None and value_estimate_idr < 0:
        raise MarketingError("invalid_value", "Estimasi nilai tidak boleh negatif")
    assert_clean(title=title, summary=summary)
    opp = SalesOpportunity(lead_id=lead.id, title=title.strip(), value_estimate_idr=value_estimate_idr, summary=summary, created_by=actor)
    session.add(opp)
    lead.status = "opportunity"
    session.flush()
    _audit(session, "opportunity.create", "sales_opportunity", opp.id, actor, {"lead_id": lead.id})
    return opp


def set_opportunity_stage(session: Session, opp: SalesOpportunity, stage: str, *, actor: str, reason: str | None = None,
                          won_value_idr: int | None = None, now: datetime | None = None) -> SalesOpportunity:
    _human(actor)
    if stage not in OPP_STAGES:
        raise MarketingError("invalid_stage", f"Tahap harus salah satu dari {OPP_STAGES}")
    if stage not in OPP_TRANSITIONS[opp.stage]:
        raise MarketingError("invalid_transition", f"Perpindahan tahap {opp.stage} -> {stage} tidak diizinkan")
    if stage in {"won", "lost"}:
        if len((reason or "").strip()) < 5:
            raise MarketingError("reason_required", "Alasan menang atau kalah wajib dicatat (min. 5 karakter)")
        assert_clean(reason=reason)
    if stage == "won":
        if won_value_idr is None or won_value_idr < 0:
            raise MarketingError("won_value_required", "Nilai kontrak aktual wajib dicatat saat menang")
        opp.won_value_idr = won_value_idr
    old = opp.stage
    opp.stage = stage
    if stage in {"won", "lost"}:
        opp.outcome_reason, opp.closed_at = reason.strip(), now or utcnow()
        lead = session.get(Lead, opp.lead_id)
        lead.status = stage
    _audit(session, "opportunity.stage", "sales_opportunity", opp.id, actor, {"from": old, "to": stage})
    return opp


def add_requirement(session: Session, opp: SalesOpportunity, *, actor: str, text: str, priority: str = "normal") -> ClientRequirement:
    access.require(actor, "requirement.write")
    text = (text or "").strip()
    if not text or len(text) > 4000:
        raise MarketingError("invalid_text", "Kebutuhan wajib diisi (maks. 4000 karakter)")
    if priority not in {"low", "normal", "high"}:
        raise MarketingError("invalid_priority", "Prioritas harus low, normal, atau high")
    assert_clean(requirement=text)
    req = ClientRequirement(opportunity_id=opp.id, text=text, priority=priority, recorded_by=actor)
    session.add(req)
    session.flush()
    return req


# ------------------------------------------------------------------ outreach (draf; belum ada konektor kirim)

def create_outreach(session: Session, lead: Lead, *, actor: str, product_id: str | None, version_id: str | None, channel: str, subject: str,
                    body: str, status: str, claim_check: dict | None, task_id: str | None) -> OutreachRecord:
    access.require(actor, "outreach.draft")
    row = OutreachRecord(lead_id=lead.id, product_id=product_id, version_id=version_id, task_id=task_id, channel=channel, subject=subject,
                         body=body, status=status, claim_check=claim_check, created_by=actor)
    session.add(row)
    session.flush()
    _audit(session, "outreach.draft", "outreach", row.id, actor, {"lead_id": lead.id, "status": status})
    return row


def mark_outreach_sent(session: Session, outreach: OutreachRecord, *, actor: str, note: str | None = None, now: datetime | None = None) -> OutreachRecord:
    """CEO mencatat bahwa ia mengirim sendiri. Belum ada konektor otomatis; pengiriman otomatis tetap memerlukan approval (Phase 9)."""
    _human(actor)
    lead = session.get(Lead, outreach.lead_id)
    _lead_open(lead)
    if outreach.status != "ready_for_review":
        raise MarketingError("not_ready", f"Draf berstatus {outreach.status}; hanya yang lolos pemeriksaan klaim yang dapat dicatat terkirim")
    if lead.contact_email and is_suppressed(session, email=lead.contact_email):
        raise MarketingError("suppressed", "Kontak ada di daftar jangan-hubungi")
    now = now or utcnow()
    outreach.status, outreach.sent_at, outreach.sent_note = "sent_manual", now, note
    add_interaction(session, lead, actor=actor, kind="email_out", summary=f"Outreach dikirim manual: {outreach.subject}", occurred_at=now, now=now)
    _audit(session, "outreach.sent_manual", "outreach", outreach.id, actor, {"lead_id": lead.id})
    return outreach


def cancel_outreach(session: Session, outreach: OutreachRecord, *, actor: str) -> OutreachRecord:
    _human(actor)
    if outreach.status not in OUTREACH_OPEN:
        raise MarketingError("not_open", f"Draf berstatus {outreach.status} tidak dapat dibatalkan")
    outreach.status = "cancelled"
    _audit(session, "outreach.cancel", "outreach", outreach.id, actor, {})
    return outreach


# ------------------------------------------------------------------ metrik (Bagian 17.2): tidak mengarang data

def analytics(session: Session, now: datetime | None = None) -> dict:
    """Nilai None berarti BELUM DIKETAHUI (bukan nol): mis. win rate tanpa peluang tertutup."""
    leads = list(session.scalars(select(Lead)))
    opps = list(session.scalars(select(SalesOpportunity)))
    by_status: dict[str, int] = {}
    for l in leads:
        by_status[l.status] = by_status.get(l.status, 0) + 1
    sources = {s.id: s.source_type for s in session.scalars(select(LeadSource))}
    by_source: dict[str, int] = {}
    for l in leads:
        by_source[sources.get(l.source_id, "?")] = by_source.get(sources.get(l.source_id, "?"), 0) + 1
    won = [o for o in opps if o.stage == "won"]
    lost = [o for o in opps if o.stage == "lost"]
    met = {i.lead_id for i in session.scalars(select(LeadInteraction).where(LeadInteraction.kind == "meeting"))}
    first: dict[str, datetime] = {}
    for i in session.scalars(select(LeadInteraction).order_by(LeadInteraction.occurred_at)):
        first.setdefault(i.lead_id, i.occurred_at)
    lead_by_id = {l.id: l for l in leads}
    delays = [(_naive(first[lid]) - _naive(lead_by_id[lid].collected_at)).total_seconds() / 3600 for lid in first if lid in lead_by_id]
    ratio = lambda a, b: round(a / b, 4) if b else None  # noqa: E731
    return {
        "leads_total": len(leads), "by_status": by_status, "by_source": by_source,
        "qualified_leads": sum(1 for l in leads if (l.score or 0) >= 1 and l.status not in {"new", "disqualified", "do_not_contact"}),
        "lead_to_meeting_rate": ratio(len(met), len(leads)),
        "opportunity_conversion_rate": ratio(len(opps), len(leads)),
        "opportunities_open": sum(1 for o in opps if o.stage in OPEN_STAGES),
        "win_rate": ratio(len(won), len(won) + len(lost)),
        "revenue_recorded_idr": sum(o.won_value_idr or 0 for o in won) if won else None,
        "avg_hours_to_first_interaction": round(sum(delays) / len(delays), 1) if delays else None,
        "customer_acquisition_cost_idr": None,      # data biaya dan atribusi belum tersedia
        "campaign_roi": None,
        "notes": ["Nilai null berarti belum diketahui, bukan nol", "CAC dan ROI belum dihitung karena data biaya dan atribusi belum ada"],
    }
