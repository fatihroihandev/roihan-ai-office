import asyncio
import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.approvals import service as approvals
from app.approvals.service import ApprovalError
from app.config import Settings
from app.db.base import utcnow
from app.db.models import (
    Approval, AuditLog, ContentAsset, Lead, LeadInteraction, OutboundMessage, OutreachRecord, Product, ProductVersion, ProjectFile, Task,
)
from app.main import create_app
from app.marketing import access, external, service
from app.marketing.access import AccessDenied
from app.marketing.external import OPT_OUT_FOOTER
from app.marketing.policy import Policy
from app.products import service as products
from app.tasks.executors import default_executors
from tests.conftest import TOKEN
from tests.fakes import FakeProvider

POLICY = Policy.from_settings(Settings(_env_file=None, app_local_token=TOKEN))

BRIEF = {"product": {"id": "p1", "name": "Kasir Pintar", "description": "Aplikasi kasir", "target_customers": "toko ritel"},
         "version": {"id": "v1", "version": "0.1.0", "status": "beta", "commit": "abc"}, "effective_permission": "beta_only",
         "usable_for_promotion": True, "promotion_label": "BETA", "blocked_reasons": [], "claims": [{"id": "f1", "text": "Mencatat penjualan harian", "basis": "verified"}],
         "unverified_claims": [], "limitations": ["Hanya satu kasir"], "pricing": None, "required_disclaimers": ["Produk ini masih dalam tahap beta."]}
GOOD_TITLE = "Kasir Pintar versi beta"
GOOD_BODY = "Kasir Pintar versi beta membantu toko ritel mencatat penjualan harian. Produk ini masih dalam tahap beta dan hanya mendukung satu kasir."
BAD_BODY = "Kasir Pintar adalah solusi terbaik dan 100% akurat untuk toko ritel Anda, sudah rilis dengan harga Rp 100.000 per bulan."
LEAD = {"company": {"name": "PT Maju Jaya", "industry": "ritel", "size_band": "small"},
        "contact": {"name": "Budi Santoso", "title": "Direktur", "email": "budi@majujaya.co.id"}, "source": {"source_type": "referral"}}


@pytest.fixture
def state(monkeypatch):
    st = {"brief": dict(BRIEF)}
    monkeypatch.setattr(products, "marketing_brief", lambda s, p, v: st["brief"])
    return st


def make(settings, replies=(), **over):
    cfg = settings.model_copy(update={"ollama_enabled": True, "retry_backoff_base_s": 0.0, **over})
    provider = FakeProvider(reply=[json.dumps(r) if isinstance(r, dict) else r for r in replies])
    c = TestClient(create_app(cfg, providers={"ollama": provider}, executors=default_executors()))
    c.provider = provider
    with c.app.state.session_factory() as s:
        s.add(Product(id="p1", name="Kasir Pintar"))
        s.flush()
        s.add(ProductVersion(id="v1", product_id="p1", version="0.1.0"))
        s.commit()
    return c


@pytest.fixture
def c(settings, state):
    return make(settings)


def drain(c):
    for _ in range(20):
        if not asyncio.run(c.app.state.worker.run_once()):
            return


def call(c, auth, method, path, body=None):
    return getattr(c, method)(f"/api/marketing{path}", json=body if body is not None else {}, headers=auth) if method == "post" or body is not None \
        else getattr(c, method)(f"/api/marketing{path}", headers=auth)


def new_content(c, auth, **over):
    r = call(c, auth, "post", "/content", {"product_id": "p1", "kind": "social_post", "channel": "linkedin", "title": GOOD_TITLE, "body": GOOD_BODY} | over)
    assert r.status_code == 201, r.text
    return r.json()


def pending(c, auth):
    return c.get("/api/approvals?status=pending", headers=auth).json()


def approve(c, auth, task_id):
    ap = c.get(f"/api/approvals?task_id={task_id}&status=pending", headers=auth).json()[0]
    assert c.post(f"/api/approvals/{ap['id']}/approve", headers=auth).status_code == 200


def task(c, tid):
    with c.app.state.session_factory() as s:
        t = s.get(Task, tid)
        return t.status, t.last_error_kind, t.result


def outbox(c, auth):
    return call(c, auth, "get", "/outbox").json()


