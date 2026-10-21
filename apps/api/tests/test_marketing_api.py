import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import AuditLog, Lead, Product, Task
from app.main import create_app
from app.tasks.executors import default_executors
from tests.fakes import FakeProvider

LEAD = {"company": {"name": "PT Maju Jaya", "industry": "ritel", "size_band": "small"},
        "contact": {"name": "Budi Santoso", "title": "Direktur", "email": "budi@majujaya.co.id", "phone": "+62 812 3456 7890"},
        "source": {"source_type": "referral"}}


@pytest.fixture
def c(settings):
    cfg = settings.model_copy(update={"ollama_enabled": True, "retry_backoff_base_s": 0.0})
    return TestClient(create_app(cfg, providers={"ollama": FakeProvider(reply="{}")}, executors=default_executors()))


def post(c, auth, path, body=None, **kw):
    return c.post(f"/api/marketing{path}", json=body if body is not None else {}, headers=auth, **kw)


def new_lead(c, auth, **over):
    r = post(c, auth, "/leads", LEAD | over)
    assert r.status_code == 201, r.text
    return r.json()


def test_every_endpoint_requires_the_token(c):
    for m, p in [("get", "/policy"), ("get", "/analytics"), ("get", "/leads"), ("post", "/leads"), ("get", "/leads/x"), ("get", "/suppression"),
                 ("get", "/retention"), ("post", "/retention/run"), ("post", "/tasks/intake"), ("get", "/outreach"), ("get", "/research")]:
        assert getattr(c, m)(f"/api/marketing{p}").status_code == 401, p


def test_policy_endpoint_states_rules_openly(c, auth):
    p = c.get("/api/marketing/policy", headers=auth).json()
    assert {s["type"] for s in p["allowed_sources"]} >= {"referral", "inbound"} and p["forbidden_sources"] and p["retention"]["auto_apply"] is False


def test_lead_list_and_detail_are_masked_by_default_and_reveal_is_audited(c, auth):
    lead = new_lead(c, auth)
    assert lead["contact"]["masked"] and "budi@" not in json.dumps(lead) and lead["contact"]["email"] == "b***@majujaya.co.id"
    assert "budi@majujaya" not in c.get("/api/marketing/leads", headers=auth).text
    d = c.get(f"/api/marketing/leads/{lead['id']}", headers=auth).json()
    assert d["contact"]["masked"] and d["source"]["type"] == "referral"
    r = c.get(f"/api/marketing/leads/{lead['id']}?reveal=true", headers=auth).json()
    assert r["contact"]["email"] == "budi@majujaya.co.id" and not r["contact"]["masked"]
    with c.app.state.session_factory() as s:
        assert len(s.scalars(select(AuditLog).where(AuditLog.action == "lead.pii_viewed")).all()) == 1


def test_policy_violations_map_to_422_and_duplicates_to_409(c, auth):
    assert post(c, auth, "/leads", LEAD | {"source": {"source_type": "purchased_list"}}).json()["code"] == "source_forbidden"
    assert post(c, auth, "/leads", LEAD | {"source": {"source_type": "public_website"}}).status_code == 422
    r = post(c, auth, "/leads", LEAD | {"contact": {"email": "x@gmail.com"}})
    assert r.status_code == 422 and r.json()["code"] == "personal_email_not_allowed"
    r = post(c, auth, "/leads", LEAD | {"contact": {"name": "Ani NIK 3174012345678901"}})
    assert r.status_code == 422 and r.json()["code"] == "sensitive_data" and "3174012345678901" not in r.text
    new_lead(c, auth)
    r = post(c, auth, "/leads", LEAD)
    assert r.status_code == 409 and r.json()["code"] == "duplicate_lead"
    assert post(c, auth, "/leads", LEAD | {"unknown_field": 1}).status_code == 422          # extra="forbid"
    with c.app.state.session_factory() as s:
        assert len(s.scalars(select(Lead)).all()) == 1                                    # penolakan tidak meninggalkan data


def test_full_pipeline_from_lead_to_won_deal(c, auth):
    lead = new_lead(c, auth)
    lid = lead["id"]
    r = post(c, auth, f"/leads/{lid}/status", {"status": "contacted"})
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"
    assert post(c, auth, f"/leads/{lid}/status", {"status": "qualified"}).json()["status"] == "qualified"
    r = post(c, auth, f"/leads/{lid}/status", {"status": "contacted"})
    assert r.status_code == 409 and r.json()["code"] == "evidence_required"
    assert post(c, auth, f"/leads/{lid}/interactions", {"kind": "call", "summary": "menelepon"}).status_code == 201
    assert post(c, auth, f"/leads/{lid}/status", {"status": "contacted"}).json()["status"] == "contacted"
    fw = post(c, auth, f"/leads/{lid}/forward", {}).json()
    assert fw["owner"] == "sales_client_relations" and fw["forwarded_at"]
    opp = post(c, auth, f"/leads/{lid}/convert", {"title": "Sistem kasir", "value_estimate_idr": 5000000})
    assert opp.status_code == 201
    oid = opp.json()["id"]
    assert post(c, auth, f"/opportunities/{oid}/requirements", {"text": "butuh laporan harian"}).status_code == 201
    assert post(c, auth, f"/opportunities/{oid}/stage", {"stage": "proposal"}).json()["stage"] == "proposal"
    r = post(c, auth, f"/opportunities/{oid}/stage", {"stage": "won", "reason": "setuju harga"})
    assert r.status_code == 422 and r.json()["code"] == "won_value_required"
    r = post(c, auth, f"/opportunities/{oid}/stage", {"stage": "won", "reason": "setuju harga", "won_value_idr": 4500000})
    assert r.json()["stage"] == "won"
    a = c.get("/api/marketing/analytics", headers=auth).json()
    assert a["win_rate"] == 1.0 and a["revenue_recorded_idr"] == 4500000 and a["customer_acquisition_cost_idr"] is None
    d = c.get(f"/api/marketing/leads/{lid}", headers=auth).json()
    assert d["status"] == "won" and d["opportunities"][0]["requirements"][0]["text"] == "butuh laporan harian"


