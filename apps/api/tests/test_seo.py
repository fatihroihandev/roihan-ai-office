"""SEO Specialist dan Marketing Analytics (Phase 14)."""
import asyncio

import pytest

from app.db.models import CampaignMetric, MarketingArtifact, ModelCapability, SeoCampaign, SeoKeyword, SeoMetric, SeoRecommendation, Task
from app.marketing import access, seo
from app.marketing.seo_agents import MarketingAnalyticsExecutor, SeoSpecialistExecutor
from app.tasks.catalog import ACTION_RISK, ROLES
from app.tasks.executors import default_executors
from tests.fakes import FakeProvider
from tests.helpers import add_task, build_env, drain, get, make_project

GOOD = """<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Roihan Software House - Jasa Pembuatan Aplikasi</title>
<meta name="description" content="Roihan Software House membantu bisnis membangun website dan aplikasi web sesuai kebutuhan, dengan proses kerja yang transparan.">
<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="canonical" href="https://roihan.example/layanan">
<meta property="og:title" content="Layanan"><script type="application/ld+json">{"@type":"Organization"}</script></head>
<body><h1>Layanan</h1><h2>Website</h2><img src="a.png" alt="logo"><a href="/kontak">Kontak</a></body></html>"""
BAD = "<html><head><meta name='robots' content='noindex'></head><body><h1>A</h1><h1>B</h1><img src='x.png'><img src='y.png' alt=''></body></html>"


def ids(report):
    return {f["id"] for f in report["findings"]}


# ------------------------------------------------------------------ audit teknis

def test_good_page_has_no_critical_or_warning_findings():
    r = seo.audit_html("https://roihan.example/layanan", GOOD, "User-agent: *\nDisallow: /admin", "<urlset><url><loc>https://roihan.example/layanan</loc></url></urlset>")
    assert r["counts"]["critical"] == 0 and r["counts"]["warning"] == 0
    assert r["page"]["title"].startswith("Roihan") and r["page"]["jsonld_blocks"] == 1 and r["page"]["sitemap_urls"] == 1


def test_bad_page_reports_concrete_findings_and_states_what_was_not_checked():
    r = seo.audit_html("https://x.example/", BAD, "User-agent: *\nDisallow: /")
    assert {"title_missing", "noindex", "h1_multiple", "img_alt_missing", "viewport_missing", "canonical_missing", "robots_blocks_all", "lang_missing"} <= ids(r)
    assert r["counts"]["critical"] == 3 and any("alt" in f["message"] for f in r["findings"])
    assert any("tautan rusak" in x for x in r["not_checked"])         # tidak berpura-pura memeriksa yang tak bisa diperiksa


def test_invalid_jsonld_sitemap_and_foreign_canonical():
    html = GOOD.replace('{"@type":"Organization"}', "{rusak").replace("https://roihan.example/layanan\"", "https://lain.example/x\"")
    r = seo.audit_html("https://roihan.example/layanan", html, "", "<urlset><url>")
    assert {"jsonld_invalid", "canonical_other_domain", "sitemap_invalid"} <= ids(r)


def test_missing_robots_and_sitemap_are_not_reported_as_failures():
    r = seo.audit_html("https://roihan.example/layanan", GOOD)
    assert {"robots_not_provided", "sitemap_not_provided"} <= ids(r) and r["counts"]["critical"] == 0


def test_robots_only_blocks_when_disallow_applies_to_all_agents():
    assert seo._robots_blocks_all("User-agent: *\nDisallow: /") is True
    assert seo._robots_blocks_all("User-agent: Googlebot\nDisallow: /") is False
    assert seo._robots_blocks_all("User-agent: *\nDisallow: /private") is False


# ------------------------------------------------------------------ klaim dan keyword

@pytest.mark.parametrize("text", ["Kami menjamin... dijamin peringkat 1", "pasti naik ke halaman pertama google", "guaranteed #1 on google", "Jaminan peringkat teratas"])
def test_guarantee_claims_are_flagged(text):
    assert seo.lint_seo_claims(text)


def test_honest_text_is_clean():
    assert seo.lint_seo_claims("Kami membantu memperbaiki struktur halaman agar lebih mudah ditemukan; hasil bergantung banyak faktor.") == []


