from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.base import utcnow
from app.db.models import AuditLog, Lead, LeadInteraction, OutreachRecord, SuppressionEntry
from app.db.session import create_db_engine, create_session_factory
from app.marketing import access, service
from app.marketing.access import AccessDenied
from app.marketing.policy import Policy, validate_source_type, validate_url
from app.marketing.privacy import (
    PolicyError, assert_clean, hash_value, is_consumer_email, mask_email, normalize_company_name, normalize_domain, normalize_email,
    normalize_phone, scan_sensitive,
)
from app.marketing.scoring import score_lead
from tests.conftest import TOKEN

POLICY = Policy.from_settings(Settings(_env_file=None, app_local_token=TOKEN))


@pytest.fixture
def s(migrated_db):
    sf = create_session_factory(create_db_engine(migrated_db))
    with sf() as session:
        yield session


def mk(s, name="PT Maju Jaya", email="budi@majujaya.co.id", source="public_website", url="https://majujaya.co.id/kontak", actor="ceo",
       contact_name="Budi Santoso", title="Direktur", **company):
    src = {"source_type": source, "url": url if source.startswith("public") else None}
    return service.create_lead(s, POLICY, actor=actor, company={"name": name, "industry": "ritel", "size_band": "small", **company},
                               contact={"name": contact_name, "title": title, "email": email, "phone": "+62 812 3456 7890"}, source=src)


# ---------------------------------------------------------------- privasi

@pytest.mark.parametrize("text", ["NIK 3174012345678901", "alamat rumah di Jl. Mawar", "agama Islam", "kartu 4539 1488 0343 6467",
                                  "NPWP 12.345.678.9-012.345", "tanggal lahir 1 Januari"])
def test_sensitive_data_is_detected(text):
    assert scan_sensitive(text)
    with pytest.raises(PolicyError) as e:
        assert_clean(note=text)
    assert e.value.code == "sensitive_data" and text not in e.value.message      # pesan tidak membocorkan isi


def test_clean_business_text_passes():
    assert scan_sensitive("Toko ritel di Bandung, 20 karyawan, butuh sistem kasir") == []


def test_normalizers():
    assert normalize_email(" Budi@Maju.CO.ID ") == "budi@maju.co.id" and normalize_email("") is None
    with pytest.raises(PolicyError):
        normalize_email("bukan-email")
    assert normalize_phone("+62 812-3456-7890") == "+6281234567890"
    with pytest.raises(PolicyError):
        normalize_phone("123")
    assert normalize_domain("https://www.Maju.co.id/kontak?x=1") == "maju.co.id"
    assert normalize_company_name("PT. Maju Jaya Tbk") == normalize_company_name("maju jaya")
    assert hash_value(" A@B.com ") == hash_value("a@b.com")
    assert mask_email("budi@maju.id") == "b***@maju.id" and is_consumer_email("x@gmail.com") and not is_consumer_email("x@maju.id")


# ---------------------------------------------------------------- kebijakan sumber

def test_source_policy():
    assert validate_source_type(POLICY, "referral")["basis"] == "legitimate_interest_b2b"
    for bad in ("purchased_list", "social_media_scraping", "leaked_data", "private_group"):
        with pytest.raises(PolicyError) as e:
            validate_source_type(POLICY, bad)
        assert e.value.code == "source_forbidden"
    with pytest.raises(PolicyError) as e:
        validate_source_type(POLICY, "teleportasi")
    assert e.value.code == "source_unknown"
    narrowed = Policy.from_settings(Settings(_env_file=None, app_local_token=TOKEN, lead_allowed_sources="manual"))
    with pytest.raises(PolicyError) as e:
        validate_source_type(narrowed, "referral")
    assert e.value.code == "source_not_allowed"


@pytest.mark.parametrize("url", ["ftp://x.com", "http://localhost/a", "http://127.0.0.1/a", "http://intranet/a", "https://a.com/x y", "javascript:alert(1)"])
def test_invalid_urls_rejected(url):
    with pytest.raises(PolicyError):
        validate_url(url, True)