def ready_lead(c, auth, **contact):
    lead = call(c, auth, "post", "/leads", LEAD | ({"contact": {**LEAD["contact"], **contact}} if contact else {})).json()
    call(c, auth, "post", f"/leads/{lead['id']}/status", {"status": "qualified"})
    assert call(c, auth, "post", f"/leads/{lead['id']}/forward", {}).status_code == 200
    return lead["id"]


def new_outreach(c, lid, body=None, status="ready_for_review"):
    with c.app.state.session_factory() as s:
        o = OutreachRecord(lead_id=lid, product_id="p1", version_id="v1", channel="email", subject="Perkenalan Kasir Pintar beta",
                           body=body or (GOOD_BODY + OPT_OUT_FOOTER), status=status, claim_check={"ok": True, "findings": []})
        s.add(o)
        s.commit()
        return o.id


# ================================================================== Content Workspace

def test_endpoints_require_token(c):
    for m, p in [("get", "/campaigns"), ("post", "/campaigns"), ("get", "/content"), ("post", "/content"), ("get", "/outbox"), ("post", "/tasks/content"),
                 ("post", "/content/x/request-publish"), ("post", "/outreach/x/request-send"), ("post", "/outbox/x/dispatch"),
                 ("post", "/opportunities/x/handoff"), ("get", "/handoffs")]:
        assert getattr(c, m)(f"/api/marketing{p}").status_code == 401, p


def test_content_passes_only_with_clean_claims(c, auth):
    ok = new_content(c, auth)
    assert ok["status"] == "ready_for_review" and ok["claim_check"]["ok"]
    bad = new_content(c, auth, body=BAD_BODY)
    assert bad["status"] == "blocked_by_claim_check" and {f["type"] for f in bad["claim_check"]["findings"]} >= {"absolute_claim", "unapproved_pricing"}


def test_content_validation(c, auth):
    for patch, code in [({"kind": "meme"}, "invalid_kind"), ({"channel": "tiktok"}, "channel_not_allowed")]:
        r = call(c, auth, "post", "/content", {"product_id": "p1", "kind": "social_post", "channel": "linkedin", "title": "T", "body": GOOD_BODY} | patch)
        assert r.status_code == 422 and r.json()["code"] == code
    r = call(c, auth, "post", "/content", {"product_id": "p1", "kind": "social_post", "channel": "linkedin", "title": "T", "body": "NIK 3174012345678901"})
    assert r.status_code == 422 and r.json()["code"] == "sensitive_data"
    r = call(c, auth, "post", "/content", {"product_id": "nope", "kind": "social_post", "channel": "linkedin", "title": "T", "body": GOOD_BODY})
    assert r.json()["code"] == "product_not_found"


def test_content_with_unapproved_product_is_flagged_not_cleared(c, auth, state):
    state["brief"] = BRIEF | {"usable_for_promotion": False, "blocked_reasons": ["izin dicabut"], "claims": []}
    assert new_content(c, auth)["status"] == "blocked_by_claim_check"


def test_editing_content_relints_and_changes_hash(c, auth):
    a = new_content(c, auth)
    r = c.patch(f"/api/marketing/content/{a['id']}", json={"body": BAD_BODY}, headers=auth).json()
    assert r["status"] == "blocked_by_claim_check"
    r = c.patch(f"/api/marketing/content/{a['id']}", json={"body": GOOD_BODY + " Tambahan jujur."}, headers=auth).json()
    assert r["status"] == "ready_for_review"
    with c.app.state.session_factory() as s:
        assert s.get(ContentAsset, a["id"]).body_hash == external.content_hash(r["title"], r["body"])


