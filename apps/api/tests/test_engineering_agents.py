import json
import subprocess

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.models import Execution, Task, TestResult, TestRun
from app.engineering.agents import ExecutorError, parse_generated, run_in_sandbox
from app.sandbox.base import DisabledSandbox, ExecResult
from app.tasks.executors import ExecutionContext
from app.workspace import git
from app.workspace.files import CODE_EXTS, WorkspaceFiles
from tests.fakes import OK_COMPILE, FakeProvider, FakeSandbox, junit_xml, pytest_fail, pytest_ok
from tests.helpers import add_task, build_env, drain, get, make_project

CALC = "def add(a, b):\n    return a + b\n"
TEST_CALC = "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"


def gen(*files, summary="Selesai"):
    return json.dumps({"summary": summary, "files": [{"path": p, "content": c} for p, c in files]})


def workspace(env, pid) -> WorkspaceFiles:
    return WorkspaceFiles(env.storage.project_dir(pid) / "workspace" / "source-code")


def rows(env, model, task_id):
    with env.sf() as s:
        return list(s.scalars(select(model).where(model.task_id == task_id).order_by(model.created_at)))


def dev_env(migrated_db, tmp_path, replies, sandbox=None, **kw):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=list(replies)), sandbox=sandbox or FakeSandbox(), **kw)
    return env, make_project(env)


def dev_task(env, pid, **kw):
    return add_task(env, pid, title="Buat kalkulator", role="developer", action_type="code_change",
                    acceptance_criteria=["add(1,2) == 3"], **kw)


# ================================================================== Developer

def test_developer_writes_verifies_and_commits(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC), summary="Fungsi add dibuat")])
    tid = dev_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert t.status == "completed" and t.attempt_count == 1
    ws = workspace(env, pid)
    assert ws.read("calc.py") == CALC
    assert t.result["files"] == [{"path": "calc.py", "bytes": len(CALC), "new": True}] and t.result["commit"]
    assert "Fungsi add dibuat" in t.result["output"]
    assert t.verification == {"method": "compile", "passed": True, "criteria_checked": False, "tests_run": False, "fix_rounds": 0}
    assert git.head(ws.root) == t.result["commit"] and git.log(ws.root)[0]["message"] == "Buat kalkulator"
    ex = rows(env, Execution, tid)
    assert [e.kind for e in ex] == ["compile"] and ex[0].argv[:3] == ["python3", "-m", "compileall"] and ex[0].status == "ok"
    assert ex[0].sandbox == "fake" and ex[0].duration_ms == 30 and ex[0].attempt_id


def test_developer_runs_existing_tests_and_stores_results(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[pytest_ok("test_add", "test_zero")])
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC))], sandbox=sb)
    tid = dev_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert t.status == "completed" and t.verification["tests_run"] is True and t.verification["tests"]["passed"] == 2
    assert t.verification["method"] == "compile+pytest"
    [run_row] = rows(env, TestRun, tid)
    assert (run_row.status, run_row.source, run_row.total, run_row.passed) == ("passed", "junit", 2, 2)
    with env.sf() as s:
        assert {r.name for r in s.scalars(select(TestResult).where(TestResult.test_run_id == run_row.id))} == {"test_add", "test_zero"}
    assert [e.kind for e in rows(env, Execution, tid)] == ["compile", "pytest"]


def test_developer_fixes_code_after_failed_tests(migrated_db, tmp_path):
    bad = "def add(a, b):\n    return a - b\n"
    sb = FakeSandbox(pytest=[pytest_fail(failed=[("test_add", "assert -1 == 3")]), pytest_ok("test_add")])
    provider_replies = [gen(("calc.py", bad), ("tests/test_calc.py", TEST_CALC)), gen(("calc.py", CALC))]
    env, pid = dev_env(migrated_db, tmp_path, provider_replies, sandbox=sb)
    tid = dev_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert t.status == "completed" and t.verification["fix_rounds"] == 1 and t.attempt_count == 1
    second_prompt = env.provider.calls[1][1].prompt
    assert "VERIFIKASI SEBELUMNYA GAGAL" in second_prompt and "test_add: assert -1 == 3" in second_prompt
    assert "return a - b" in second_prompt                                  # model melihat kode yang salah
    assert workspace(env, pid).read("calc.py") == CALC
    assert [r.status for r in rows(env, TestRun, tid)] == ["failed", "passed"]   # kegagalan pertama tetap tercatat
    assert len(rows(env, Execution, tid)) == 4