def test_public_source_requires_url_and_traceability(s):
    with pytest.raises(PolicyError) as e:
        mk(s, url=None)
    assert e.value.code == "source_url_required"
    lead = mk(s)
    src = s.get(service.LeadSource, lead.source_id)
    assert (src.source_type, src.url, src.collected_by, lead.basis) == ("public_website", "https://majujaya.co.id/kontak", "ceo", "legitimate_interest_b2b")


# ---------------------------------------------------------------- akses

def test_access_matrix():
    assert access.allowed("ceo", "anything")
    assert access.allowed("sales_client_relations", "lead.read_pii")
    for role in ("lead_generation", "market_research", "content_promotion", "manager", "developer", "unknown"):
        assert not access.allowed(role, "lead.read_pii")
    assert not access.allowed("market_research", "lead.create") and not access.allowed("sales_client_relations", "lead.create")
    with pytest.raises(AccessDenied):
        access.require("market_research", "lead.read_masked")


def test_agents_cannot_make_human_decisions(s):
    lead = mk(s)
    for actor in ("lead_generation", "sales_client_relations", "manager", "reviewer"):
        for fn in (lambda a: service.set_status(s, POLICY, lead, "qualified", actor=a, override_reason="alasan cukup panjang"),
                   lambda a: service.add_interaction(s, lead, actor=a, kind="meeting", summary="x"),
                   lambda a: service.forward_to_sales(s, POLICY, lead, actor=a), lambda a: service.opt_out(s, lead, actor=a),
                   lambda a: service.erase(s, lead, actor=a), lambda a: service.convert_to_opportunity(s, lead, actor=a, title="x")):
            with pytest.raises(AccessDenied):
                fn(actor)
    assert lead.status == "new"


def test_only_sales_and_ceo_read_pii_and_it_is_audited(s):
    lead = mk(s)
    with pytest.raises(AccessDenied):
        service.pii_for_actor(s, lead, "market_research")
    assert service.pii_for_actor(s, lead, "sales_client_relations")["email"] == "budi@majujaya.co.id"
    s.commit()
    rows = s.scalars(select(AuditLog).where(AuditLog.action == "lead.pii_viewed")).all()
    assert len(rows) == 1 and "budi" not in str(rows[0].details)


def test_audit_never_contains_pii(s):
    lead = mk(s)
    service.opt_out(s, lead, actor="ceo")
    s.commit()
    blob = " ".join(str(a.details) + a.entity_id for a in s.scalars(select(AuditLog)))
    assert "budi" not in blob.lower() and "majujaya.co.id" not in blob and "812" not in blob


# ---------------------------------------------------------------- pembuatan prospek

def test_personal_email_only_allowed_for_inbound(s):
    with pytest.raises(PolicyError) as e:
        mk(s, email="budi@gmail.com", name="PT A")
    assert e.value.code == "personal_email_not_allowed"
    lead = service.create_lead(s, POLICY, actor="ceo", company={"name": "PT B"}, contact={"email": "ani@gmail.com"}, source={"source_type": "inbound"})
    assert lead.basis == "inbound_inquiry"


def test_sensitive_data_blocked_in_every_free_text_field(s):
    with pytest.raises(PolicyError):
        mk(s, name="PT Z", contact_name="Budi NIK 3174012345678901")
    with pytest.raises(PolicyError):
        mk(s, name="PT Z", description="pemilik beragama Islam, agama tidak relevan")
    with pytest.raises(PolicyError):
        service.create_source(s, POLICY, actor="ceo", source_type="manual", note="alamat rumah pemilik")


