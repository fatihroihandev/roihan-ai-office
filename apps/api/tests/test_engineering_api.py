import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.sandbox.wsl import WslSandbox
from app.tasks.executors import default_executors
from tests.fakes import FakeProvider, FakeSandbox, pytest_fail, pytest_ok
from tests.test_engineering_agents import CALC, TEST_CALC, gen
from tests.test_sandbox_wsl import Runner

import asyncio


def make_client(settings, provider=None, sandbox=None):
    cfg = settings.model_copy(update={"ollama_enabled": True, "retry_backoff_base_s": 0.0})
    app = create_app(cfg, providers={"ollama": provider or FakeProvider()}, executors=default_executors(), sandbox=sandbox)
    return TestClient(app)


def drain(client):
    worker = client.app.state.worker
    for _ in range(20):
        if not asyncio.run(worker.run_once()):
            return


def project(client, auth):
    return client.post("/api/projects", json={"name": "Proyek"}, headers=auth).json()["id"]


def queue(client, auth, pid, **kw):
    body = {"project_id": pid, "title": "Buat kalkulator", "role": "developer", "action_type": "code_change", **kw}
    t = client.post("/api/tasks", json=body, headers=auth).json()
    client.post(f"/api/tasks/{t['id']}/queue", headers=auth)
    return t["id"]


def test_endpoints_require_token(settings):
    c = make_client(settings)
    for method, path in [("get", "/api/sandbox"), ("post", "/api/sandbox/selftest"), ("get", "/api/projects/x/workspace"),
                         ("get", "/api/projects/x/workspace/file?path=a.py")]:
        assert getattr(c, method)(path).status_code == 401, path


def test_sandbox_status_when_not_configured(settings, auth):
    c = make_client(settings)
    body = c.get("/api/sandbox", headers=auth).json()
    assert (body["configured_backend"], body["backend"], body["available"], body["reason"]) == ("none", "none", False, "sandbox_disabled")
    assert body["limits"] == {"timeout_s": 60, "memory_mb": 768, "max_output_kb": 64, "network": False}
    st = c.post("/api/sandbox/selftest", headers=auth).json()
    assert st["passed"] is False and st["reason"] == "sandbox_disabled"


def test_sandbox_status_and_selftest_report_with_wsl_backend(settings, auth):
    sb = WslSandbox("Ubuntu", runner=Runner())
    c = make_client(settings, sandbox=sb)
    body = c.get("/api/sandbox", headers=auth).json()
    assert body["available"] is True and body["backend"] == "wsl" and body["selftest"]["passed"] is True
    assert {x["name"] for x in body["selftest"]["checks"]} >= {"no_network", "non_root", "memory_limit"}
    rerun = c.post("/api/sandbox/selftest", headers=auth).json()
    assert rerun["passed"] is True and rerun["ran_at"]


def test_failed_selftest_is_reported_and_gates_execution(settings, auth):
    r = Runner()
    r.fail_case = "socket.create_connection"
    c = make_client(settings, sandbox=WslSandbox("Ubuntu", runner=r))
    body = c.get("/api/sandbox", headers=auth).json()
    assert body["available"] is False and body["reason"] == "isolation_selftest_failed"
    failed = [x["name"] for x in body["selftest"]["checks"] if not x["passed"]]
    assert failed == ["no_network"]


def test_workspace_endpoints_show_files_commits_and_content(settings, auth):
    prov = FakeProvider(reply=[gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC), summary="calc")])
    c = make_client(settings, prov, FakeSandbox(pytest=[pytest_ok("test_add")]))
    pid = project(c, auth)
    assert c.get(f"/api/projects/{pid}/workspace", headers=auth).json() == {"files": [], "commits": []}
    queue(c, auth, pid)
    drain(c)
    ws = c.get(f"/api/projects/{pid}/workspace", headers=auth).json()
    assert [f["path"] for f in ws["files"]] == ["calc.py", "tests/test_calc.py"]
    assert ws["commits"][0]["message"] == "Buat kalkulator" and ws["commits"][0]["author"] == "developer agent"
    f = c.get(f"/api/projects/{pid}/workspace/file?path=calc.py", headers=auth).json()
    assert f["content"] == CALC and f["size"] == len(CALC)


@pytest.mark.parametrize("path", ["../../../etc/passwd", "..", ".git/config", ".gitignore", "/etc/passwd", "missing.py", "a\\b", "C:/x"])
def test_workspace_file_endpoint_cannot_escape_or_read_hidden(settings, auth, path):
    c = make_client(settings, FakeProvider(reply=[gen(("calc.py", CALC))]), FakeSandbox())
    pid = project(c, auth)
    queue(c, auth, pid)
    drain(c)
    assert c.get(f"/api/projects/{pid}/workspace/file", params={"path": path}, headers=auth).status_code == 404


def test_workspace_of_unknown_or_deleted_project(settings, auth):
    c = make_client(settings)
    assert c.get("/api/projects/tidak-ada/workspace", headers=auth).status_code == 404
    pid = project(c, auth)
    c.delete(f"/api/projects/{pid}", headers=auth)
    assert c.get(f"/api/projects/{pid}/workspace", headers=auth).status_code == 404


def test_task_detail_exposes_executions_and_test_results(settings, auth):
    sb = FakeSandbox(pytest=[pytest_fail(failed=[("test_add", "assert 3 == 4")], passed=("test_ok",)), pytest_ok("test_add", "test_ok")])
    prov = FakeProvider(reply=[gen(("calc.py", "bad"), ("tests/test_calc.py", TEST_CALC)), gen(("calc.py", CALC))])
    c = make_client(settings, prov, sb)
    pid = project(c, auth)
    tid = queue(c, auth, pid)
    drain(c)
    d = c.get(f"/api/tasks/{tid}", headers=auth).json()
    assert d["status"] == "completed" and d["verification"]["fix_rounds"] == 1
    assert [e["kind"] for e in d["executions"]] == ["compile", "pytest", "compile", "pytest"]
    assert all(e["sandbox"] == "fake" and e["argv"][0] == "python3" for e in d["executions"])
    assert [(r["status"], r["total"]) for r in d["test_runs"]] == [("failed", 2), ("passed", 2)]
    failed = d["test_runs"][0]["results"]
    assert {(x["name"], x["outcome"]) for x in failed} == {("test_add", "failed"), ("test_ok", "passed")}
    assert next(x for x in failed if x["outcome"] == "failed")["message"] == "assert 3 == 4"
    assert d["result"]["commit"] and d["result"]["files"][0]["path"] == "calc.py"


def test_blocked_task_reports_reason_through_api(settings, auth):
    c = make_client(settings, FakeProvider(), FakeSandbox(available=False, reason="isolation_selftest_failed", message="Uji isolasi gagal"))
    pid = project(c, auth)
    tid = queue(c, auth, pid)
    drain(c)
    d = c.get(f"/api/tasks/{tid}", headers=auth).json()
    assert (d["status"], d["blocked_reason"], d["last_error"]) == ("blocked", "isolation_selftest_failed", "Uji isolasi gagal")
    assert d["executions"] == []