def test_developer_compile_error_is_fed_back(migrated_db, tmp_path):
    sb = FakeSandbox(compile=[ExecResult(1, "", "SyntaxError: invalid syntax (calc.py, line 1)", 20), OK_COMPILE])
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", "def add(a, b) return a+b")), gen(("calc.py", CALC))], sandbox=sb)
    tid = dev_task(env, pid)
    drain(env)
    assert get(env, tid).status == "completed"
    assert "Kode tidak dapat dikompilasi" in env.provider.calls[1][1].prompt and "SyntaxError" in env.provider.calls[1][1].prompt


def test_developer_gives_up_after_fix_rounds_and_never_claims_success(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[pytest_fail()])
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC))] * 3, sandbox=sb)
    tid = dev_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.last_error_kind, t.attempt_count, t.result) == ("failed", "verification_failed", 1, None)
    assert len(env.provider.calls) == 3                                   # 1 penulisan + 2 perbaikan
    assert git.log(workspace(env, pid).root)[0]["message"].endswith("[belum terverifikasi]")


def test_developer_is_blocked_without_sandbox_and_writes_nothing(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC))],
                       sandbox=FakeSandbox(available=False, reason="isolation_selftest_failed", message="Uji isolasi gagal"))
    tid = dev_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.blocked_reason, t.last_error) == ("blocked", "isolation_selftest_failed", "Uji isolasi gagal")
    assert env.provider.calls == [] and workspace(env, pid).list() == []


def test_developer_with_default_disabled_sandbox_is_blocked(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[gen(("calc.py", CALC))]))   # sandbox bawaan: tidak ada
    pid = make_project(env)
    tid = dev_task(env, pid)
    drain(env)
    assert (get(env, tid).status, get(env, tid).blocked_reason) == ("blocked", "sandbox_disabled")


def test_blocked_task_can_run_after_sandbox_becomes_available(migrated_db, tmp_path):
    sb = FakeSandbox(available=False)
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC))], sandbox=sb)
    tid = dev_task(env, pid)
    drain(env)
    assert get(env, tid).status == "blocked"
    sb.available = True
    from app.tasks import service
    with env.sf() as s:
        service.requeue_task(s, s.get(Task, tid))
        s.commit()
    drain(env)
    assert get(env, tid).status == "completed"


@pytest.mark.parametrize("path", ["../evil.py", ".git/hooks/pre-commit", ".env", "/etc/cron.d/x.py", "C:/x.py", "a\\b.py", "x.exe", "run.sh", "nul.py"])
def test_unsafe_generated_paths_are_rejected_before_anything_is_written(path, tmp_path):
    ws = WorkspaceFiles(tmp_path / "src")
    with pytest.raises(ExecutorError) as e:
        parse_generated(gen(("ok.py", CALC), (path, "x")), ws, CODE_EXTS)
    assert e.value.kind == "invalid_code_output" and e.value.retryable
    assert ws.list() == []


def test_generated_output_validation_details(tmp_path):
    ws = WorkspaceFiles(tmp_path / "src")
    for bad in ("bukan json", "{}", '{"summary":"x","files":[]}', gen(("a.py", "x"), ("a.py", "y")),
                json.dumps({"summary": "x", "files": [{"path": f"f{i}.py", "content": "x"} for i in range(7)]})):
        with pytest.raises(ExecutorError):
            parse_generated(bad, ws, CODE_EXTS)