def test_keyword_volume_only_kept_when_present_in_material():
    material = "Catatan: 'jasa pembuatan website' dicari sekitar 1.900 per bulan, persaingan tinggi. Tidak ada data lain."
    items = [
        {"keyword": "jasa pembuatan website", "intent": "transactional", "priority": "high", "rationale": "relevan", "volume": 1900,
         "competition": "tinggi", "evidence_quote": "'jasa pembuatan website' dicari sekitar 1.900 per bulan, persaingan tinggi"},
        {"keyword": "aplikasi kasir", "intent": "commercial", "priority": "medium", "rationale": "dijamin peringkat 1", "volume": 5400,
         "competition": "rendah", "evidence_quote": "aplikasi kasir 5.400"},                       # kutipan karangan
        {"keyword": "x", "intent": "aneh", "volume": 1},                                         # terlalu pendek: dibuang
    ]
    out = seo.ground_keywords(items, material)
    assert len(out) == 2
    a, b = out
    assert a["volume"] == 1900 and a["competition"] == "tinggi" and a["data_available"] is True
    assert b["volume"] is None and b["competition"] is None and b["data_available"] is False and b["evidence_quote"] == ""
    assert b["rationale"] == "" and b["flagged_claims"]           # rasional dengan jaminan dibuang dan ditandai


def test_keyword_volume_must_match_quote_digits():
    material = "'seo bandung' sekitar 300 per bulan"
    out = seo.ground_keywords([{"keyword": "seo bandung", "volume": 9999, "competition": "", "evidence_quote": "'seo bandung' sekitar 300 per bulan"}], material)
    assert out[0]["volume"] is None


# ------------------------------------------------------------------ KPI

