import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from app.providers.base import ProviderError, ProviderErrorKind as K
from app.tasks.executors import default_executors
from tests.fakes import FakeProvider
from tests.test_manager import plan_json


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def client(settings, provider):
    settings = settings.model_copy(update={"ollama_enabled": True, "retry_backoff_base_s": 0.0})
    return TestClient(create_app(settings, providers={"ollama": provider}, executors=default_executors()))


@pytest.fixture
def pid(client, auth):
    return client.post("/api/projects", json={"name": "Proyek"}, headers=auth).json()["id"]


def run_worker(client, times=20):
    worker = client.app.state.worker
    for _ in range(times):
        if not asyncio.run(worker.run_once()):
            return


def mk(client, auth, pid, **kw):
    body = {"project_id": pid, "title": "Analisis", "role": "analyst", "action_type": "analysis", **kw}
    r = client.post("/api/tasks", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def test_endpoints_require_token(client):
    for method, path in [("get", "/api/tasks"), ("post", "/api/tasks"), ("get", "/api/tasks/x"), ("post", "/api/tasks/x/queue"),
                         ("post", "/api/tasks/x/cancel"), ("post", "/api/tasks/x/retry"), ("get", "/api/agents"),
                         ("get", "/api/worker"), ("get", "/api/events"), ("post", "/api/events/ticket"),
                         ("post", "/api/projects/x/plan"), ("post", "/api/projects/x/tasks/queue-drafts")]:
        assert getattr(client, method)(path).status_code == 401, path


def test_create_list_filter_and_detail(client, auth, pid):
    t = mk(client, auth, pid, acceptance_criteria=["a"], priority=3)
    assert t["status"] == "draft" and t["risk_level"] == "low" and t["difficulty_category"] == "medium"
    mk(client, auth, pid, title="Dev", role="developer", action_type="code_change")
    assert len(client.get("/api/tasks", headers=auth).json()) == 2
    assert [x["role"] for x in client.get(f"/api/tasks?project_id={pid}&role=developer", headers=auth).json()] == ["developer"]
    assert client.get("/api/tasks?status=draft", headers=auth).json().__len__() == 2
    assert client.get("/api/tasks?status=ngawur", headers=auth).status_code == 422
    d = client.get(f"/api/tasks/{t['id']}", headers=auth).json()
    assert d["attempts"] == [] and d["events"][0]["type"] == "task.created" and d["depends_on"] == []
    assert client.get("/api/tasks/tidak-ada", headers=auth).status_code == 404


def test_create_validation(client, auth, pid):
    post = lambda **kw: client.post("/api/tasks", json={"project_id": pid, "title": "T", "role": "analyst", "action_type": "analysis", **kw}, headers=auth)  # noqa: E731
    assert post(role="tukang").status_code == 422
    assert post(action_type="hack").status_code == 422
    assert post(title="  ").status_code == 422
    assert post(depends_on=["tidak-ada"]).status_code == 409
    assert client.post("/api/tasks", json={"project_id": "x", "title": "T", "role": "analyst", "action_type": "analysis"}, headers=auth).status_code == 404


def test_full_lifecycle_through_api(client, auth, pid):
    t = mk(client, auth, pid)
    assert client.post(f"/api/tasks/{t['id']}/queue", headers=auth).json()["status"] == "queued"
    assert client.post(f"/api/tasks/{t['id']}/queue", headers=auth).status_code == 409   # bukan draft lagi
    run_worker(client)
    d = client.get(f"/api/tasks/{t['id']}", headers=auth).json()
    assert d["status"] == "completed" and d["result"]["output"] and d["verification"]["passed"] is True
    assert [e["to_status"] for e in d["events"]] == ["draft", "queued", "running", "completed"]
    assert d["attempts"][0]["status"] == "succeeded" and d["routing"][0]["model"] == "fake-model:1b"
    assert client.post(f"/api/tasks/{t['id']}/cancel", headers=auth).status_code == 409   # completed: terminal
    assert client.post(f"/api/tasks/{t['id']}/retry", headers=auth).status_code == 409


def test_plan_endpoint_manager_creates_drafts_and_queue_drafts(client, auth, pid, provider):
    provider.reply = [plan_json()]
    r = client.post(f"/api/projects/{pid}/plan", json={"goal": "Bangun CRM"}, headers=auth)
    assert r.status_code == 201 and r.json()["role"] == "manager" and r.json()["status"] == "queued"
    run_worker(client)
    tasks = client.get(f"/api/tasks?project_id={pid}", headers=auth).json()
    assert sorted(t["status"] for t in tasks) == ["completed", "draft", "draft", "draft"]
    queued = client.post(f"/api/projects/{pid}/tasks/queue-drafts", headers=auth).json()
    assert sorted(t["status"] for t in queued) == ["pending_approval", "queued", "queued"]
    assert client.post("/api/projects/x/plan", json={"goal": "g"}, headers=auth).status_code == 404
    assert client.post(f"/api/projects/{pid}/plan", json={"goal": "  "}, headers=auth).status_code == 422


def test_retry_endpoint_after_failure(client, auth, pid, provider):
    provider.error = ProviderError(K.invalid_request, "salah")
    t = mk(client, auth, pid)
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    run_worker(client)
    assert client.get(f"/api/tasks/{t['id']}", headers=auth).json()["status"] == "failed"
    provider.error = None
    assert client.post(f"/api/tasks/{t['id']}/retry", headers=auth).json()["status"] == "queued"
    run_worker(client)
    assert client.get(f"/api/tasks/{t['id']}", headers=auth).json()["status"] == "completed"


def test_cancel_queued_task_and_blocked_dependents(client, auth, pid):
    a = mk(client, auth, pid, title="A")
    b = mk(client, auth, pid, title="B", depends_on=[a["id"]])
    for x in (a, b):
        client.post(f"/api/tasks/{x['id']}/queue", headers=auth)
    assert client.post(f"/api/tasks/{a['id']}/cancel", headers=auth).json()["status"] == "cancelled"
    run_worker(client)
    assert client.get(f"/api/tasks/{b['id']}", headers=auth).json()["blocked_reason"] == "dependency_failed"


def test_cancel_running_task_through_api(settings, auth):
    slow = FakeProvider(delay=5)
    cfg = settings.model_copy(update={"ollama_enabled": True, "worker_enabled": True, "worker_poll_interval_s": 0.05})
    app = create_app(cfg, providers={"ollama": slow}, executors=default_executors())
    with TestClient(app) as c:      # lifespan aktif agar loop worker berjalan di event loop server
        pid = c.post("/api/projects", json={"name": "P"}, headers=auth).json()["id"]
        t = mk(c, auth, pid)
        c.post(f"/api/tasks/{t['id']}/queue", headers=auth)
        import time
        for _ in range(100):
            if app.state.worker.current_task_id == t["id"]:
                break
            time.sleep(0.05)
        assert app.state.worker.current_task_id == t["id"], "worker tidak mengambil task"
        r = c.post(f"/api/tasks/{t['id']}/cancel", headers=auth)
        assert r.status_code == 200 and r.json()["status"] == "cancelled"


def test_agents_status_is_derived_from_tasks(client, auth, pid):
    base = {a["role"]: a for a in client.get("/api/agents", headers=auth).json()}
    assert len(base) == 10 and {a["status"] for a in base.values()} == {"idle"}
    assert base["manager"]["department"] == "coordination" and base["qa"]["department"] == "engineering"
    mk(client, auth, pid, role="developer", action_type="code_change")
    t = mk(client, auth, pid, role="sales_client_relations", action_type="external_outreach")
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    s = {a["role"]: a for a in client.get("/api/agents", headers=auth).json()}
    assert s["developer"]["status"] == "idle"                                # draft tidak membuat agent sibuk
    assert s["sales_client_relations"]["status"] == "awaiting_approval"
    d = mk(client, auth, pid, role="qa", action_type="run_tests")
    client.post(f"/api/tasks/{d['id']}/queue", headers=auth)
    run_worker(client)                                                       # qa tidak punya executor -> blocked
    assert {a["role"]: a["status"] for a in client.get("/api/agents", headers=auth).json()}["qa"] == "blocked"
    a = mk(client, auth, pid)
    client.post(f"/api/tasks/{a['id']}/queue", headers=auth)
    run_worker(client)
    assert {x["role"]: x["status"] for x in client.get("/api/agents", headers=auth).json()}["analyst"] == "completed"


def test_worker_status_endpoint(client, auth, pid):
    mk(client, auth, pid)
    w = client.get("/api/worker", headers=auth).json()
    assert w["max_concurrent_tasks"] == 1 and w["counts"]["draft"] == 1 and w["current_task_id"] is None


def test_events_rest_catch_up(client, auth, pid):
    t = mk(client, auth, pid)
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    evs = client.get("/api/events", headers=auth).json()
    assert [e["type"] for e in evs] == ["task.created", "task.queued"]
    assert client.get(f"/api/events?since={evs[0]['seq']}", headers=auth).json()[0]["type"] == "task.queued"
    assert client.get("/api/events?since=999999", headers=auth).json() == []


# ------------------------------------------------------------------ WebSocket

def ticket(client, auth):
    return client.post("/api/events/ticket", headers=auth).json()["ticket"]


def test_websocket_streams_events_after_connect(client, auth, pid):
    with client.websocket_connect(f"/api/ws?ticket={ticket(client, auth)}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        t = mk(client, auth, pid)
        client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
        got = [ws.receive_json(), ws.receive_json()]
    assert [e["type"] for e in got] == ["task.created", "task.queued"]
    e = got[0]
    assert e["entity_type"] == "task" and e["entity_id"] == t["id"] and e["project_id"] == pid and e["seq"] > hello["last_seq"]
    assert e["occurred_at"] and e["payload"]["to"] == "draft"
    assert got[1]["seq"] > got[0]["seq"]


def test_websocket_replays_from_since_so_client_can_recover_after_reconnect(client, auth, pid):
    t = mk(client, auth, pid)
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    with client.websocket_connect(f"/api/ws?ticket={ticket(client, auth)}&since=0") as ws:
        assert ws.receive_json()["last_seq"] == 0
        assert [ws.receive_json()["type"], ws.receive_json()["type"]] == ["task.created", "task.queued"]


def test_websocket_ticket_is_single_use_and_required(client, auth):
    tk = ticket(client, auth)
    with client.websocket_connect(f"/api/ws?ticket={tk}") as ws:
        assert ws.receive_json()["type"] == "hello"
    for url in (f"/api/ws?ticket={tk}", "/api/ws?ticket=ngawur", "/api/ws"):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(url):
                pass


def test_websocket_rejects_foreign_origin_and_expired_ticket(client, auth):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/ws?ticket={ticket(client, auth)}", headers={"origin": "http://evil.example"}):
            pass
    tk = ticket(client, auth)
    client.app.state.ws_tickets[tk] = 0.0   # kedaluwarsa
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/ws?ticket={tk}"):
            pass
    with client.websocket_connect(f"/api/ws?ticket={ticket(client, auth)}", headers={"origin": "http://localhost:3000"}) as ws:
        assert ws.receive_json()["type"] == "hello"


def test_agent_error_clears_after_a_newer_success_on_same_role(client, auth, pid, provider):
    provider.error = ProviderError(K.invalid_request, "salah")
    bad = mk(client, auth, pid, title="gagal")
    client.post(f"/api/tasks/{bad['id']}/queue", headers=auth)
    run_worker(client)
    status = lambda: {a["role"]: a["status"] for a in client.get("/api/agents", headers=auth).json()}["analyst"]  # noqa: E731
    assert status() == "error"

    provider.error = None
    ok = mk(client, auth, pid, title="berhasil")
    client.post(f"/api/tasks/{ok['id']}/queue", headers=auth)
    run_worker(client)
    assert client.get(f"/api/tasks/{bad['id']}", headers=auth).json()["status"] == "failed"   # tetap tercatat gagal
    assert status() == "completed"                                                              # tetapi agent tidak lagi error