def test_content_agent_drafts_from_brief_with_correction_and_refuses_unapproved_products(settings, auth, state):
    c = make(settings, [{"title": "Judul", "body": BAD_BODY}, {"title": GOOD_TITLE, "body": GOOD_BODY}])
    tid = call(c, auth, "post", "/tasks/content", {"product_id": "p1", "kind": "social_post", "channel": "linkedin", "angle": "efisiensi toko"}).json()["task_id"]
    drain(c)
    status, kind, result = task(c, tid)
    assert status == "completed" and result["status"] == "ready_for_review" and len(c.provider.calls) == 2
    assert "ditolak karena" in c.provider.calls[1][1].prompt and "Mencatat penjualan harian" in c.provider.calls[0][1].prompt
    state["brief"] = BRIEF | {"usable_for_promotion": False, "blocked_reasons": ["izin dicabut"]}
    tid2 = call(c, auth, "post", "/tasks/content", {"product_id": "p1", "kind": "article", "channel": "blog"}).json()["task_id"]
    n = len(c.provider.calls)
    drain(c)
    assert task(c, tid2)[:2] == ("failed", "product_not_cleared") and len(c.provider.calls) == n      # model tidak dipanggil


def test_content_agent_persistent_violations_stay_blocked(settings, auth, state):
    c = make(settings, [{"title": "Judul", "body": BAD_BODY}] * 3)
    tid = call(c, auth, "post", "/tasks/content", {"product_id": "p1", "kind": "social_post", "channel": "linkedin"}).json()["task_id"]
    drain(c)
    assert task(c, tid)[:2] == ("failed", "unverified")
    with c.app.state.session_factory() as s:
        assert s.scalar(select(ContentAsset)).status == "blocked_by_claim_check"


def test_content_task_rejects_bad_channel_before_creating_task(c, auth):
    r = call(c, auth, "post", "/tasks/content", {"product_id": "p1", "kind": "social_post", "channel": "tiktok"})
    assert r.status_code == 422
    with c.app.state.session_factory() as s:
        assert s.scalars(select(Task)).all() == []


# ================================================================== publikasi: approval atas isi persis yang sama

def test_publish_needs_ceo_approval_and_ends_in_outbox_not_network(c, auth):
    a = new_content(c, auth)
    r = call(c, auth, "post", f"/content/{a['id']}/request-publish")
    assert r.status_code == 201 and r.json()["status"] == "pending_approval"
    tid = r.json()["task_id"]
    drain(c)
    assert task(c, tid)[0] == "pending_approval" and outbox(c, auth) == []          # tanpa approval tidak ada yang terjadi
    ap = pending(c, auth)[0]
    assert ap["risk_level"] == "critical" and ap["payload"]["action_type"] == "publish" and ap["payload"]["params"]["content_id"] == a["id"]
    approve(c, auth, tid)
    drain(c)
    assert task(c, tid)[0] == "completed"
    box = outbox(c, auth)
    assert len(box) == 1 and box[0]["status"] == "queued_manual" and box[0]["body"] == GOOD_BODY and box[0]["kind"] == "content"
    assert call(c, auth, "get", f"/content/{a['id']}").json()["status"] == "queued_for_dispatch"
    assert c.provider.calls == []                                                   # tidak ada panggilan model/jaringan apa pun
    d = call(c, auth, "post", f"/outbox/{box[0]['id']}/dispatch").json()
    assert d["status"] == "dispatched_manual" and call(c, auth, "get", f"/content/{a['id']}").json()["status"] == "published_manual"
    assert call(c, auth, "post", f"/outbox/{box[0]['id']}/dispatch").status_code == 409


def test_publish_request_refused_for_blocked_or_wrong_status_content(c, auth):
    bad = new_content(c, auth, body=BAD_BODY)
    r = call(c, auth, "post", f"/content/{bad['id']}/request-publish")
    assert r.status_code == 409 and r.json()["code"] == "not_ready"
    with c.app.state.session_factory() as s:
        assert s.scalars(select(Task)).all() == []


def test_content_edited_after_approval_request_cannot_be_published(c, auth):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    c.patch(f"/api/marketing/content/{a['id']}", json={"body": GOOD_BODY + " Kalimat baru yang tidak pernah disetujui."}, headers=auth)
    approve(c, auth, tid)
    drain(c)
    assert task(c, tid)[:2] == ("failed", "content_changed") and outbox(c, auth) == []


def test_revoked_product_permission_blocks_an_already_approved_publish(c, auth, state):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    approve(c, auth, tid)
    state["brief"] = BRIEF | {"usable_for_promotion": False, "blocked_reasons": ["klaim disengketakan"], "claims": []}      # izin gugur setelah approval
    drain(c)
    assert task(c, tid)[:2] == ("failed", "product_not_cleared") and outbox(c, auth) == []


