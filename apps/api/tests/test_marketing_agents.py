import json

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.models import AuditLog, Lead, MarketResearch, OutreachRecord, Product
from app.marketing import agents, service
from app.marketing.agents import OPT_OUT_FOOTER, ground_candidate, ground_research, in_material, Candidate, ResearchItem
from app.marketing.policy import Policy
from app.tasks.executors import default_executors
from tests.conftest import TOKEN
from tests.fakes import FakeProvider
from tests.helpers import add_task, build_env, drain, get, make_project

POLICY = Policy.from_settings(Settings(_env_file=None, app_local_token=TOKEN))
RAW = ("Daftar peserta pameran UMKM Bandung.\n"
       "PT Sinar Kasir Nusantara, toko ritel di Bandung, hubungi Rina Wijaya (Direktur) di rina@sinarkasir.co.id atau +62 811 2233 4455.\n"
       "CV Warung Digital menjual sembako; kontak ani@gmail.com.\n"
       "PT Blokir Abadi, kontak Joko di joko@blokir.co.id.\n")


def cand(**kw):
    base = {"company_name": "PT Sinar Kasir Nusantara", "industry": "ritel", "city": "Bandung", "website": "", "size_band": "small",
            "contact_name": "Rina Wijaya", "contact_title": "Direktur", "contact_email": "rina@sinarkasir.co.id",
            "contact_phone": "+62 811 2233 4455", "evidence_quote": "PT Sinar Kasir Nusantara, toko ritel di Bandung"}
    return base | kw


def reply(*cands):
    return json.dumps({"candidates": list(cands)})


def env_with(migrated_db, tmp_path, *replies):
    return build_env(migrated_db, tmp_path, provider=FakeProvider(reply=list(replies)), executors=default_executors())


def intake(env, pid, raw=RAW, source=None, **kw):
    params = {"source": source or {"source_type": "event", "title": "Pameran UMKM"}, "raw_text": raw}
    return add_task(env, pid, role="lead_generation", action_type="lead_intake", params=params, **kw)


# ---------------------------------------------------------------- pembumian (grounding)

def test_in_material_normalizes_whitespace_and_case():
    assert in_material("PT  Sinar\nKasir", RAW) and not in_material("PT Tidak Ada", RAW) and not in_material("ab", RAW)


def test_candidate_grounding_rejects_fabricated_company_and_drops_fabricated_fields():
    assert ground_candidate(Candidate(**cand()), RAW) == (None, Candidate(**cand()), [])
    for patch, why in [({"company_name": "PT Karangan"}, "nama perusahaan"), ({"evidence_quote": "kalimat palsu"}, "kutipan")]:
        assert why in ground_candidate(Candidate(**cand(**patch)), RAW)[0]
    for field, bad in [("contact_email", "palsu@sinarkasir.co.id"), ("contact_phone", "+62 899 0000 1111"), ("contact_name", "Orang Fiktif"),
                       ("contact_title", "Presiden Galaksi"), ("website", "https://karangan.example.com")]:
        why, clean, dropped = ground_candidate(Candidate(**cand(**{field: bad})), RAW)
        assert why is None and getattr(clean, field) == "" and dropped == [field]          # fakta karangan tidak pernah disimpan
        assert clean.company_name == "PT Sinar Kasir Nusantara" and clean.contact_email in ("", "rina@sinarkasir.co.id")


def test_research_grounding_downgrades_unsupported_claims():
    items = [ResearchItem(statement="Ada toko ritel di Bandung", basis="provided_material", evidence_quote="toko ritel di Bandung"),
             ResearchItem(statement="Pasar tumbuh 40%", basis="provided_material", evidence_quote="pasar tumbuh 40 persen"),
             ResearchItem(statement="Dugaan", basis="assumption", evidence_quote=""),
             ResearchItem(statement="Semua toko ritel memakai sistem kasir cloud berlangganan", basis="provided_material", evidence_quote="toko ritel di Bandung"),
             ResearchItem(statement="Fitur X", basis="product_catalog", evidence_quote="fitur x")]
    out = ground_research(items, RAW, "Sistem Kasir\nfitur kasir offline")
    assert [o["verified"] for o in out] == [True, False, False, False, False]
    assert out[1]["basis"] == "assumption" and out[1]["claimed_basis"] == "provided_material" and out[1]["evidence_quote"] == ""


