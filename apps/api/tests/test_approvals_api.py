import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.tasks.executors import ExecutorOutcome
from tests.fakes import FakeProvider


class Recorder:
    idempotent = True

    def __init__(self):
        self.runs = []

    async def run(self, ctx):
        self.runs.append(ctx.task.id)
        return ExecutorOutcome("ok", True, {"method": "uji", "passed": True}, {"output": "ok"})


@pytest.fixture
def rec():
    return Recorder()


@pytest.fixture
def client(settings, rec):
    cfg = settings.model_copy(update={"ollama_enabled": True})
    return TestClient(create_app(cfg, providers={"ollama": FakeProvider()}, executors={"analyst": rec}))


def drain(client):
    for _ in range(10):
        if not asyncio.run(client.app.state.worker.run_once()):
            return


@pytest.fixture
def pid(client, auth):
    return client.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]


def risky(client, auth, pid, **kw):
    t = client.post("/api/tasks", json={"project_id": pid, "title": "Bayar vendor", "role": "analyst", "action_type": "spend",
                                        "description": "Bayar", **kw}, headers=auth).json()
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    return t["id"]


def pending(client, auth):
    return client.get("/api/approvals?status=pending", headers=auth).json()


def test_endpoints_require_token(client):
    for method, path in [("get", "/api/approvals"), ("get", "/api/approvals/x"), ("post", "/api/approvals/x/approve"),
                         ("post", "/api/approvals/x/reject")]:
        assert getattr(client, method)(path).status_code == 401, path


def test_list_filter_and_get(client, auth, pid):
    a, b = risky(client, auth, pid), risky(client, auth, pid)
    rows = pending(client, auth)
    assert {r["task_id"] for r in rows} == {a, b} and all(r["status"] == "pending" and r["risk_level"] == "critical" for r in rows)
    r = rows[0]
    assert r["payload"]["action_type"] == "spend" and r["payload"]["title"] == "Bayar vendor" and r["expires_at"]
    assert client.get(f"/api/approvals/{r['id']}", headers=auth).json()["id"] == r["id"]
    assert client.get(f"/api/approvals?task_id={a}", headers=auth).json()[0]["task_id"] == a
    assert client.get(f"/api/approvals?project_id={pid}&status=approved", headers=auth).json() == []
    assert client.get("/api/approvals?status=ngawur", headers=auth).status_code == 422
    assert client.get("/api/approvals/tidak-ada", headers=auth).status_code == 404


def test_approve_through_api_runs_the_task(client, auth, pid, rec):
    tid = risky(client, auth, pid)
    drain(client)
    assert rec.runs == []                                                 # belum disetujui: tidak jalan
    ap = pending(client, auth)[0]
    r = client.post(f"/api/approvals/{ap['id']}/approve", json={"reason": "ok"}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_by"] == "ceo" and r.json()["decision_reason"] == "ok"
    assert client.get(f"/api/tasks/{tid}", headers=auth).json()["status"] == "queued"
    drain(client)
    d = client.get(f"/api/tasks/{tid}", headers=auth).json()
    assert d["status"] == "completed" and rec.runs == [tid]
    assert [(a["status"], bool(a["used_at"])) for a in d["approvals"]] == [("approved", True)]


def test_reject_through_api_cancels_task(client, auth, pid, rec):
    tid = risky(client, auth, pid)
    ap = pending(client, auth)[0]
    r = client.post(f"/api/approvals/{ap['id']}/reject", json={"reason": "terlalu mahal"}, headers=auth)
    assert r.json()["status"] == "rejected" and r.json()["decision_reason"] == "terlalu mahal"
    assert client.get(f"/api/tasks/{tid}", headers=auth).json()["status"] == "cancelled"
    drain(client)
    assert rec.runs == []


def test_decision_without_body_is_allowed_and_second_decision_conflicts(client, auth, pid):
    risky(client, auth, pid)
    ap = pending(client, auth)[0]
    assert client.post(f"/api/approvals/{ap['id']}/approve", headers=auth).status_code == 200
    again = client.post(f"/api/approvals/{ap['id']}/reject", headers=auth)
    assert again.status_code == 409 and "approved" in again.json()["detail"]


def test_expired_approval_conflicts_and_is_marked_expired(client, auth, pid):
    from datetime import timedelta
    from sqlalchemy import select
    from app.db.base import utcnow
    from app.db.models import Approval
    tid = risky(client, auth, pid)
    with client.app.state.session_factory() as s:
        s.scalars(select(Approval)).first().expires_at = utcnow() - timedelta(minutes=1)
        s.commit()
    ap = pending(client, auth)[0]
    r = client.post(f"/api/approvals/{ap['id']}/approve", headers=auth)
    assert r.status_code == 409 and "kedaluwarsa" in r.json()["detail"]
    assert client.get(f"/api/approvals/{ap['id']}", headers=auth).json()["status"] == "expired"
    assert client.get(f"/api/tasks/{tid}", headers=auth).json()["status"] == "cancelled"


def test_content_change_between_request_and_decision_conflicts(client, auth, pid):
    from sqlalchemy import select
    from app.db.models import Task
    tid = risky(client, auth, pid)
    ap = pending(client, auth)[0]
    with client.app.state.session_factory() as s:
        s.get(Task, tid).title = "Bayar vendor lain"
        s.commit()
    r = client.post(f"/api/approvals/{ap['id']}/approve", headers=auth)
    assert r.status_code == 409 and "berubah" in r.json()["detail"]
    assert client.get(f"/api/approvals/{ap['id']}", headers=auth).json()["status"] == "cancelled"


def test_events_announce_required_and_resolved_approvals(client, auth, pid):
    risky(client, auth, pid)
    ap = pending(client, auth)[0]
    client.post(f"/api/approvals/{ap['id']}/approve", headers=auth)
    evs = client.get("/api/events", headers=auth).json()
    types = [e["type"] for e in evs]
    assert "approval.required" in types and "approval.resolved" in types
    required = next(e for e in evs if e["type"] == "approval.required")
    assert required["payload"]["approval_id"] == ap["id"]
    resolved = next(e for e in evs if e["type"] == "approval.resolved")
    assert resolved["payload"]["status"] == "approved" and resolved["payload"]["decided_by"] == "ceo"


def test_low_and_medium_risk_tasks_need_no_approval(client, auth, pid, rec):
    t = client.post("/api/tasks", json={"project_id": pid, "title": "Analisis", "role": "analyst", "action_type": "analysis"}, headers=auth).json()
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    assert pending(client, auth) == []
    drain(client)
    assert rec.runs == [t["id"]]