def test_claims_rechecked_at_execution(c, auth, state):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    approve(c, auth, tid)
    state["brief"] = BRIEF | {"unverified_claims": [{"id": "f9", "text": "mencatat penjualan harian toko", "status": "disputed", "label": "x", "problems": []}]}
    drain(c)
    assert task(c, tid)[:2] == ("failed", "claims_failed") and outbox(c, auth) == []


def test_rejected_approval_publishes_nothing(c, auth):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    ap = pending(c, auth)[0]
    c.post(f"/api/approvals/{ap['id']}/reject", headers=auth)
    drain(c)
    assert task(c, tid)[0] == "cancelled" and outbox(c, auth) == []


def test_publish_daily_limit_counts_queued_messages(settings, auth, state):
    c = make(settings, content_max_publish_per_day=1)
    a, b = new_content(c, auth), new_content(c, auth, title="Judul lain", body=GOOD_BODY + " Versi kedua.")
    t1 = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    approve(c, auth, t1)
    drain(c)
    r = call(c, auth, "post", f"/content/{b['id']}/request-publish")
    assert r.status_code == 409 and r.json()["code"] == "daily_limit"


def test_channel_policy_is_enforced_at_publish_time_too(settings, auth, state):
    c = make(settings)
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    approve(c, auth, tid)
    c.app.state.settings.content_allowed_channels = "blog"          # kebijakan diperketat setelah approval
    drain(c)
    assert task(c, tid)[:2] == ("failed", "channel_not_allowed") and outbox(c, auth) == []


# ================================================================== pengiriman outreach

def test_outreach_send_full_flow_records_real_interaction_only_when_ceo_dispatches(c, auth):
    lid = ready_lead(c, auth)
    oid = new_outreach(c, lid)
    r = call(c, auth, "post", f"/outreach/{oid}/request-send")
    assert r.status_code == 201 and r.json()["status"] == "pending_approval"
    tid = r.json()["task_id"]
    p = pending(c, auth)[0]["payload"]["params"]
    assert p["recipient_domain"] == "majujaya.co.id" and "budi" not in json.dumps(p).lower()          # tidak ada data pribadi pada approval
    approve(c, auth, tid)
    drain(c)
    box = outbox(c, auth)
    assert len(box) == 1 and box[0]["kind"] == "outreach" and box[0]["lead_id"] == lid
    with c.app.state.session_factory() as s:
        assert s.scalars(select(LeadInteraction).where(LeadInteraction.kind == "email_out")).all() == []      # belum terkirim = belum ada interaksi
        assert s.get(OutreachRecord, oid).status == "queued_for_dispatch"
    assert call(c, auth, "post", f"/outreach/{oid}/mark-sent", {}).status_code == 409                        # tidak bisa dicatat ganda
    assert call(c, auth, "post", f"/outbox/{box[0]['id']}/dispatch").json()["status"] == "dispatched_manual"
    with c.app.state.session_factory() as s:
        assert len(s.scalars(select(LeadInteraction).where(LeadInteraction.kind == "email_out")).all()) == 1
        assert s.get(OutreachRecord, oid).status == "sent_manual"
    again = call(c, auth, "post", f"/outreach/{new_outreach(c, lid)}/request-send")
    assert again.status_code == 409 and again.json()["code"] == "too_soon"


@pytest.mark.parametrize("case,code", [("unforwarded", "not_forwarded"), ("no_footer", "opt_out_missing"), ("bad_status", "not_ready"), ("bad_claim", "claims_failed"),
                                       ("dnc", "do_not_contact"), ("suppressed", "suppressed")])
def test_outreach_request_refusals(c, auth, state, case, code):
    if case == "unforwarded":
        lead = call(c, auth, "post", "/leads", LEAD).json()
        oid = new_outreach(c, lead["id"])
    else:
        lid = ready_lead(c, auth)
        oid = new_outreach(c, lid, body=GOOD_BODY if case == "no_footer" else (BAD_BODY + OPT_OUT_FOOTER if case == "bad_claim" else None),
                           status="blocked_by_claim_check" if case == "bad_status" else "ready_for_review")
        if case == "dnc":
            call(c, auth, "post", f"/leads/{lid}/opt-out", {})
        if case == "suppressed":
            call(c, auth, "post", "/suppression", {"kind": "domain", "value": "majujaya.co.id", "reason": "complaint"})
    r = call(c, auth, "post", f"/outreach/{oid}/request-send")
    assert r.status_code == 409 and r.json()["code"] == code, r.text
    with c.app.state.session_factory() as s:
        assert s.scalars(select(Task)).all() == []                                 # tidak ada task/approval yang dibuat