def test_dedupe_by_email_and_by_company_contact(s):
    first = mk(s)
    with pytest.raises(service.MarketingError) as e:
        mk(s, name="Lain", email="BUDI@majujaya.co.id")
    assert e.value.code == "duplicate_lead" and e.value.details["lead_id"] == first.id
    with pytest.raises(service.MarketingError):
        mk(s, name="PT. Maju Jaya", email="b2@majujaya.co.id")           # nama kontak sama pada perusahaan yang sama
    other = mk(s, name="PT Maju Jaya", email="siti@majujaya.co.id", contact_name="Siti")
    assert other.company_id == first.company_id                          # perusahaan tidak digandakan


def test_opt_out_blocks_recollection(s):
    lead = mk(s)
    service.opt_out(s, lead, actor="ceo", reason="minta berhenti")
    assert lead.do_not_contact and lead.status == "do_not_contact"
    with pytest.raises(service.MarketingError) as e:
        mk(s, name="PT Baru", email="budi@majujaya.co.id", contact_name="Budi Lagi")
    assert e.value.code == "suppressed"
    entry = s.scalar(select(SuppressionEntry))
    assert entry.value_hash == hash_value("budi@majujaya.co.id") and "budi" not in repr(entry.__dict__).replace("budi@majujaya.co.id".encode().hex(), "")
    with pytest.raises(service.MarketingError):
        service.add_interaction(s, lead, actor="ceo", kind="email_out", summary="kirim lagi")
    with pytest.raises(service.MarketingError):
        service.set_status(s, POLICY, lead, "qualified", actor="ceo", override_reason="alasan yang panjang")


def test_domain_suppression(s):
    service.add_suppression(s, kind="domain", value="https://www.blocked.co.id", reason="complaint", actor="ceo")
    with pytest.raises(service.MarketingError) as e:
        mk(s, name="PT Blocked", email="a@blocked.co.id")
    assert e.value.code == "suppressed"


# ---------------------------------------------------------------- skor

def test_score_is_deterministic_and_explained():
    comp = {"name": "PT Kasir", "industry": "ritel toko", "size_band": "small", "city": "Bandung", "website": "https://a.co.id", "description": "toko ritel", "domain": "a.co.id"}
    lead = {"contact_name": "Budi", "contact_title": "Direktur", "contact_email": "b@a.co.id", "contact_phone": "+62811111111", "collected_at": utcnow()}
    prod = {"target_customers": "toko ritel kecil", "description": "sistem kasir"}
    a = score_lead(company=comp, lead=lead, source_type="referral", product=prod, now=utcnow())
    b = score_lead(company=comp, lead=lead, source_type="referral", product=prod, now=lead["collected_at"])
    assert a[0] == b[0] and 0 <= a[0] <= 100 and all({"factor", "points", "max", "note"} <= set(r) for r in a[1])
    assert sum(r["points"] for r in a[1]) == a[0] and all(r["points"] <= r["max"] for r in a[1])
    bare = score_lead(company={"name": "X"}, lead={"collected_at": utcnow() - timedelta(days=400)}, source_type="manual", product=None, now=utcnow())
    assert bare[0] < a[0] / 2


# ---------------------------------------------------------------- tahap prospek butuh bukti

def test_status_machine_requires_real_evidence(s):
    lead = mk(s)
    assert lead.score >= POLICY.min_score_for_sales
    with pytest.raises(service.MarketingError) as e:
        service.set_status(s, POLICY, lead, "contacted", actor="ceo")
    assert e.value.code == "invalid_transition"
    service.set_status(s, POLICY, lead, "qualified", actor="ceo")
    with pytest.raises(service.MarketingError) as e:
        service.set_status(s, POLICY, lead, "contacted", actor="ceo")
    assert e.value.code == "evidence_required"
    service.add_interaction(s, lead, actor="ceo", kind="note", summary="catatan saja")
    with pytest.raises(service.MarketingError):
        service.set_status(s, POLICY, lead, "contacted", actor="ceo")          # catatan bukan kontak keluar
    service.add_interaction(s, lead, actor="ceo", kind="call", summary="menelepon")
    service.set_status(s, POLICY, lead, "contacted", actor="ceo")
    with pytest.raises(service.MarketingError) as e:
        service.set_status(s, POLICY, lead, "meeting", actor="ceo")
    assert e.value.code == "evidence_required"
    service.add_interaction(s, lead, actor="ceo", kind="meeting", summary="bertemu")
    service.set_status(s, POLICY, lead, "meeting", actor="ceo")
    for bad in ("won", "lost", "do_not_contact", "opportunity"):
        with pytest.raises(service.MarketingError) as e:
            service.set_status(s, POLICY, lead, bad, actor="ceo")
        assert e.value.code == "status_not_settable"