def test_invalid_output_is_corrected_once_with_feedback(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [gen(("../evil.py", CALC)), gen(("calc.py", CALC))])
    tid = dev_task(env, pid)
    drain(env)
    assert get(env, tid).status == "completed"
    assert "Path ditolak" in env.provider.calls[1][1].prompt
    assert not (tmp_path / "evil.py").exists() and not (tmp_path / "data" / "evil.py").exists()


def test_persistently_invalid_output_fails_after_bounded_retries(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [gen((".env", "TOKEN=1"))] * 12)
    tid = dev_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.last_error_kind, t.attempt_count) == ("failed", "invalid_code_output", 3)
    assert workspace(env, pid).list() == []


def test_developer_documentation_needs_no_sandbox_and_only_writes_docs(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[gen(("docs/api.md", "# API\n"), summary="Dokumen API")]))
    pid = make_project(env)
    tid = add_task(env, pid, title="Dokumentasi API", role="developer", action_type="documentation")
    drain(env)
    t = get(env, tid)
    assert t.status == "completed" and t.verification["method"] == "files_written"
    assert workspace(env, pid).read("docs/api.md") == "# API\n" and t.result["commit"]
    assert rows(env, Execution, tid) == []

    env2 = build_env(migrated_db, tmp_path / "b", provider=FakeProvider(reply=[gen(("evil.py", "import os"))] * 6))
    pid2 = make_project(env2)
    tid2 = add_task(env2, pid2, title="Dokumen", role="developer", action_type="documentation")
    drain(env2)
    assert get(env2, tid2).status == "failed" and workspace(env2, pid2).list() == []


def test_developer_rejects_unsupported_actions(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [])
    tid = add_task(env, pid, role="developer", action_type="analysis")
    drain(env)
    assert (get(env, tid).status, get(env, tid).last_error_kind) == ("failed", "unsupported_action")


def test_only_allowlisted_commands_ever_reach_the_sandbox(migrated_db, tmp_path):
    sb = FakeSandbox()
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC))], sandbox=sb)
    dev_task(env, pid)
    drain(env)
    assert [r.argv[:3] for r in sb.runs] == [["python3", "-m", "compileall"], ["python3", "-m", "pytest", "-q"][:3]]
    assert all(r.argv[0] == "python3" for r in sb.runs)
    assert all(r.timeout_s == env.settings.sandbox_timeout_s and r.memory_mb == env.settings.sandbox_memory_mb for r in sb.runs)


def test_run_in_sandbox_rejects_commands_outside_allowlist(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [])
    ws = workspace(env, pid)
    ws.write("calc.py", CALC)
    snap = ExecutionContext(task=None, attempt_id="a", session_factory=env.sf, gateway=env.gateway, router=env.router,
                            settings=env.settings, storage=env.storage, sandbox=FakeSandbox())
    for kind, args in (("bash", ["-c", "id"]), ("pip", ["install", "x"]), ("pytest", ["../../etc"]), ("python_file", ["calc.py", "--evil"])):
        with pytest.raises(ExecutorError) as e:
            asyncio_run(run_in_sandbox(snap, ws, kind, args))
        assert e.value.kind == "command_rejected" and e.value.retryable is False


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


def test_execution_logs_are_redacted_and_bounded(migrated_db, tmp_path):
    token = "token-uji-1234567890"
    leaky = ExecResult(0, f"debug TOKEN={token} " + "x" * 30000, f"err {token}", 40)
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC))], sandbox=FakeSandbox(compile=[leaky]))
    tid = dev_task(env, pid)
    drain(env)
    [ex] = rows(env, Execution, tid)
    assert token not in ex.stdout and token not in ex.stderr and "[REDACTED]" in ex.stdout
    assert len(ex.stdout) <= 20000 and ex.output_truncated is True


def test_timeout_is_recorded_as_timeout_status(migrated_db, tmp_path):
    hang = ExecResult(None, "", "", 60000, timed_out=True)
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC))] * 3, sandbox=FakeSandbox(compile=[hang]))
    tid = dev_task(env, pid)
    drain(env)
    ex = rows(env, Execution, tid)
    assert ex and ex[0].status == "timeout" and ex[0].timed_out and ex[0].exit_code is None
    assert get(env, tid).status == "failed" and "batas waktu" in get(env, tid).last_error