def test_kpis_use_null_for_unknown_and_roi_only_with_complete_data(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    with env.sf() as s:
        k = seo.kpis(s)
        assert k["organic"]["impressions"] is None and k["organic"]["ctr"] is None and k["money"]["roi"] is None
        assert any("belum" in n for n in k["notes"])
        seo.record_metric(s, "impressions", 1000, page="/", period="2026-10", recorded_by="ceo")
        seo.record_metric(s, "clicks", 50, page="/", period="2026-10", recorded_by="ceo")
        seo.record_metric(s, "position", 8, page="/", period="2026-10", recorded_by="ceo")
        seo.record_metric(s, "position", 12, page="/x", period="2026-10", recorded_by="ceo")
        s.commit()
        k = seo.kpis(s)
        assert k["organic"]["ctr"] == 0.05 and k["organic"]["avg_position"] == 10.0 and k["organic"]["organic_sessions"] is None
        with pytest.raises(Exception):
            seo.record_metric(s, "position", 0.5, page=None, period="2026-10", recorded_by="ceo")
        with pytest.raises(Exception):
            seo.record_metric(s, "ngawur", 1, page=None, period="2026-10", recorded_by="ceo")


def test_roi_requires_both_cost_and_revenue(migrated_db, tmp_path):
    from app.db.models import Campaign, Product
    env = build_env(migrated_db, tmp_path)
    with env.sf() as s:
        p = Product(name="P")
        s.add(p)
        s.flush()
        c = Campaign(name="C", product_id=p.id, objective="o", channels=["blog"], status="draft", budget_idr=0)
        s.add(c)
        s.flush()
        s.add(CampaignMetric(campaign_id=c.id, metric="cost_idr", value=1000, recorded_by="ceo"))
        s.commit()
        assert seo.kpis(s)["money"]["roi"] is None            # pendapatan belum ada
        s.add(CampaignMetric(campaign_id=c.id, metric="revenue_idr", value=3000, recorded_by="ceo"))
        s.commit()
        assert seo.kpis(s)["money"]["roi"] == 2.0


# ------------------------------------------------------------------ peran dan akses

def test_roles_actions_and_executors_registered():
    assert ROLES["seo_specialist"] == "marketing" and ROLES["marketing_analytics"] == "marketing"
    assert all(ACTION_RISK[a] == "low" for a in ("seo_audit", "keyword_research", "content_brief", "marketing_analysis"))
    ex = default_executors()
    assert ex["seo_specialist"].idempotent and ex["marketing_analytics"].idempotent


def test_seo_and_analytics_cannot_touch_pii_or_enqueue_outbound():
    for role in ("seo_specialist", "marketing_analytics"):
        assert not access.allowed(role, "lead.read_pii") and not access.allowed(role, "outbound.enqueue") and not access.allowed(role, "outreach.draft")
    assert access.allowed("seo_specialist", "seo.write") and not access.allowed("market_research", "seo.write")


# ------------------------------------------------------------------ executor melalui worker

def run_task(env, project_id, role, action, params, **kw):
    from app.tasks import service
    with env.sf() as s:
        t = service.create_task(s, project_id=project_id, title="T", role=role, action_type=action, params=params, **kw)
        service.queue_task(s, t)
        s.commit()
        tid = t.id
    drain(env)
    return tid


def artifacts(env):
    with env.sf() as s:
        return list(s.query(MarketingArtifact).all())


def test_audit_task_runs_without_any_model_call(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = run_task(env, pid, "seo_specialist", "seo_audit", {"url": "https://x.example/", "html": BAD})
    assert get(env, tid).status == "completed" and env.provider.calls == []
    [a] = artifacts(env)
    assert a.kind == "audit" and a.data["counts"]["critical"] >= 1 and a.task_id == tid


def test_audit_requires_html(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = run_task(env, make_project(env), "seo_specialist", "seo_audit", {"url": "u", "html": "  "})
    assert get(env, tid).status == "failed" and get(env, tid).last_error_kind == "invalid_html"


def test_campaign_external_audit_crawls_only_allowlisted_domain(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    with env.sf() as s:
        campaign = SeoCampaign(name="Situs uji", website_url="https://contoh.id/", allowed_domains=["contoh.id"],
                               project_id=None, status="auditing")
        s.add(campaign)
        s.commit()
        campaign_id = campaign.id

    class FakeWeb:
        def __init__(self): self.requested = []
        async def fetch(self, url, **kwargs):
            self.requested.append(url)
            return {"url": url, "status": 200, "bytes": 100, "title": "Halaman uji", "description": "Deskripsi",
                    "links": ["https://contoh.id/kontak", "https://evil.example/"],
                    "seo": {"lang": "id", "robots": "", "canonical": url, "h1": 1, "h2": 0,
                            "images": 0, "images_no_alt": 0, "viewport": True, "og_tags": [], "jsonld_validity": []},
                    "text": "teks rahasia yang tidak disimpan"}

    fake_web = FakeWeb()
    env.worker._web_access = fake_web
    tid = run_task(env, pid, "seo_specialist", "seo_audit", {"campaign_id": campaign_id})
    assert get(env, tid).status == "completed"
    assert fake_web.requested == ["https://contoh.id/", "https://contoh.id/kontak"]
    [artifact] = [a for a in artifacts(env) if a.kind == "audit"]
    assert len(artifact.data["pages"]) == 2
    assert "teks rahasia yang tidak disimpan" not in str(artifact.data)


KW_JSON = ('{"summary":"ringkas","items":[{"keyword":"jasa website","intent":"transactional","priority":"high","rationale":"relevan layanan",'
           '"volume":500,"competition":"sedang","evidence_quote":"jasa website 500 per bulan sedang"},'
           '{"keyword":"seo lokal","intent":"informational","priority":"low","rationale":"pasti naik peringkat 1","volume":900,"competition":"","evidence_quote":""}]}')


def test_keyword_task_stores_grounded_items_only(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=KW_JSON))
    tid = run_task(env, make_project(env), "seo_specialist", "keyword_research", {"topic": "layanan", "material": "Data internal: jasa website 500 per bulan sedang."})
    assert get(env, tid).status == "completed"
    [a] = artifacts(env)
    first, second = a.data["items"]
    assert first["volume"] == 500 and second["volume"] is None and second["flagged_claims"] and second["rationale"] == ""
    assert (a.verified_count, a.unverified_count) == (1, 1)


def test_keyword_task_rejects_empty_material_and_pii(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=KW_JSON))
    pid = make_project(env)
    t1 = run_task(env, pid, "seo_specialist", "keyword_research", {"topic": "layanan", "material": ""})
    t2 = run_task(env, pid, "seo_specialist", "keyword_research", {"topic": "layanan", "material": "hubungi budi@contoh.co.id untuk data"})
    assert get(env, t1).last_error_kind == "invalid_material"
    assert get(env, t2).status == "failed" and not artifacts(env)


BRIEF_OK = ('{"title_options":["Panduan memilih jasa website"],"search_intent":"informasional","outline":[{"heading":"Apa itu","points":["definisi"]}],'
            '"faq":["Berapa lama?"],"internal_links":["/layanan"],"avoid_claims":["jangan menjanjikan peringkat"]}')
BRIEF_BAD = BRIEF_OK.replace("Panduan memilih jasa website", "Dijamin peringkat 1 di Google")


def test_brief_stored_and_guarantee_claims_blocked(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=BRIEF_OK))
    pid = make_project(env)
    ok = run_task(env, pid, "seo_specialist", "content_brief", {"topic": "jasa website"})
    assert get(env, ok).status == "completed" and artifacts(env)[0].kind == "brief"
    env2 = build_env(migrated_db, tmp_path / "b", provider=FakeProvider(reply=BRIEF_BAD))
    bad = run_task(env2, make_project(env2, "P2"), "seo_specialist", "content_brief", {"topic": "jasa website"})
    assert get(env2, bad).status == "failed" and get(env2, bad).last_error_kind == "claims_blocked"


def test_analytics_report_is_deterministic_and_marks_unknowns(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    tid = run_task(env, make_project(env), "marketing_analytics", "marketing_analysis", {})
    assert get(env, tid).status == "completed" and env.provider.calls == []
    [a] = artifacts(env)
    assert a.kind == "analysis" and a.data["kpis"]["organic"]["impressions"] is None
    assert any("belum" in o for o in a.data["observations"]) and a.data["observations"][-1].startswith("Pengamatan ini deskriptif")


def test_wrong_action_is_rejected_for_each_role(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    t1 = run_task(env, pid, "seo_specialist", "analysis", {})
    t2 = run_task(env, pid, "marketing_analytics", "analysis", {})
    assert get(env, t1).last_error_kind == "unsupported_action" and get(env, t2).last_error_kind == "unsupported_action"


# ------------------------------------------------------------------ API

def test_api_requires_token_and_full_flow(client, auth, settings):
    assert client.post("/api/marketing/seo/tasks/audit", json={"html": "x"}).status_code == 401
    assert client.get("/api/marketing/seo/kpis").status_code == 401
    r = client.post("/api/marketing/seo/tasks/audit", json={"url": "https://x.example/", "html": BAD}, headers=auth)
    assert r.status_code == 201
    assert client.post("/api/marketing/seo/tasks/audit", json={"html": ""}, headers=auth).status_code == 422
    assert client.post("/api/marketing/seo/tasks/keywords", json={"topic": "layanan", "material": "m", "product_id": "tidak-ada"}, headers=auth).status_code == 404
    assert client.post("/api/marketing/seo/tasks/analysis", headers=auth).status_code == 201
    k = client.get("/api/marketing/seo/kpis", headers=auth).json()
    assert k["organic"]["impressions"] is None and k["money"]["roi"] is None
    m = client.post("/api/marketing/seo/metrics", json={"metric": "clicks", "value": 12, "period": "2026-10"}, headers=auth)
    assert m.status_code == 201
    assert client.post("/api/marketing/seo/metrics", json={"metric": "clicks", "value": -1, "period": "2026-10"}, headers=auth).status_code == 422
    assert client.post("/api/marketing/seo/metrics", json={"metric": "position", "value": 0.2, "period": "2026-10"}, headers=auth).status_code == 422
    assert client.post("/api/marketing/seo/metrics", json={"metric": "clicks", "value": 1, "period": "bulan-ini"}, headers=auth).status_code == 422
    assert client.get("/api/marketing/seo/kpis", headers=auth).json()["organic"]["clicks"] == 12
    assert client.get("/api/marketing/seo/metrics", headers=auth).json()[0]["metric"] == "clicks"


def test_handoff_creates_draft_engineering_task_once(client, auth, settings):
    pid = client.post("/api/projects", json={"name": "Website"}, headers=auth).json()["id"]
    from app.db.session import create_db_engine, create_session_factory
    sf = create_session_factory(create_db_engine(settings.database_url))
    report = seo.audit_html("https://x.example/", BAD)
    with sf() as s:
        a = MarketingArtifact(kind="audit", title="Audit uji", summary="s", data=report)
        k = MarketingArtifact(kind="keywords", title="K", summary="s", data={"items": []})
        s.add_all([a, k])
        s.commit()
        aid, kid = a.id, k.id
    assert client.get(f"/api/marketing/seo/artifacts/{aid}", headers=auth).json()["data"]["counts"]["critical"] >= 1
    assert [x["id"] for x in client.get("/api/marketing/seo/artifacts?kind=audit", headers=auth).json()] == [aid]
    assert client.post(f"/api/marketing/seo/artifacts/{kid}/handoff", json={"project_id": pid}, headers=auth).status_code == 422
    assert client.post(f"/api/marketing/seo/artifacts/{aid}/handoff", json={"project_id": "tidak-ada"}, headers=auth).status_code == 404
    r = client.post(f"/api/marketing/seo/artifacts/{aid}/handoff", json={"project_id": pid}, headers=auth)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    t = client.get(f"/api/tasks/{r.json()['task_id']}", headers=auth).json()
    assert t["role"] == "developer" and t["action_type"] == "code_change" and "noindex" in t["description"]
    assert client.post(f"/api/marketing/seo/artifacts/{aid}/handoff", json={"project_id": pid}, headers=auth).status_code == 409
    assert client.get("/api/marketing/seo/artifacts/tidak-ada", headers=auth).status_code == 404


def test_seo_campaign_lifecycle_and_keyword_approval(client, auth, settings):
    assert client.get("/api/marketing/seo/campaigns").status_code == 401
    payload = {"name": "SEO Bandung", "website_url": "https://example.com/", "target_country": "ID", "target_language": "id",
               "primary_keywords": ["jasa website bandung"], "objective": "organic_traffic", "api_budget_idr": 25000,
               "external_budget_idr": 0, "autonomy": "read_only"}
    assert client.post("/api/marketing/seo/campaigns", json={**payload, "website_url": "http://127.0.0.1/"}, headers=auth).status_code == 422
    created = client.post("/api/marketing/seo/campaigns", json=payload, headers=auth)
    assert created.status_code == 201
    campaign = created.json()
    assert campaign["status"] == "draft" and campaign["allowed_domains"] == ["example.com"]
    assert campaign["external_integrations"] == {"search_console": "not_connected", "analytics": "not_connected"}
    cid = campaign["id"]
    from app.db.session import create_db_engine, create_session_factory
    sf = create_session_factory(create_db_engine(settings.database_url))
    with sf() as s:
        artifact = MarketingArtifact(kind="audit", title="Audit test", summary="observed", data={"campaign_id": cid})
        s.add(artifact)
        s.flush()
        recommendation = SeoRecommendation(campaign_id=cid, artifact_id=artifact.id, finding_id="title_missing", category="title_missing",
            title="Title missing", severity="critical", evidence={"page": "/"}, recommendation="Add an accurate title",
            impact_basis="unknown", confidence="observed", effort="unknown", risk="unknown", dependencies=[],
            acceptance_criteria=["Repeat audit"], verification_method="Repeat audit", priority_order=1)
        s.add(recommendation)
        s.commit()
        rid = recommendation.id
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/tasks/audit", headers=auth).status_code == 422
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/tasks/keywords", json={}, headers=auth).status_code == 422
    queued = client.post(f"/api/marketing/seo/campaigns/{cid}/tasks/keywords", json={"material": "Kami menawarkan layanan pembuatan website untuk klinik."}, headers=auth)
    assert queued.status_code == 201 and client.get(f"/api/tasks/{queued.json()['task_id']}", headers=auth).json()["action_type"] == "keyword_research"
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/tasks/keywords", json={"material": "Materi yang sama"}, headers=auth).status_code == 409
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/status", json={"status": "active"}, headers=auth).status_code == 409
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/status", json={"status": "planning"}, headers=auth).status_code == 200
    added = client.post(f"/api/marketing/seo/campaigns/{cid}/keywords", json={"keyword": "  jasa   website bandung  ", "intent": "commercial"}, headers=auth)
    assert added.status_code == 201 and added.json()["keyword"] == "jasa website bandung"
    assert added.json()["volume"] is None and added.json()["competition"] is None and added.json()["approval_status"] == "pending"
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/keywords", json={"keyword": "jasa website bandung"}, headers=auth).status_code == 409
    kid = added.json()["id"]
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/tasks/content-plan", json={"keyword_id": kid}, headers=auth).status_code == 409
    approved = client.post(f"/api/marketing/seo/campaigns/{cid}/keywords/{kid}/decision", json={"status": "approved"}, headers=auth)
    assert approved.status_code == 200 and approved.json()["approved_at"]
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/keywords/decisions", json={"keyword_ids": [kid], "status": "rejected"}, headers=auth).status_code == 200
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/keywords/{kid}/decision", json={"status": "approved"}, headers=auth).status_code == 200
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/tasks/content-plan", json={"keyword_id": kid}, headers=auth).status_code == 422
    assert client.get(f"/api/marketing/seo/campaigns/{cid}", headers=auth).json()["keywords"][0]["approval_status"] == "approved"
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/recommendations/{rid}/decision", json={"status": "completed"}, headers=auth).status_code == 409
    assert client.post(f"/api/marketing/seo/campaigns/{cid}/recommendations/{rid}/decision", json={"status": "approved"}, headers=auth).status_code == 200
    exported = client.get(f"/api/marketing/seo/campaigns/{cid}/report", headers=auth)
    assert exported.status_code == 200 and exported.headers["content-disposition"].endswith(f"seo-campaign-{cid}.json\"")
    assert exported.json()["data_quality"]["gsc"] == "not_connected"
    assert exported.json()["campaign"]["recommendations"][0]["impact_basis"] == "unknown"


def test_campaign_keyword_suggestions_persist_with_unavailable_metrics(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=KW_JSON))
    pid = make_project(env)
    with env.sf() as s:
        campaign = SeoCampaign(name="uji", website_url="https://example.test", allowed_domains=["example.test"], primary_keywords=[],
                               objective="organic_traffic", baseline={}, api_budget_idr=0, external_budget_idr=0,
                               autonomy="read_only", approval_policy={}, status="draft")
        s.add(campaign)
        s.commit()
        cid = campaign.id
    tid = run_task(env, pid, "seo_specialist", "keyword_research", {"campaign_id": cid, "topic": "jasa website", "material": "Data: jasa website 500 per bulan sedang."})
    assert get(env, tid).status == "completed"
    with env.sf() as s:
        rows = list(s.query(SeoKeyword).filter_by(campaign_id=cid).all())
        assert len(rows) == 2 and all(k.approval_status == "pending" and k.source == "ai" for k in rows)
        assert rows[0].volume is None or rows[0].volume == 500
        assert rows[1].volume is None and rows[1].competition is None


def test_campaign_budget_blocks_paid_generation_when_estimate_exceeds_limit(migrated_db, tmp_path):
    from types import SimpleNamespace
    from app.tasks.executors import ExecutionContext, ExecutorBlocked
    env = build_env(migrated_db, tmp_path)
    with env.sf() as s:
        campaign = SeoCampaign(name="budget", website_url="https://example.test", allowed_domains=["example.test"], primary_keywords=[],
            objective="organic_traffic", baseline={}, api_budget_idr=1, external_budget_idr=0, autonomy="read_only", approval_policy={}, status="draft")
        s.add(campaign)
        s.add(ModelCapability(provider="paid", model_id="priced-model", available=True, is_paid=True,
                              cost_estimate_idr_per_1k=1000, validation_status="unvalidated"))
        s.commit()
        cid = campaign.id

    class Router:
        async def choose(self, *_args):
            return SimpleNamespace(provider="paid", model="priced-model", num_ctx=4096)

    class Gateway:
        async def generate(self, *_args, **_kwargs):
            raise AssertionError("paid model should be blocked before generation")

    ctx = ExecutionContext(task=SimpleNamespace(role="seo_specialist", params={"campaign_id": cid}), attempt_id="attempt",
                           session_factory=env.sf, gateway=Gateway(), router=Router(), settings=None, storage=None)
    async def generate():
        with pytest.raises(ExecutorBlocked, match="estimasi biaya melewati"):
            await ctx.generate("system", "prompt", max_tokens=10)
    asyncio.run(generate())