def test_low_score_needs_override_and_disqualify_needs_reason(s):
    lead = service.create_lead(s, POLICY, actor="ceo", company={"name": "PT Kecil"}, contact=None, source={"source_type": "manual"})
    lead.collected_at = utcnow() - timedelta(days=400)
    service.recompute_score(s, POLICY, lead)
    assert lead.score < POLICY.min_score_for_sales
    with pytest.raises(service.MarketingError) as e:
        service.set_status(s, POLICY, lead, "qualified", actor="ceo")
    assert e.value.code == "score_too_low"
    with pytest.raises(service.MarketingError):
        service.set_status(s, POLICY, lead, "qualified", actor="ceo", override_reason="pendek")
    service.set_status(s, POLICY, lead, "qualified", actor="ceo", override_reason="kenalan lama, relevan")
    with pytest.raises(service.MarketingError) as e:
        service.set_status(s, POLICY, lead, "disqualified", actor="ceo")
    assert e.value.code == "reason_required"
    service.set_status(s, POLICY, lead, "disqualified", actor="ceo", reason="tidak butuh")
    assert lead.status == "disqualified"


def test_interaction_rules(s):
    lead = mk(s)
    with pytest.raises(service.MarketingError):
        service.add_interaction(s, lead, actor="ceo", kind="fax", summary="x")
    with pytest.raises(service.MarketingError):
        service.add_interaction(s, lead, actor="ceo", kind="note", summary="  ")
    with pytest.raises(PolicyError):
        service.add_interaction(s, lead, actor="ceo", kind="note", summary="NIK 3174012345678901")
    with pytest.raises(PolicyError):
        service.add_interaction(s, lead, actor="ceo", kind="note", summary="x", occurred_at=utcnow() + timedelta(days=2))
    i = service.add_interaction(s, lead, actor="ceo", kind="email_in", summary="balasan")
    assert lead.last_interaction_at == i.occurred_at


# ---------------------------------------------------------------- teruskan ke Sales

def test_forward_to_sales_rules(s):
    lead = mk(s)
    with pytest.raises(service.MarketingError) as e:
        service.forward_to_sales(s, POLICY, lead, actor="ceo")
    assert e.value.code == "not_qualified"
    service.set_status(s, POLICY, lead, "qualified", actor="ceo")
    service.forward_to_sales(s, POLICY, lead, actor="ceo")
    assert lead.owner == "sales_client_relations" and lead.forwarded_at is not None
    narrowed = Policy.from_settings(Settings(_env_file=None, app_local_token=TOKEN, lead_allowed_sources="manual"))
    with pytest.raises(service.MarketingError) as e:
        service.forward_to_sales(s, narrowed, lead, actor="ceo")           # sumber tidak lagi diizinkan
    assert e.value.code == "provenance_incomplete"


def test_forward_blocked_when_suppressed_after_collection(s):
    lead = mk(s)
    service.set_status(s, POLICY, lead, "qualified", actor="ceo")
    service.add_suppression(s, kind="email", value=lead.contact_email, reason="complaint", actor="ceo")
    with pytest.raises(service.MarketingError) as e:
        service.forward_to_sales(s, POLICY, lead, actor="ceo")
    assert e.value.code == "suppressed"