def test_opt_out_between_request_and_approval_stops_the_send(c, auth):
    lid = ready_lead(c, auth)
    oid = new_outreach(c, lid)
    tid = call(c, auth, "post", f"/outreach/{oid}/request-send").json()["task_id"]
    call(c, auth, "post", f"/leads/{lid}/opt-out", {"reason": "minta berhenti"})
    approve(c, auth, tid)
    drain(c)
    assert task(c, tid)[:2] == ("failed", "do_not_contact") and outbox(c, auth) == []


def test_opt_out_while_queued_cancels_the_outbox_item_and_blocks_dispatch(c, auth):
    lid = ready_lead(c, auth)
    oid = new_outreach(c, lid)
    tid = call(c, auth, "post", f"/outreach/{oid}/request-send").json()["task_id"]
    approve(c, auth, tid)
    drain(c)
    mid = outbox(c, auth)[0]["id"]
    call(c, auth, "post", f"/leads/{lid}/opt-out", {})
    assert call(c, auth, "get", "/outbox?status=cancelled").json()[0]["id"] == mid
    assert call(c, auth, "post", f"/outbox/{mid}/dispatch").status_code == 409
    with c.app.state.session_factory() as s:
        assert s.get(OutreachRecord, oid).status == "cancelled" and s.scalars(select(LeadInteraction).where(LeadInteraction.kind == "email_out")).all() == []


def test_dispatch_rechecks_suppression_added_after_queueing(c, auth):
    lid = ready_lead(c, auth)
    tid = call(c, auth, "post", f"/outreach/{new_outreach(c, lid)}/request-send").json()["task_id"]
    approve(c, auth, tid)
    drain(c)
    mid = outbox(c, auth)[0]["id"]
    call(c, auth, "post", "/suppression", {"kind": "domain", "value": "majujaya.co.id", "reason": "complaint"})
    r = call(c, auth, "post", f"/outbox/{mid}/dispatch")
    assert r.status_code == 409 and r.json()["code"] == "suppressed"
    assert call(c, auth, "get", "/outbox?status=cancelled").json()[0]["id"] == mid


def test_outreach_daily_limit(settings, auth, state):
    c = make(settings, outreach_max_per_day=1)
    l1 = ready_lead(c, auth)
    l2 = ready_lead(c, auth, name="Siti Rahma", email="siti@majujaya.co.id")
    o1, o2 = new_outreach(c, l1), new_outreach(c, l2)
    t1 = call(c, auth, "post", f"/outreach/{o1}/request-send").json()["task_id"]
    approve(c, auth, t1)
    drain(c)
    r = call(c, auth, "post", f"/outreach/{o2}/request-send")
    assert r.status_code == 409 and r.json()["code"] == "daily_limit"


def test_cancel_outbox_item(c, auth):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    approve(c, auth, tid)
    drain(c)
    mid = outbox(c, auth)[0]["id"]
    assert call(c, auth, "post", f"/outbox/{mid}/cancel", {"reason": "batal"}).json()["status"] == "cancelled"
    assert call(c, auth, "get", f"/content/{a['id']}").json()["status"] == "cancelled"
    assert call(c, auth, "post", f"/outbox/{mid}/dispatch").status_code == 409


# ================================================================== pembatasan tindakan otomatis (tidak dapat dilewati)

def test_external_actions_are_critical_and_agents_cannot_approve_them(c, auth):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    with c.app.state.session_factory() as s:
        t = s.get(Task, tid)
        assert (t.risk_level, t.requires_approval, t.action_type) == ("critical", True, "publish")
        ap = s.scalar(select(Approval).where(Approval.task_id == tid))
        for actor in ("content_promotion", "sales_client_relations", "manager", "system", "worker", ""):
            with pytest.raises(ApprovalError) as e:
                approvals.decide(s, ap, "approved", actor)
            assert e.value.code == "agent_cannot_approve"


