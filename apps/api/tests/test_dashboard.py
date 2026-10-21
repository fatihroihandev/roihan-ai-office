import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.db.base import utcnow
from app.db.models import ModelUsage
from app.main import create_app
from app.tasks.catalog import ROLES
from app.tasks.executors import ExecutorOutcome
from tests.fakes import FakeProvider


class Slow:
    idempotent = True

    async def run(self, ctx):
        return ExecutorOutcome("ok", True, {"method": "uji", "passed": True}, {"output": "ok"})


@pytest.fixture
def client(settings):
    cfg = settings.model_copy(update={"ollama_enabled": True})
    return TestClient(create_app(cfg, providers={"ollama": FakeProvider()}, executors={"analyst": Slow()}))


@pytest.fixture
def pid(client, auth):
    return client.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]


def drain(client):
    for _ in range(10):
        if not asyncio.run(client.app.state.worker.run_once()):
            return


def task(client, auth, pid, **kw):
    t = client.post("/api/tasks", json={"project_id": pid, "title": "T", "role": "analyst", "action_type": "analysis", **kw}, headers=auth).json()
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    return t["id"]


def test_requires_token(client):
    assert client.get("/api/dashboard").status_code == 401


def test_empty_system_is_all_zero_and_every_agent_is_idle(client, auth):
    d = client.get("/api/dashboard", headers=auth).json()
    assert d["projects_active"] == 0 and d["approvals_pending"] == 0 and d["needs_decision"] == []
    assert sum(d["tasks"].values()) == 0 and d["ai"]["calls_24h"] == 0 and d["ai"]["paid_providers_enabled"] is False
    assert [a["role"] for a in d["agents"]] == list(ROLES) and {a["status"] for a in d["agents"]} == {"idle"}
    assert d["marketing"]["leads_total"] == 0 and d["marketing"]["outbox_waiting"] == 0 and d["worker"]["running"] is True


def test_agents_in_dashboard_equal_the_agents_endpoint(client, auth, pid):
    task(client, auth, pid)
    risky = client.post("/api/tasks", json={"project_id": pid, "title": "Bayar", "role": "analyst", "action_type": "spend"}, headers=auth).json()
    client.post(f"/api/tasks/{risky['id']}/queue", headers=auth)
    d = client.get("/api/dashboard", headers=auth).json()
    assert d["agents"] == client.get("/api/agents", headers=auth).json()
    analyst = next(a for a in d["agents"] if a["role"] == "analyst")
    assert analyst["status"] == "awaiting_approval" and analyst["queued"] == 1
    assert d["approvals_pending"] == 1 and d["needs_decision"][0]["kind"] == "approval" and d["needs_decision"][0]["title"] == "Bayar"


def test_snapshot_is_repeatable_so_a_reloaded_view_matches(client, auth, pid):
    task(client, auth, pid)
    drain(client)
    a = client.get("/api/dashboard", headers=auth).json()
    b = client.get("/api/dashboard", headers=auth).json()
    a.pop("generated_at"), b.pop("generated_at")
    assert a == b
    assert a["tasks"]["completed"] == 1 and next(x for x in a["agents"] if x["role"] == "analyst")["status"] == "completed"


def test_failed_and_blocked_tasks_need_a_decision(client, auth, pid):
    t = client.post("/api/tasks", json={"project_id": pid, "title": "Tanpa executor", "role": "developer", "action_type": "code_change"}, headers=auth).json()
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    drain(client)
    d = client.get("/api/dashboard", headers=auth).json()
    assert [(n["kind"], n["title"]) for n in d["needs_decision"]] == [("task_blocked", "Tanpa executor")]
    assert d["needs_decision"][0]["href"] == f"/tasks/{t['id']}" and d["tasks"]["blocked"] == 1


def test_ai_usage_counts_only_last_24_hours_and_flags_paid_calls(client, auth):
    with client.app.state.session_factory() as s:
        s.add(ModelUsage(provider="ollama", model="m", status="ok", prompt_tokens=10, completion_tokens=5))
        s.add(ModelUsage(provider="ollama", model="m", status="error"))
        s.add(ModelUsage(provider="ollama", model="m", status="ok", prompt_tokens=1000, completion_tokens=1000, created_at=utcnow() - timedelta(days=3)))
        s.commit()
    ai = client.get("/api/dashboard", headers=auth).json()["ai"]
    assert (ai["calls_24h"], ai["errors_24h"], ai["tokens_24h"], ai["paid_calls_24h"]) == (2, 1, 15, 0)