# ---------------------------------------------------------------- peluang

def test_opportunity_flow(s):
    lead = mk(s)
    with pytest.raises(service.MarketingError):
        service.convert_to_opportunity(s, lead, actor="ceo", title="x")        # belum qualified
    service.set_status(s, POLICY, lead, "qualified", actor="ceo")
    opp = service.convert_to_opportunity(s, lead, actor="ceo", title="Sistem kasir", value_estimate_idr=5_000_000)
    assert lead.status == "opportunity" and opp.stage == "qualification"
    with pytest.raises(service.MarketingError):
        service.set_opportunity_stage(s, opp, "won", actor="ceo", reason="deal", won_value_idr=1)   # lompat tahap
    service.set_opportunity_stage(s, opp, "proposal", actor="ceo")
    with pytest.raises(service.MarketingError) as e:
        service.set_opportunity_stage(s, opp, "won", actor="ceo", won_value_idr=1000)
    assert e.value.code == "reason_required"
    with pytest.raises(service.MarketingError) as e:
        service.set_opportunity_stage(s, opp, "won", actor="ceo", reason="setuju harga")
    assert e.value.code == "won_value_required"
    service.set_opportunity_stage(s, opp, "won", actor="ceo", reason="setuju harga", won_value_idr=4_500_000)
    assert lead.status == "won" and opp.closed_at is not None and opp.won_value_idr == 4_500_000
    with pytest.raises(service.MarketingError):
        service.set_opportunity_stage(s, opp, "lost", actor="ceo", reason="batal ya")     # tahap akhir tidak dapat diubah
    with pytest.raises(AccessDenied):
        service.add_requirement(s, opp, actor="lead_generation", text="x")
    assert service.add_requirement(s, opp, actor="sales_client_relations", text="butuh laporan harian").priority == "normal"


# ---------------------------------------------------------------- retensi dan penghapusan

def test_retention_anonymizes_only_what_is_due_and_protects_open_opportunities(s):
    old = mk(s, name="PT Lama", email="a@lama.co.id", contact_name="Ani")
    old.collected_at = utcnow() - timedelta(days=POLICY.retention_no_interaction_days + 5)
    fresh = mk(s, name="PT Baru", email="b@baru.co.id", contact_name="Bimo")
    active = mk(s, name="PT Aktif", email="c@aktif.co.id", contact_name="Cici")
    active.collected_at = old.collected_at
    service.set_status(s, POLICY, active, "qualified", actor="ceo", override_reason="alasan pengecualian")
    service.convert_to_opportunity(s, active, actor="ceo", title="Proyek")
    interacted = mk(s, name="PT Pernah", email="d@pernah.co.id", contact_name="Dedi")
    service.add_interaction(s, interacted, actor="ceo", kind="note", summary="rahasia pembicaraan", occurred_at=utcnow() - timedelta(days=400))
    interacted.collected_at = old.collected_at
    due = {d["lead_id"] for d in service.retention_due(s, POLICY)}
    assert due == {old.id}                       # yang punya interaksi memakai batas lebih panjang
    assert service.apply_retention(s, POLICY, actor="ceo") == 1
    assert old.anonymized_at and old.contact_email is None and old.contact_name is None and old.email_hash is None
    assert fresh.contact_email and active.contact_email
    later = utcnow() + timedelta(days=POLICY.retention_after_interaction_days)
    assert {d["lead_id"] for d in service.retention_due(s, POLICY, later)} == {fresh.id, interacted.id}   # peluang terbuka tetap dilindungi
    with pytest.raises(AccessDenied):
        service.apply_retention(s, POLICY, actor="lead_generation")