def test_enqueue_without_valid_approval_is_impossible(c, auth):
    a = new_content(c, auth)
    # task publish dibuat manual TANPA approval disetujui: eksekusi langsung lewat fungsi ditolak
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    with c.app.state.session_factory() as s:
        asset = s.get(ContentAsset, a["id"])
        with pytest.raises(service.MarketingError) as e:
            external.enqueue_publish(s, POLICY, asset, task_id=tid, expected_hash=asset.body_hash, actor="content_promotion")
        assert e.value.code == "not_approved"
        with pytest.raises(AccessDenied):
            external.enqueue_publish(s, POLICY, asset, task_id=tid, expected_hash=asset.body_hash, actor="lead_generation")
        with pytest.raises(AccessDenied):
            external.enqueue_publish(s, POLICY, asset, task_id=tid, expected_hash=asset.body_hash, actor="market_research")


def test_approval_for_other_payload_does_not_authorise_this_content(c, auth):
    a, b = new_content(c, auth), new_content(c, auth, title="Lain", body=GOOD_BODY + " Berbeda.")
    ta = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    tb = call(c, auth, "post", f"/content/{b['id']}/request-publish").json()["task_id"]
    approve(c, auth, ta)
    with c.app.state.session_factory() as s:
        # menyalahgunakan approval milik task A untuk konten B
        with pytest.raises(service.MarketingError) as e:
            external.enqueue_publish(s, POLICY, s.get(ContentAsset, b["id"]), task_id=tb, expected_hash=b["body_hash"] if "body_hash" in b else "x", actor="content_promotion")
        assert e.value.code == "not_approved"


def test_task_created_directly_via_tasks_api_still_needs_approval_and_fails_safely(c, auth):
    pid = c.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]
    t = c.post("/api/tasks", json={"project_id": pid, "title": "Kirim langsung", "role": "sales_client_relations", "action_type": "external_outreach",
                                   "params": {"outreach_id": "ngawur", "body_hash": "x"}}, headers=auth).json()
    q = c.post(f"/api/tasks/{t['id']}/queue", headers=auth).json()
    assert q["status"] == "pending_approval"
    drain(c)
    assert task(c, t["id"])[0] == "pending_approval"
    approve(c, auth, t["id"])
    drain(c)
    assert task(c, t["id"])[:2] == ("failed", "outreach_not_found") and outbox(c, auth) == []


def test_access_matrix_for_phase_9():
    assert access.allowed("content_promotion", "content.write") and access.allowed("content_promotion", "product_brief.read")
    assert not access.allowed("content_promotion", "lead.read_pii") and not access.allowed("content_promotion", "lead.create")
    assert not access.allowed("market_research", "outbound.enqueue") and not access.allowed("lead_generation", "outbound.enqueue")
    assert not access.allowed("market_research", "content.write")


# ================================================================== kampanye