# ---------------------------------------------------------------- Lead Intake

def test_intake_creates_only_grounded_policy_compliant_leads(migrated_db, tmp_path):
    env = env_with(migrated_db, tmp_path, reply(
        cand(),
        cand(company_name="PT Karangan Fiktif", evidence_quote="PT Karangan Fiktif bergerak di ritel"),          # tidak ada di materi
        cand(company_name="CV Warung Digital", contact_name="", contact_title="", contact_phone="", contact_email="ani@gmail.com",
             evidence_quote="CV Warung Digital menjual sembako"),                                           # email pribadi + sumber event
        cand(company_name="PT Blokir Abadi", contact_name="Joko", contact_title="", contact_phone="", contact_email="joko@blokir.co.id",
             evidence_quote="PT Blokir Abadi, kontak Joko")))                                                  # ada di daftar jangan-hubungi
    with env.sf() as s:
        service.add_suppression(s, kind="email", value="joko@blokir.co.id", reason="opt_out", actor="ceo")
        s.commit()
    pid = make_project(env)
    tid = intake(env, pid)
    drain(env)
    t = get(env, tid)
    assert t.status == "completed", t.last_error
    res = t.result
    assert len(res["created_lead_ids"]) == 1
    assert {x["code"] for x in res["skipped"]} == {"not_grounded", "personal_email_not_allowed", "suppressed"}
    with env.sf() as s:
        lead = s.get(Lead, res["created_lead_ids"][0])
        src = s.get(service.LeadSource, lead.source_id)
        assert (lead.created_by, lead.contact_email, src.source_type, src.method, src.collected_by) == (
            "lead_generation", "rina@sinarkasir.co.id", "event", "agent_extraction", "lead_generation")
        assert s.scalar(select(service.Company).where(service.Company.name == "PT Karangan Fiktif")) is None
        assert len(s.scalars(select(Lead)).all()) == 1                    # tidak ada prospek hantu
        assert len(s.scalars(select(service.LeadSource)).all()) == 1       # sumber tidak digandakan/yatim


def test_intake_rejects_forbidden_source_before_calling_the_model(migrated_db, tmp_path):
    env = env_with(migrated_db, tmp_path)
    pid = make_project(env)
    tid = intake(env, pid, source={"source_type": "purchased_list"})
    drain(env)
    t = get(env, tid)
    assert t.status == "failed" and t.last_error_kind == "source_forbidden" and env.provider.calls == []


def test_intake_requires_url_for_public_sources_and_material(migrated_db, tmp_path):
    env = env_with(migrated_db, tmp_path)
    pid = make_project(env)
    a = intake(env, pid, source={"source_type": "public_website"})
    b = intake(env, pid, raw="x" * 8001)
    drain(env)
    assert get(env, a).last_error_kind == "source_url_required" and get(env, b).last_error_kind == "invalid_material" and env.provider.calls == []


def test_intake_is_not_auto_retried_and_dedupes_on_rerun(migrated_db, tmp_path):
    env = env_with(migrated_db, tmp_path, reply(cand()), reply(cand()))
    pid = make_project(env)
    intake(env, pid)
    intake(env, pid)
    drain(env)
    assert default_executors()["lead_generation"].idempotent is False
    with env.sf() as s:
        assert len(s.scalars(select(Lead)).all()) == 1       # eksekusi kedua dilewati sebagai duplikat


def test_intake_invalid_model_output_fails_without_creating_data(migrated_db, tmp_path):
    env = env_with(migrated_db, tmp_path, "bukan json", "masih bukan json")
    pid = make_project(env)
    tid = intake(env, pid, max_retries=0)
    drain(env)
    assert get(env, tid).status == "failed"
    with env.sf() as s:
        assert s.scalars(select(Lead)).all() == []


# ---------------------------------------------------------------- Market Research

def research(env, pid, material="PT Sinar Kasir Nusantara, toko ritel di Bandung, tertarik sistem kasir.", **p):
    return add_task(env, pid, role="market_research", action_type="market_research",
                    params={"topic": "UMKM ritel Bandung", "material": material} | p)