# ================================================================== QA

def qa_task(env, pid, **kw):
    return add_task(env, pid, title="Uji kalkulator", role="qa", action_type="run_tests",
                    acceptance_criteria=["add benar"], **kw)


def seeded(migrated_db, tmp_path, replies, sandbox=None):
    env, pid = dev_env(migrated_db, tmp_path, replies, sandbox=sandbox)
    ws = workspace(env, pid)
    git.ensure_repo(ws.root)
    ws.write("calc.py", CALC)
    git.commit_all(ws.root, "awal")
    return env, pid


def test_qa_writes_tests_runs_them_and_records_evidence(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[pytest_ok("test_add", "test_negative", "test_zero")])
    env, pid = seeded(migrated_db, tmp_path, [gen(("tests/test_calc.py", TEST_CALC))], sb)
    tid = qa_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert t.status == "completed" and t.result["tests"] == {"total": 3, "passed": 3, "failed": 0, "errors": 0, "skipped": 0}
    assert t.verification["method"] == "pytest" and t.verification["criteria_checked"] is False
    assert workspace(env, pid).read("tests/test_calc.py") == TEST_CALC
    [run_row] = rows(env, TestRun, tid)
    assert run_row.id == t.result["test_run_id"] and run_row.passed == 3
    [ex] = rows(env, Execution, tid)
    assert ex.kind == "pytest" and ex.argv[-1] == "tests" and run_row.execution_id == ex.id
    assert "calc.py" in env.provider.calls[0][1].prompt                       # QA melihat kode yang diuji
    assert git.log(workspace(env, pid).root)[0]["author"] == "qa agent"


def test_qa_reports_failing_tests_as_failed_task_with_evidence(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[pytest_fail(failed=[("test_add_negative", "assert -1 == 0")], passed=("test_add",))])
    env, pid = seeded(migrated_db, tmp_path, [gen(("tests/test_calc.py", TEST_CALC))], sb)
    tid = qa_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert (t.status, t.last_error_kind, t.attempt_count, t.result) == ("failed", "tests_failed", 1, None)   # tidak diulang otomatis
    assert "test_add_negative" in t.last_error and '"failed": 1' in t.last_error
    [run_row] = rows(env, TestRun, tid)
    assert (run_row.status, run_row.failed, run_row.passed) == ("failed", 1, 1)
    with env.sf() as s:
        failing = s.scalars(select(TestResult).where(TestResult.test_run_id == run_row.id, TestResult.outcome == "failed")).one()
        assert failing.name == "test_add_negative" and failing.message == "assert -1 == 0"


@pytest.mark.parametrize("path", ["calc.py", "tests/sub/test_x.py", "tests/helper.py", "test_x.py", "tests/test_x.txt", "../tests/test_x.py"])
def test_qa_may_only_write_test_files(migrated_db, tmp_path, path):
    env, pid = seeded(migrated_db, tmp_path, [gen((path, "x = 1"))] * 12)
    tid = qa_task(env, pid)
    drain(env)
    assert get(env, tid).status == "failed" and get(env, tid).last_error_kind == "invalid_code_output"
    assert workspace(env, pid).read("calc.py") == CALC                         # kode produksi tidak tersentuh


def test_qa_never_modifies_source_code(migrated_db, tmp_path):
    env, pid = seeded(migrated_db, tmp_path, [gen(("calc.py", "def add(a, b):\n    return 0\n"))] * 12)
    qa_task(env, pid)
    drain(env)
    assert workspace(env, pid).read("calc.py") == CALC


def test_qa_with_nothing_to_test(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [gen(("tests/test_x.py", "x"))])
    tid = qa_task(env, pid)
    drain(env)
    assert (get(env, tid).status, get(env, tid).last_error_kind) == ("failed", "nothing_to_test")
    assert env.provider.calls == []


def test_qa_with_only_test_files_has_nothing_to_test(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [])
    workspace(env, pid).write("tests/test_x.py", TEST_CALC)
    tid = qa_task(env, pid)
    drain(env)
    assert get(env, tid).last_error_kind == "nothing_to_test"