def test_campaign_rules_and_report(c, auth):
    base = {"name": "Peluncuran beta", "product_id": "p1", "channels": ["linkedin", "blog"], "objective": "Mengenalkan beta"}
    r = call(c, auth, "post", "/campaigns", base | {"budget_idr": 1_000_000})
    assert r.status_code == 422 and r.json()["code"] == "paid_ads_unsupported"
    assert call(c, auth, "post", "/campaigns", base | {"channels": ["tiktok"]}).json()["code"] == "channel_not_allowed"
    assert call(c, auth, "post", "/campaigns", base | {"product_id": "nope"}).json()["code"] == "product_not_found"
    assert call(c, auth, "post", "/campaigns", base | {"objective": "NIK 3174012345678901"}).status_code == 422
    camp = call(c, auth, "post", "/campaigns", base).json()
    cid = camp["id"]
    assert camp["status"] == "draft" and camp["budget_idr"] == 0
    r = call(c, auth, "post", "/content", {"product_id": "p1", "kind": "social_post", "channel": "instagram", "title": "T", "body": GOOD_BODY, "campaign_id": cid})
    assert r.json()["code"] == "channel_not_in_campaign"
    a = new_content(c, auth, campaign_id=cid)
    rep = call(c, auth, "get", f"/campaigns/{cid}").json()
    assert rep["report"]["content_by_status"] == {"ready_for_review": 1} and rep["report"]["roi"] is None
    assert all(v is None for v in rep["report"]["metrics"].values())                     # belum ada angka: null, bukan nol
    call(c, auth, "post", f"/campaigns/{cid}/metrics", {"metric": "revenue_idr", "value": 3_000_000})
    assert call(c, auth, "get", f"/campaigns/{cid}").json()["report"]["roi"] is None      # pendapatan tanpa biaya: ROI tidak dihitung
    call(c, auth, "post", f"/campaigns/{cid}/metrics", {"metric": "cost_idr", "value": 1_000_000})
    assert call(c, auth, "get", f"/campaigns/{cid}").json()["report"]["roi"] == 2.0
    assert call(c, auth, "post", f"/campaigns/{cid}/metrics", {"metric": "karangan", "value": 1}).status_code == 422
    assert call(c, auth, "post", f"/campaigns/{cid}/status", {"status": "completed"}).status_code == 409
    assert call(c, auth, "post", f"/campaigns/{cid}/status", {"status": "active"}).json()["status"] == "active"
    assert call(c, auth, "post", f"/campaigns/{cid}/status", {"status": "completed"}).json()["status"] == "completed"
    assert call(c, auth, "post", f"/campaigns/{cid}/status", {"status": "active"}).status_code == 409
    assert a["campaign_id"] == cid


def test_agents_cannot_run_campaigns(c, auth):
    with c.app.state.session_factory() as s:
        for actor in ("content_promotion", "market_research", "manager"):
            with pytest.raises(AccessDenied):
                external.create_campaign(s, POLICY, actor=actor, name="X", product_id="p1", channels=["blog"])


# ================================================================== serah-terima kebutuhan klien ke Engineering

def won_opportunity(c, auth, requirements=("Laporan penjualan harian", "Integrasi printer struk")):
    lid = ready_lead(c, auth)
    opp = call(c, auth, "post", f"/leads/{lid}/convert", {"title": "Sistem kasir toko"}).json()
    for r in requirements:
        call(c, auth, "post", f"/opportunities/{opp['id']}/requirements", {"text": r})
    return lid, opp["id"]


def to_won(c, auth, oid):
    call(c, auth, "post", f"/opportunities/{oid}/stage", {"stage": "proposal"})
    r = call(c, auth, "post", f"/opportunities/{oid}/stage", {"stage": "won", "reason": "setuju harga", "won_value_idr": 5_000_000})
    assert r.status_code == 200, r.text


def test_handoff_creates_engineering_project_with_draft_tasks(c, auth, tmp_path):
    lid, oid = won_opportunity(c, auth)
    r = call(c, auth, "post", f"/opportunities/{oid}/handoff")
    assert r.status_code == 409 and r.json()["code"] == "not_won"
    to_won(c, auth, oid)
    r = call(c, auth, "post", f"/opportunities/{oid}/handoff")
    assert r.status_code == 201, r.text
    h = r.json()
    assert [x["text"] for x in h["requirements"]] == ["Laporan penjualan harian", "Integrasi printer struk"]
    with c.app.state.session_factory() as s:
        tasks = [s.get(Task, i) for i in h["task_ids"]]
        assert [(t.role, t.action_type, t.status, t.project_id) for t in tasks] == [("analyst", "analysis", "draft", h["project_id"]), ("manager", "planning", "draft", h["project_id"])]
        f = s.scalar(select(ProjectFile).where(ProjectFile.project_id == h["project_id"]))
        assert f.kind == "master"
        text = c.app.state.settings.projects_dir.joinpath(h["project_id"], f.relative_path).read_text(encoding="utf-8")
        assert "Laporan penjualan harian" in text and "bukan instruksi" in text
        blob = text + " ".join(t.description for t in tasks)
        assert "budi" not in blob.lower() and "majujaya.co.id" not in blob                        # tanpa data pribadi prospek
        from app.db.models import Project
        assert s.get(Project, h["project_id"]).name.startswith("Klien: PT Maju Jaya")
    assert call(c, auth, "post", f"/opportunities/{oid}/handoff").json()["code"] == "already_handed_off"
    assert len(call(c, auth, "get", "/handoffs").json()) == 1