def test_research_persists_grounded_findings_and_flags_the_rest(migrated_db, tmp_path):
    out = {"summary": "ringkas", "items": [
        {"statement": "Ada toko ritel di Bandung", "basis": "provided_material", "evidence_quote": "toko ritel di Bandung"},
        {"statement": "Pasar tumbuh 40%", "basis": "provided_material", "evidence_quote": "pasar tumbuh 40 persen"}]}
    env = env_with(migrated_db, tmp_path, json.dumps(out))
    pid = make_project(env)
    tid = research(env, pid)
    drain(env)
    t = get(env, tid)
    assert t.status == "completed", (t.last_error_kind, t.last_error)
    with env.sf() as s:
        r = s.get(MarketResearch, t.result["research_id"])
        assert (r.verified_count, r.unverified_count) == (1, 1) and r.items[1]["verified"] is False


def test_research_never_receives_contact_data_or_sensitive_text(migrated_db, tmp_path):
    env = env_with(migrated_db, tmp_path)
    pid = make_project(env)
    a = research(env, pid, material="hubungi rina@sinarkasir.co.id")
    b = research(env, pid, material="pemilik beragama tertentu, NIK 3174012345678901")
    drain(env)
    assert get(env, a).last_error_kind == "pii_in_material" and get(env, b).last_error_kind == "sensitive_data" and env.provider.calls == []


# ---------------------------------------------------------------- Sales outreach

BRIEF = {"product": {"id": "p1", "name": "Kasir Pintar", "description": "Aplikasi kasir", "target_customers": "toko ritel"},
         "version": {"id": "v1", "version": "0.1.0", "status": "beta", "commit": "abc"}, "effective_permission": "beta_only",
         "usable_for_promotion": True, "promotion_label": "BETA", "blocked_reasons": [], "claims": [{"id": "f1", "text": "Mencatat penjualan harian", "basis": "verified"}],
         "unverified_claims": [], "limitations": ["Hanya satu kasir"], "pricing": None,
         "required_disclaimers": ["Produk ini masih dalam tahap beta."]}
GOOD = {"subject": "Perkenalan Kasir Pintar (beta)", "body": "Halo Bapak Rina, kami menawarkan Kasir Pintar versi beta yang mencatat penjualan harian untuk toko ritel."}
BAD = {"subject": "Kasir Pintar", "body": "Halo, Kasir Pintar adalah solusi terbaik dan 100% akurat untuk toko Anda, sudah rilis dan harga Rp 100.000 per bulan."}


@pytest.fixture
def sales(migrated_db, tmp_path, monkeypatch):
    def make(*replies, brief=BRIEF, forward=True):
        monkeypatch.setattr(agents, "_brief", lambda s, product_id, version_id: brief)
        env = env_with(migrated_db, tmp_path, *[json.dumps(r) for r in replies])
        with env.sf() as s:
            s.add(Product(id="p1", name="Kasir Pintar"))
            s.flush()
            lead = service.create_lead(s, POLICY, actor="ceo", company={"name": "PT Sinar Kasir", "industry": "ritel"},
                                       contact={"name": "Rina Wijaya", "title": "Direktur", "email": "rina@sinarkasir.co.id"},
                                       source={"source_type": "referral"})
            if forward:
                service.set_status(s, POLICY, lead, "qualified", actor="ceo")
                service.forward_to_sales(s, POLICY, lead, actor="ceo")
            s.commit()
            lid = lead.id
        return env, lid
    return make


def outreach(env, pid, lid):
    return add_task(env, pid, role="sales_client_relations", action_type="draft_outreach", params={"lead_id": lid, "product_id": "p1"}, max_retries=0)


def test_outreach_draft_passes_claim_check_and_gets_opt_out_footer(sales):
    env, lid = sales(GOOD)
    tid = outreach(env, make_project(env), lid)
    drain(env)
    t = get(env, tid)
    assert t.status == "completed", t.last_error
    with env.sf() as s:
        o = s.get(OutreachRecord, t.result["outreach_id"])
        assert o.status == "ready_for_review" and o.body.endswith(OPT_OUT_FOOTER) and o.claim_check["ok"]
        assert o.sent_at is None and s.get(Lead, lid).status == "qualified"          # menyusun draf tidak mengirim atau mengubah tahap
        assert len(s.scalars(select(AuditLog).where(AuditLog.action == "lead.pii_viewed")).all()) == 1