def test_marketing_block_reflects_waiting_items(client, auth):
    from app.db.models import ContentAsset, OutboundMessage, Product
    with client.app.state.session_factory() as s:
        s.add(Product(id="p1", name="K"))
        s.flush()
        s.add(ContentAsset(product_id="p1", kind="social_post", channel="blog", title="t", body="b", body_hash="h", status="ready_for_review"))
        s.add(OutboundMessage(kind="content", ref_id="x", channel="blog", body_hash="h", task_id="t", approval_id="a"))
        s.commit()
    m = client.get("/api/dashboard", headers=auth).json()["marketing"]
    assert (m["content_ready"], m["outbox_waiting"], m["outreach_ready"]) == (1, 1, 0)


# ================================================================== insights (grafik)

def _task(c, auth, pid, **kw):
    return c.post("/api/tasks", json={"project_id": pid, "title": kw.pop("title", "T"), "role": kw.pop("role", "analyst"), "action_type": "analysis", **kw}, headers=auth).json()["id"]


def test_insights_requires_token_and_validates_range(client, auth):
    assert client.get("/api/dashboard/insights").status_code == 401
    assert client.get("/api/dashboard/insights?days=3", headers=auth).status_code == 422
    assert client.get("/api/dashboard/insights?days=61", headers=auth).status_code == 422


def test_insights_empty_system_uses_null_not_zero_for_unknowns(client, auth):
    d = client.get("/api/dashboard/insights", headers=auth).json()
    assert len(d["throughput"]) == 14 and all(x["created"] == x["completed"] == x["failed"] == 0 for x in d["throughput"])
    assert d["quality"] == {"finished_7d": 0, "success_rate_7d": None, "avg_minutes": None}
    assert d["projects"] == [] and d["activity"] == [] and len(d["ai_hourly"]) == 24
    assert [s["stage"] for s in d["funnel"]["stages"]] == ["new", "qualified", "contacted", "meeting", "opportunity", "won"]
    assert d["workload"][0]["role"] == "manager" and len(d["workload"]) == 10


def test_insights_progress_throughput_and_quality_from_real_tasks(client, auth, pid):
    for i in range(3):
        task(client, auth, pid, title=f"T{i}")
    drain(client)                                               # 3 task analyst selesai
    t = client.post("/api/tasks", json={"project_id": pid, "title": "Tanpa executor", "role": "developer", "action_type": "code_change"}, headers=auth).json()
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    drain(client)                                               # terblokir
    d = client.get("/api/dashboard/insights", headers=auth).json()
    proj = d["projects"][0]
    assert (proj["total"], proj["counts"]["completed"], proj["counts"]["blocked"], proj["percent"]) == (4, 3, 1, 75)
    today = d["throughput"][-1]
    assert (today["created"], today["completed"], today["failed"]) == (4, 3, 0)
    assert d["quality"]["finished_7d"] == 3 and d["quality"]["success_rate_7d"] == 1.0 and d["quality"]["avg_minutes"] is not None
    wl = {w["role"]: w for w in d["workload"]}
    assert wl["analyst"]["completed_7d"] == 3 and wl["developer"]["blocked"] == 1
    assert d["activity"][0]["seq"] > d["activity"][-1]["seq"] and d["activity"][0]["project"] == "P"


def test_insights_ai_hourly_buckets_and_marketing_funnel(client, auth):
    from app.db.models import Company, Lead, LeadSource
    with client.app.state.session_factory() as s:
        s.add(ModelUsage(provider="ollama", model="m", status="ok", prompt_tokens=10, completion_tokens=5))
        s.add(ModelUsage(provider="ollama", model="m", status="error"))
        co = Company(name="A", normalized_name="a")
        src = LeadSource(source_type="manual", collected_at=utcnow(), collected_by="ceo")
        s.add_all([co, src])
        s.flush()
        for st in ("new", "qualified", "meeting", "won", "lost"):
            s.add(Lead(company_id=co.id, source_id=src.id, status=st, basis="legitimate_interest_b2b", collected_at=utcnow()))
        s.commit()
    d = client.get("/api/dashboard/insights", headers=auth).json()
    assert sum(b["calls"] for b in d["ai_hourly"]) == 2 and d["ai_hourly"][-1]["tokens"] == 15 and d["ai_hourly"][-1]["errors"] == 1
    st = {x["stage"]: x for x in d["funnel"]["stages"]}
    assert (st["new"]["reached"], st["qualified"]["reached"], st["meeting"]["reached"], st["won"]["reached"]) == (4, 3, 2, 1)
    assert st["contacted"]["now"] == 0 and d["funnel"]["out"]["lost"] == 1