def test_opt_out_then_recollection_is_refused(c, auth):
    lead = new_lead(c, auth)
    assert post(c, auth, f"/leads/{lead['id']}/opt-out", {"reason": "minta berhenti"}).json()["do_not_contact"] is True
    r = post(c, auth, "/leads", LEAD | {"company": {"name": "PT Lain"}, "contact": {"email": "budi@majujaya.co.id", "name": "B"}})
    assert r.status_code == 409 and r.json()["code"] == "suppressed"
    sup = c.get("/api/marketing/suppression", headers=auth).json()
    assert len(sup) == 1 and "budi" not in json.dumps(sup) and "majujaya" not in json.dumps(sup)


def test_erase_and_retention_endpoints(c, auth):
    lead = new_lead(c, auth)
    r = post(c, auth, f"/leads/{lead['id']}/erase", {"reason": "permintaan subjek"}).json()
    assert r["anonymized"] and r["contact"]["email"] is None
    assert c.get(f"/api/marketing/leads/{lead['id']}?reveal=true", headers=auth).json()["contact"]["email"] is None
    dry = post(c, auth, "/retention/run").json()
    assert dry["dry_run"] is True and dry["due"] == []
    assert post(c, auth, "/retention/run?dry_run=false").json() == {"dry_run": False, "anonymized": 0}


def test_task_helpers_create_marketing_tasks_with_params(c, auth):
    r = post(c, auth, "/tasks/intake", {"source": {"source_type": "event", "title": "Pameran"}, "raw_text": "PT Contoh di Bandung"})
    assert r.status_code == 201
    r2 = post(c, auth, "/tasks/research", {"topic": "Pasar kasir", "material": "bahan riset"})
    assert r2.status_code == 201 and r2.json()["project_id"] == r.json()["project_id"]          # satu proyek internal
    with c.app.state.session_factory() as s:
        t = s.get(Task, r.json()["task_id"])
        assert (t.role, t.action_type, t.status, t.params["raw_text"]) == ("lead_generation", "lead_intake", "queued", "PT Contoh di Bandung")
    bad = post(c, auth, "/tasks/intake", {"source": {"source_type": "social_media_scraping"}, "raw_text": "x"})
    assert bad.status_code == 422 and bad.json()["code"] == "source_forbidden"
    assert post(c, auth, "/tasks/intake", {"source": {"source_type": "event"}, "raw_text": "x" * 8001}).status_code == 422


def test_outreach_task_requires_forwarded_lead_and_known_product(c, auth):
    lead = new_lead(c, auth)
    with c.app.state.session_factory() as s:
        s.add(Product(id="p1", name="Kasir"))
        s.commit()
    r = post(c, auth, "/tasks/outreach", {"lead_id": lead["id"], "product_id": "p1"})
    assert r.status_code == 409 and r.json()["code"] == "not_forwarded"
    post(c, auth, f"/leads/{lead['id']}/status", {"status": "qualified"})
    fw = post(c, auth, f"/leads/{lead['id']}/forward", {"draft_outreach_product_id": "p1"}).json()
    assert fw["outreach_task"]["status"] == "queued"
    assert post(c, auth, "/tasks/outreach", {"lead_id": lead["id"], "product_id": "nope"}).status_code == 404


def test_mark_sent_endpoint_rejects_unready_drafts(c, auth):
    lead = new_lead(c, auth)
    from app.db.models import OutreachRecord
    with c.app.state.session_factory() as s:
        o = OutreachRecord(lead_id=lead["id"], subject="a", body="b", status="blocked_by_claim_check")
        s.add(o)
        s.commit()
        oid = o.id
    r = post(c, auth, f"/outreach/{oid}/mark-sent", {})
    assert r.status_code == 409 and r.json()["code"] == "not_ready"
    assert post(c, auth, f"/outreach/{oid}/cancel").json()["status"] == "cancelled"
    assert post(c, auth, "/outreach/zzz/cancel").status_code == 404


def test_missing_resources_return_404(c, auth):
    for path in ("/leads/zzz", "/opportunities/zzz/stage"):
        r = c.get(f"/api/marketing{path}", headers=auth) if path.startswith("/leads") else post(c, auth, path, {"stage": "proposal"})
        assert r.status_code == 404