def test_qa_is_blocked_without_sandbox(migrated_db, tmp_path):
    env, pid = seeded(migrated_db, tmp_path, [gen(("tests/test_calc.py", TEST_CALC))], FakeSandbox(available=False))
    tid = qa_task(env, pid)
    drain(env)
    assert get(env, tid).status == "blocked" and env.provider.calls == []


def test_zero_collected_tests_is_not_a_pass(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[ExecResult(5, "no tests ran in 0.01s", "", 50, collected=junit_xml())])
    env, pid = seeded(migrated_db, tmp_path, [gen(("tests/test_calc.py", "x = 1"))], sb)
    tid = qa_task(env, pid)
    drain(env)
    t = get(env, tid)
    assert t.status == "failed" and t.last_error_kind == "tests_failed"


def test_exit_zero_without_any_evidence_is_not_a_pass(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[ExecResult(0, "selesai tanpa ringkasan", "", 50, collected=None)])
    env, pid = seeded(migrated_db, tmp_path, [gen(("tests/test_calc.py", TEST_CALC))], sb)
    tid = qa_task(env, pid)
    drain(env)
    assert get(env, tid).status == "failed"
    assert rows(env, TestRun, tid)[0].status == "error" and rows(env, TestRun, tid)[0].source == "none"


def test_qa_accepts_stdout_summary_when_junit_is_missing_or_hostile(migrated_db, tmp_path):
    for i, collected in enumerate((None, "<!DOCTYPE x><testsuite/>")):
        sb = FakeSandbox(pytest=[ExecResult(0, "3 passed in 0.1s", "", 50, collected=collected)])
        env, pid = seeded(migrated_db, tmp_path / str(i), [gen(("tests/test_calc.py", TEST_CALC))], sb)
        tid = qa_task(env, pid)
        drain(env)
        assert get(env, tid).status == "completed"
        assert rows(env, TestRun, tid)[0].source == "stdout"


def test_qa_timeout_is_a_failure(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[ExecResult(None, "", "", 60000, timed_out=True)])
    env, pid = seeded(migrated_db, tmp_path, [gen(("tests/test_calc.py", TEST_CALC))], sb)
    tid = qa_task(env, pid)
    drain(env)
    assert get(env, tid).status == "failed" and "batas waktu" in get(env, tid).last_error


def test_dev_then_qa_pipeline_via_dependencies(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[pytest_ok("test_add")])
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC), summary="calc dibuat"), gen(("tests/test_calc.py", TEST_CALC))], sandbox=sb)
    dev = dev_task(env, pid)
    qa = qa_task(env, pid, depends_on=[dev])
    assert drain(env) == 2
    assert (get(env, dev).status, get(env, qa).status) == ("completed", "completed")
    assert "calc dibuat" in env.provider.calls[1][1].prompt                   # keluaran Developer sampai ke QA
    assert [c["message"] for c in git.log(workspace(env, pid).root)] == ["tests: Uji kalkulator", "Buat kalkulator"]


def test_qa_is_blocked_when_developer_failed(migrated_db, tmp_path):
    sb = FakeSandbox(compile=[ExecResult(1, "", "SyntaxError", 10)])
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", "x"))] * 5, sandbox=sb)
    dev = dev_task(env, pid)
    qa = qa_task(env, pid, depends_on=[dev])
    drain(env)
    assert get(env, dev).status == "failed"
    assert (get(env, qa).status, get(env, qa).blocked_reason) == ("blocked", "dependency_failed")


def test_workspace_commits_are_isolated_per_project(migrated_db, tmp_path):
    env, pid = dev_env(migrated_db, tmp_path, [gen(("calc.py", CALC))])
    other = make_project(env, "Lain")
    dev_task(env, pid)
    drain(env)
    assert workspace(env, other).list() == []
    assert subprocess.run(["git", "status", "--porcelain"], cwd=workspace(env, pid).root, capture_output=True, text=True).stdout == ""
