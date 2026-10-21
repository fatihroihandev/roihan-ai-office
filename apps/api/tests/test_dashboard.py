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