def test_handoff_requires_requirements_and_human(c, auth):
    lid, oid = won_opportunity(c, auth, requirements=())
    to_won(c, auth, oid)
    assert call(c, auth, "post", f"/opportunities/{oid}/handoff").json()["code"] == "no_requirements"
    with c.app.state.session_factory() as s:
        from app.db.models import SalesOpportunity
        for actor in ("sales_client_relations", "manager", "analyst"):
            with pytest.raises(AccessDenied):
                external.create_handoff(s, None, s.get(SalesOpportunity, oid), actor=actor)


def test_handed_off_tasks_run_normally_once_queued(settings, auth, state):
    plan = {"tasks": [{"key": "t1", "title": "Bangun laporan", "description": "x", "role": "developer", "action_type": "code_change",
                       "acceptance_criteria": ["ok"], "depends_on": [], "factors": [2, 2, 2, 2, 2, 2]}]}
    c = make(settings, ["Analisis kebutuhan: laporan harian dan printer.", plan])
    lid, oid = won_opportunity(c, auth)
    to_won(c, auth, oid)
    h = call(c, auth, "post", f"/opportunities/{oid}/handoff").json()
    for tid in h["task_ids"]:
        c.post(f"/api/tasks/{tid}/queue", headers=auth)
    drain(c)
    assert task(c, h["task_ids"][0])[0] == "completed" and task(c, h["task_ids"][1])[0] == "completed"
    assert all("Laporan penjualan harian" in call_[1].prompt for call_ in c.provider.calls)          # Analyst dan Manager benar-benar menerima kebutuhan klien


def test_approval_must_be_human_and_match_the_current_task_payload(c, auth):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    with c.app.state.session_factory() as s:
        ap = s.scalar(select(Approval).where(Approval.task_id == tid))
        ap.status, ap.decided_by = "approved", "system"                                 # persetujuan palsu bukan dari manusia
        s.commit()
        asset = s.get(ContentAsset, a["id"])
        with pytest.raises(service.MarketingError) as e:
            external.enqueue_publish(s, POLICY, asset, task_id=tid, expected_hash=asset.body_hash, actor="content_promotion")
        assert e.value.code == "not_approved"
        ap.decided_by = "ceo"
        s.commit()
        t = s.get(Task, tid)
        t.params = {**t.params, "channel": "blog"}                                      # isi task diubah setelah disetujui
        s.commit()
        with pytest.raises(service.MarketingError) as e:
            external.enqueue_publish(s, POLICY, asset, task_id=tid, expected_hash=asset.body_hash, actor="content_promotion")
        assert e.value.code == "not_approved"


def test_outreach_edited_after_request_cannot_be_sent(c, auth):
    lid = ready_lead(c, auth)
    oid = new_outreach(c, lid)
    tid = call(c, auth, "post", f"/outreach/{oid}/request-send").json()["task_id"]
    with c.app.state.session_factory() as s:
        o = s.get(OutreachRecord, oid)
        o.body = o.body + " Kalimat yang tidak pernah disetujui."
        s.commit()
    approve(c, auth, tid)
    drain(c)
    assert task(c, tid)[:2] == ("failed", "content_changed") and outbox(c, auth) == []


def test_queued_content_cannot_be_edited(c, auth):
    a = new_content(c, auth)
    tid = call(c, auth, "post", f"/content/{a['id']}/request-publish").json()["task_id"]
    approve(c, auth, tid)
    drain(c)
    r = c.patch(f"/api/marketing/content/{a['id']}", json={"body": GOOD_BODY + " Diubah setelah antre."}, headers=auth)
    assert r.status_code == 409 and r.json()["code"] == "not_editable"


def test_handoff_manager_task_depends_on_analysis(c, auth):
    from app.db.models import TaskDependency
    lid, oid = won_opportunity(c, auth)
    to_won(c, auth, oid)
    h = call(c, auth, "post", f"/opportunities/{oid}/handoff").json()
    with c.app.state.session_factory() as s:
        dep = s.scalar(select(TaskDependency).where(TaskDependency.task_id == h["task_ids"][1]))
        assert dep.depends_on_id == h["task_ids"][0]