def test_outreach_with_forbidden_claims_is_corrected_once_then_blocked(sales):
    env, lid = sales(BAD, BAD, BAD)
    tid = outreach(env, make_project(env), lid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.last_error_kind) == ("failed", "unverified")          # verifikasi gagal: task tidak dianggap sukses
    with env.sf() as s:
        o = s.scalar(select(OutreachRecord))
        assert o.status == "blocked_by_claim_check" and not o.claim_check["ok"] and o.sent_at is None
    assert len(env.provider.calls) == 3
    assert "ditolak karena" in env.provider.calls[1][1].prompt                  # umpan balik temuan linter dikirim ke model


def test_outreach_self_corrects_when_second_draft_is_clean(sales):
    env, lid = sales(BAD, GOOD)
    tid = outreach(env, make_project(env), lid)
    drain(env)
    assert get(env, tid).result["status"] == "ready_for_review" and len(env.provider.calls) == 2


def test_outreach_refused_when_product_not_cleared(sales):
    env, lid = sales(GOOD, brief=BRIEF | {"usable_for_promotion": False, "blocked_reasons": ["izin dicabut"], "claims": []})
    tid = outreach(env, make_project(env), lid)
    drain(env)
    t = get(env, tid)
    assert t.status == "failed" and t.last_error_kind == "product_not_cleared" and env.provider.calls == []


def test_outreach_refused_for_unforwarded_or_dnc_leads(sales):
    env, lid = sales(GOOD, forward=False)
    pid = make_project(env)
    a = outreach(env, pid, lid)
    drain(env)
    assert get(env, a).last_error_kind == "not_forwarded"
    with env.sf() as s:
        lead = s.get(Lead, lid)
        service.set_status(s, POLICY, lead, "qualified", actor="ceo")
        service.forward_to_sales(s, POLICY, lead, actor="ceo")
        service.opt_out(s, lead, actor="ceo")
        s.commit()
    b = outreach(env, pid, lid)
    drain(env)
    assert get(env, b).last_error_kind == "do_not_contact" and env.provider.calls == []


def test_outreach_blocked_when_email_suppressed_after_forwarding(sales):
    env, lid = sales(GOOD)
    with env.sf() as s:
        service.add_suppression(s, kind="domain", value="sinarkasir.co.id", reason="complaint", actor="ceo")
        s.commit()
    tid = outreach(env, make_project(env), lid)
    drain(env)
    assert get(env, tid).last_error_kind == "suppressed" and env.provider.calls == []


def test_marketing_tasks_never_need_ceo_approval_to_draft_but_nothing_is_sent(migrated_db):
    from app.tasks.catalog import ACTION_RISK, needs_approval, risk_for
    for a in ("market_research", "lead_intake", "draft_outreach"):
        assert not needs_approval(risk_for(a))
    assert needs_approval(risk_for("external_outreach"))        # pengiriman nyata tetap memerlukan approval CEO


def test_suppressed_contact_in_source_line_blocks_candidate_even_if_model_omits_contact(migrated_db, tmp_path):
    env = env_with(migrated_db, tmp_path, reply(
        cand(company_name="PT Blokir Abadi", contact_name="", contact_title="", contact_phone="", contact_email="",        # kontak dikosongkan model
             evidence_quote="PT Blokir Abadi, kontak Joko"),
        cand()))
    with env.sf() as s:
        service.add_suppression(s, kind="email", value="joko@blokir.co.id", reason="opt_out", actor="ceo")
        s.commit()
    tid = intake(env, make_project(env))
    drain(env)
    t = get(env, tid)
    res = t.result
    assert t.status == "completed", (t.last_error_kind, t.last_error)
    assert [x["code"] for x in res["skipped"]] == ["suppressed"], res and len(res["created_lead_ids"]) == 1
    with env.sf() as s:
        assert s.scalar(select(service.Company).where(service.Company.name == "PT Blokir Abadi")) is None


def test_invalid_but_grounded_website_is_dropped_not_a_reason_to_reject_the_lead(migrated_db, tmp_path):
    raw = RAW + "Situs PT Sinar Kasir Nusantara: http://sinar_kasir/halaman\n"
    env = env_with(migrated_db, tmp_path, reply(cand(website="http://sinar_kasir/halaman")))
    tid = intake(env, make_project(env), raw=raw)
    drain(env)
    res = get(env, tid).result
    assert len(res["created_lead_ids"]) == 1 and res["skipped"] == []
    assert list(res["ungrounded_fields_dropped"].values()) == [["website"]]