def test_erase_wipes_pii_everywhere_and_blocks_recollection(s):
    lead = mk(s)
    service.add_interaction(s, lead, actor="ceo", kind="note", summary="isi pembicaraan pribadi")
    s.add(OutreachRecord(lead_id=lead.id, subject="Halo Budi", body="isi email", status="ready_for_review"))
    s.flush()
    service.erase(s, lead, actor="ceo", reason="permintaan subjek data")
    s.commit()
    assert lead.anonymized_at and lead.contact_name is None and lead.contact_phone is None and lead.do_not_contact
    assert all("pembicaraan" not in i.summary for i in s.scalars(select(LeadInteraction)))
    o = s.scalar(select(OutreachRecord))
    assert o.status == "cancelled" and "Budi" not in o.subject and "isi email" not in o.body
    with pytest.raises(service.MarketingError) as e:
        mk(s, name="PT Lain", email="budi@majujaya.co.id", contact_name="Budi Lagi")
    assert e.value.code == "suppressed"
    with pytest.raises(service.MarketingError):
        service.add_interaction(s, lead, actor="ceo", kind="note", summary="x")


# ---------------------------------------------------------------- outreach manual dan analitik

def test_mark_sent_requires_ready_draft_and_records_real_interaction(s):
    lead = mk(s)
    service.set_status(s, POLICY, lead, "qualified", actor="ceo")
    blocked = service.create_outreach(s, lead, actor="sales_client_relations", product_id=None, version_id=None, channel="email", subject="a", body="b",
                                      status="blocked_by_claim_check", claim_check={}, task_id=None)
    with pytest.raises(service.MarketingError) as e:
        service.mark_outreach_sent(s, blocked, actor="ceo")
    assert e.value.code == "not_ready"
    ready = service.create_outreach(s, lead, actor="sales_client_relations", product_id=None, version_id=None, channel="email", subject="Halo", body="isi",
                                    status="ready_for_review", claim_check={"ok": True}, task_id=None)
    with pytest.raises(AccessDenied):
        service.mark_outreach_sent(s, ready, actor="sales_client_relations")
    service.mark_outreach_sent(s, ready, actor="ceo", note="dikirim lewat Gmail")
    assert ready.status == "sent_manual"
    service.set_status(s, POLICY, lead, "contacted", actor="ceo")          # kini bukti nyata ada
    with pytest.raises(AccessDenied):
        service.create_outreach(s, lead, actor="market_research", product_id=None, version_id=None, channel="email", subject="a", body="b",
                                status="draft", claim_check=None, task_id=None)


def test_analytics_reports_unknown_as_null(s):
    a = service.analytics(s)
    assert a["leads_total"] == 0 and a["win_rate"] is None and a["revenue_recorded_idr"] is None and a["avg_hours_to_first_interaction"] is None
    assert a["customer_acquisition_cost_idr"] is None and a["campaign_roi"] is None
    lead = mk(s)
    service.set_status(s, POLICY, lead, "qualified", actor="ceo")
    opp = service.convert_to_opportunity(s, lead, actor="ceo", title="P")
    service.set_opportunity_stage(s, opp, "lost", actor="ceo", reason="tidak ada anggaran")
    a = service.analytics(s)
    assert a["leads_total"] == 1 and a["win_rate"] == 0.0 and a["by_source"] == {"public_website": 1} and a["revenue_recorded_idr"] is None


def test_forward_requires_score_or_override(s):
    lead = service.create_lead(s, POLICY, actor="ceo", company={"name": "PT Kecil"}, contact=None, source={"source_type": "manual"})
    lead.collected_at = utcnow() - timedelta(days=400)
    service.recompute_score(s, POLICY, lead)
    service.set_status(s, POLICY, lead, "qualified", actor="ceo", override_reason="kenalan lama, relevan")
    with pytest.raises(service.MarketingError) as e:
        service.forward_to_sales(s, POLICY, lead, actor="ceo")
    assert e.value.code == "score_too_low"
    service.forward_to_sales(s, POLICY, lead, actor="ceo", override_reason="CEO mengenal langsung")
    assert lead.forwarded_at is not None
