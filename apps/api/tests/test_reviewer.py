import json

import pytest
from sqlalchemy import select

from app.db.models import CodeReview, Execution, Task, TestRun
from app.review.reviewer import ModelReview, finalize, grounded, parse_review
from app.review.static_scan import scan_files, scan_python
from app.tasks.executors import ExecutorError
from tests.fakes import FakeProvider, FakeSandbox, pytest_fail, pytest_ok
from tests.helpers import add_task, build_env, drain, get, make_project
from tests.test_engineering_agents import CALC, TEST_CALC, dev_task, gen, qa_task, rows, workspace


# ================================================================== pemindaian statis

def kinds(findings):
    return {(f["severity"], f["category"]) for f in findings}


@pytest.mark.parametrize("code,sev", [
    ("eval(x)", "high"), ("exec(code)", "high"), ("import os\nos.system('ls')", "high"), ("import os\nos.popen('ls')", "high"),
    ("import pickle\npickle.loads(b)", "high"), ("import yaml\nyaml.load(f)", "high"), ("import marshal\nmarshal.loads(b)", "high"),
    ("import subprocess\nsubprocess.run('ls', shell=True)", "high"), ("import subprocess\nsubprocess.run(['ls'])", "medium"),
    ("__import__('os')", "medium"), ("import socket", "medium"), ("import requests", "medium"),
    ("x = 1  # TODO perbaiki", "low"), ("try:\n    pass\nexcept:\n    pass", "low"),
])
def test_static_scan_flags_risky_constructs(code, sev):
    assert any(f["severity"] == sev for f in scan_python("a.py", code)), code


@pytest.mark.parametrize("code", [
    "API_KEY = 'abcd1234efgh5678'", "password = \"hunter2hunter2\"", "k = 'sk-" + "a" * 24 + "'", "k = 'AKIA" + "A" * 16 + "'",
    "x = '-----BEGIN RSA PRIVATE KEY-----'", "t = 'ghp_" + "a" * 32 + "'",
])
def test_static_scan_finds_hardcoded_secrets(code):
    assert any(f["severity"] in {"high", "critical"} and f["category"] == "security" for f in scan_python("a.py", code)), code


def test_static_scan_clean_code_and_safe_patterns_have_no_findings():
    assert scan_python("calc.py", CALC) == []
    assert scan_python("t.py", TEST_CALC) == []
    assert scan_python("a.py", "import yaml\nyaml.load(f, Loader=yaml.SafeLoader)") == []
    assert scan_python("a.py", "password = os.environ['PASSWORD']\nx = 'short'") == []


def test_static_scan_reports_syntax_errors_with_line():
    [f] = scan_python("bad.py", "def f(:\n    pass")
    assert (f["severity"], f["category"], f["file"], f["line"]) == ("high", "correctness", "bad.py", 1)


def test_static_scan_covers_non_python_files_for_secrets():
    findings = scan_files({"conf.toml": "token = 'abcdefgh12345678'", "notes.md": "tidak ada apa-apa", "a.py": CALC})
    assert [(f["file"], f["severity"]) for f in findings] == [("conf.toml", "high")]


# ================================================================== aturan verdict (deterministik)

CRITERIA = {"C1": "add(1,2) == 3", "C2": "divide by zero raises"}
REFS = {"test_add", "calc.py", "tests/test_calc.py", "abc1234"}
RERUN_OK = {"status": "passed", "passed": 3, "failed": 0, "errors": 0}


def model(met=(True, True), evidence=("test_add membuktikan jumlah di calc.py", "calc.py baris divide melempar ValueError"), findings=()):
    return ModelReview.model_validate({
        "summary": "ringkasan", "findings": list(findings), "unresolved_risks": [],
        "criteria": [{"id": f"C{i + 1}", "met": m, "evidence": e} for i, (m, e) in enumerate(zip(met, evidence))]})


def test_review_is_approved_only_when_everything_is_proven():
    v = finalize(model(), CRITERIA, REFS, RERUN_OK, [])
    assert v["verdict"] == "approved" and v["reasons"] == [] and all(c["met"] is True and c["grounded"] for c in v["criteria"])


@pytest.mark.parametrize("rerun,expected", [
    (None, "tes tidak dijalankan ulang"),
    ({"status": "failed", "passed": 2, "failed": 1, "errors": 0}, "tes gagal pada eksekusi ulang"),
    ({"status": "error", "passed": 0, "failed": 0, "errors": 1}, "tes gagal pada eksekusi ulang"),
])
def test_review_is_never_approved_without_passing_independent_tests(rerun, expected):
    v = finalize(model(), CRITERIA, REFS, rerun, [])
    assert v["verdict"] == "changes_requested" and any(expected in r for r in v["reasons"])


def test_model_approval_cannot_override_a_failed_rerun():
    v = finalize(model(met=(True, True)), CRITERIA, REFS, {"status": "failed", "passed": 0, "failed": 3, "errors": 0}, [])
    assert v["verdict"] == "changes_requested"


def test_unmet_or_missing_criteria_block_approval():
    assert finalize(model(met=(True, False)), CRITERIA, REFS, RERUN_OK, [])["verdict"] == "changes_requested"
    partial = ModelReview.model_validate({"summary": "x", "criteria": [{"id": "C1", "met": True, "evidence": "test_add lulus di calc.py"}]})
    v = finalize(partial, CRITERIA, REFS, RERUN_OK, [])
    assert v["verdict"] == "changes_requested" and v["criteria"][1]["met"] is None and "Tidak dinilai" in v["criteria"][1]["evidence"]
    assert finalize(model(), {}, REFS, RERUN_OK, [])["verdict"] == "changes_requested"          # tanpa criteria, tak ada yang bisa dibuktikan


@pytest.mark.parametrize("evidence", ["Semua terlihat bagus dan benar", "ok", "", "Implementasi sudah sesuai harapan pengguna"])
def test_claims_without_evidence_that_cites_real_facts_are_rejected(evidence):
    v = finalize(model(evidence=(evidence, "calc.py melempar ValueError")), CRITERIA, REFS, RERUN_OK, [])
    assert v["verdict"] == "changes_requested"
    c1 = v["criteria"][0]
    assert c1["met"] is None and c1["grounded"] is False


def test_grounding_is_case_insensitive_and_needs_a_real_reference():
    assert grounded("Tes TEST_ADD lulus pada Calc.py", REFS)
    assert grounded("lihat commit ABC1234", REFS)
    assert not grounded("sesuai spesifikasi", REFS)
    assert not grounded("test_add", {"test_add"})              # terlalu pendek untuk disebut bukti
    assert grounded("test_add lulus", {"test_add"})
    assert not grounded("calc.py ada di sana", set()) and not grounded("pendek", REFS)


@pytest.mark.parametrize("sev", ["high", "critical"])
def test_serious_findings_block_approval(sev):
    f = {"severity": sev, "category": "security", "description": "masalah serius"}
    v = finalize(model(findings=[f]), CRITERIA, REFS, RERUN_OK, [])
    assert v["verdict"] == "changes_requested" and any("temuan berat" in r for r in v["reasons"])


def test_minor_findings_do_not_block_and_static_findings_rank_first():
    static = [{"severity": "high", "category": "security", "file": "a.py", "line": 3, "description": "eval", "suggestion": "", "source": "static"}]
    low = {"severity": "low", "category": "style", "description": "nama kurang jelas"}
    v = finalize(model(findings=[low]), CRITERIA, REFS, RERUN_OK, [])
    assert v["verdict"] == "approved"
    v2 = finalize(model(findings=[low]), CRITERIA, REFS, RERUN_OK, static)
    assert v2["verdict"] == "changes_requested" and [f["source"] for f in v2["findings"]] == ["static", "model"]


@pytest.mark.parametrize("payload,fragment", [
    ("bukan json", "tidak valid"),
    (json.dumps({"summary": "x", "criteria": [{"id": "C9", "met": True, "evidence": "e"}], "findings": [], "unresolved_risks": []}), "ID criteria tidak dikenal"),
    (json.dumps({"summary": "x", "criteria": [], "findings": [{"severity": "gawat", "category": "security", "description": "d"}], "unresolved_risks": []}), "Severity"),
    (json.dumps({"summary": "x", "criteria": [], "findings": [{"severity": "low", "category": "lainnya", "description": "d"}], "unresolved_risks": []}), "kategori"),
    (json.dumps({"summary": "x", "criteria": [{"id": "C1", "met": "mungkin", "evidence": "e"}]}), "tidak valid"),
])
def test_review_output_is_validated(payload, fragment):
    with pytest.raises(ExecutorError) as e:
        parse_review(payload, {"C1", "C2"})
    assert fragment in e.value.message and e.value.retryable


# ================================================================== alur lengkap Developer -> QA -> Reviewer

def review_json(met=True, evidence="test_add di tests/test_calc.py membuktikan penjumlahan", findings=(), risks=(), n=3):
    ids = tuple(f"C{i + 1}" for i in range(n))
    return json.dumps({"summary": "Perubahan sudah diperiksa terhadap tes dan kode.", "findings": list(findings), "unresolved_risks": list(risks),
                       "criteria": [{"id": i, "met": met, "evidence": evidence} for i in ids]})


QA_TEST = "from calc import add\n\n\ndef test_add_qa():\n    assert add(2, 2) == 4\n"


def pipeline(migrated_db, tmp_path, review_reply, rerun=None, replies_extra=(), sandbox_kw=None):
    sb = FakeSandbox(pytest=[pytest_ok("test_add"), pytest_ok("test_add", "test_add_qa"), rerun or pytest_ok("test_add", "test_add_qa")], **(sandbox_kw or {}))
    replies = [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC), summary="calc dibuat"), gen(("tests/test_calc_qa.py", QA_TEST)), review_reply, *replies_extra]
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=replies), sandbox=sb)
    pid = make_project(env)
    dev = dev_task(env, pid)
    qa = qa_task(env, pid, depends_on=[dev])
    rv = add_task(env, pid, title="Review kalkulator", role="reviewer", action_type="review", depends_on=[dev, qa],
                  acceptance_criteria=["Semua tes lulus"])
    drain(env)
    return env, pid, dev, qa, rv


def test_reviewer_approves_when_independent_evidence_supports_it(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json())
    t = get(env, rv)
    assert t.status == "completed" and t.verification["method"] == "independent_review" and t.verification["criteria_checked"] is True
    assert t.verification["verdict"] == "approved" and t.verification["passed"] is True and t.verification["rerun_tests"] is True
    with env.sf() as s:
        [review] = s.scalars(select(CodeReview)).all()
        assert (review.verdict, review.task_id, sorted(review.reviewed_task_ids)) == ("approved", rv, sorted([dev, qa]))
        assert [c["met"] for c in review.criteria] == [True, True, True] and review.verdict_reasons == []
        assert review.evidence["rerun"]["passed"] == 2 and review.commit
    assert (get(env, dev).review_status, get(env, qa).review_status) == ("approved", "approved")
    assert get(env, rv).review_status is None


def test_reviewer_reruns_tests_itself_and_records_the_evidence(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json())
    [ex] = rows(env, Execution, rv)
    assert ex.kind == "pytest" and ex.argv[:4] == ["python3", "-m", "pytest", "-q"]
    [run_row] = rows(env, TestRun, rv)
    assert run_row.passed == 2 and run_row.execution_id == ex.id
    assert get(env, rv).result["verdict"] == "approved" and "# Hasil Review: approved" in get(env, rv).result["output"]


def test_a_failed_independent_rerun_overrides_a_confident_model(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json(), rerun=pytest_fail(failed=[("test_add_qa", "assert 5 == 4")], passed=("test_add",)))
    t = get(env, rv)
    assert t.status == "completed" and t.verification["verdict"] == "changes_requested" and t.verification["passed"] is False
    assert any("tes gagal pada eksekusi ulang" in r for r in t.verification["reasons"])
    assert get(env, dev).review_status == "changes_requested" and get(env, qa).review_status == "changes_requested"


def test_ungrounded_approval_from_the_model_is_not_enough(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json(evidence="Semua terlihat bagus dan sesuai"))
    t = get(env, rv)
    assert t.verification["verdict"] == "changes_requested"
    with env.sf() as s:
        review = s.scalars(select(CodeReview)).one()
        assert all(c["met"] is None and c["grounded"] is False for c in review.criteria)
        assert "Klaim 'terpenuhi' ditolak" in review.criteria[0]["evidence"]


def test_unmet_criteria_from_the_model_request_changes(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json(met=False, evidence="calc.py tidak menangani pembagian nol"))
    assert get(env, rv).verification["verdict"] == "changes_requested" and get(env, dev).review_status == "changes_requested"


def test_dangerous_code_found_by_static_scan_blocks_approval_even_if_model_misses_it(migrated_db, tmp_path):
    evil = "import os\n\n\ndef run(cmd):\n    return eval(cmd)\n"
    sb = FakeSandbox(pytest=[pytest_ok("test_add")])
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[gen(("calc.py", evil), ("tests/test_calc.py", TEST_CALC)), review_json(n=1)]), sandbox=sb)
    pid = make_project(env)
    dev = dev_task(env, pid)
    rv = add_task(env, pid, title="Review", role="reviewer", action_type="review", depends_on=[dev])
    drain(env)
    assert get(env, dev).status == "completed"
    with env.sf() as s:
        review = s.scalars(select(CodeReview)).one()
    assert review.verdict == "changes_requested" and any("temuan berat" in r for r in review.verdict_reasons)
    static = [f for f in review.findings if f["source"] == "static"]
    assert any("eval" in f["description"] and f["file"] == "calc.py" and f["line"] == 5 for f in static)


def test_review_findings_and_risks_are_stored_and_reach_the_report(migrated_db, tmp_path):
    finding = {"severity": "medium", "category": "tests", "file": "tests/test_calc.py", "description": "Tidak ada tes pembagian nol", "suggestion": "Tambah tes"}
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json(findings=[finding], risks=["Belum ada validasi tipe input"]))
    from app.reporting.builder import build_task_report
    with env.sf() as s:
        md, facts = build_task_report(s, dev)
    assert "Tidak ada tes pembagian nol" in md and "Belum ada validasi tipe input" in md and "approved" in md
    assert "Temuan medium (tests): Tidak ada tes pembagian nol" in " ".join(unresolved for unresolved in __import__("app.reporting.builder", fromlist=["x"]).unresolved_issues(facts))


def test_reviewer_prompt_contains_evidence_not_just_claims(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json())
    prompt = env.provider.calls[-1][1].prompt
    assert "C1: add(1,2) == 3" in prompt and "C2: add benar" in prompt and "C3: Semua tes lulus" in prompt
    assert "TES DIJALANKAN ULANG SECARA INDEPENDEN: passed" in prompt and "klaim, belum tentu benar" in prompt
    assert "diff" in prompt.lower() and "calc.py" in prompt and "HASIL TES SEBELUMNYA" in prompt


def test_reviewer_only_runs_allowlisted_commands(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, review_json())
    sb_runs = env.worker._sandbox.runs
    assert all(r.argv[0] == "python3" for r in sb_runs) and sb_runs[-1].argv[:4] == ["python3", "-m", "pytest", "-q"]


def test_reviewer_is_blocked_when_tests_exist_but_sandbox_is_unavailable(migrated_db, tmp_path):
    sb = FakeSandbox(available=False, reason="isolation_selftest_failed", message="Uji isolasi gagal")
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[review_json()]), sandbox=sb)
    pid = make_project(env)
    ws = workspace(env, pid)
    from app.workspace import git
    git.ensure_repo(ws.root)
    ws.write("calc.py", CALC)
    ws.write("tests/test_calc.py", TEST_CALC)
    git.commit_all(ws.root, "awal")
    rv = add_task(env, pid, title="Review", role="reviewer", action_type="review", acceptance_criteria=["Tes lulus"])
    drain(env)
    t = get(env, rv)
    assert (t.status, t.blocked_reason) == ("blocked", "isolation_selftest_failed") and env.provider.calls == []


def test_without_tests_the_review_can_run_but_cannot_approve(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[gen(("calc.py", CALC)), review_json(evidence="calc.py berisi add yang benar", n=2)]), sandbox=FakeSandbox())
    pid = make_project(env)
    dev = dev_task(env, pid)
    rv = add_task(env, pid, title="Review", role="reviewer", action_type="review", depends_on=[dev], acceptance_criteria=["Tes lulus"])
    drain(env)
    t = get(env, rv)
    assert t.status == "completed" and t.verification["verdict"] == "changes_requested" and t.verification["rerun_tests"] is False
    assert any("tidak dijalankan ulang" in r for r in t.verification["reasons"]) and rows(env, Execution, rv) == []


def test_nothing_to_review_in_an_empty_workspace(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[review_json()]), sandbox=FakeSandbox())
    pid = make_project(env)
    rv = add_task(env, pid, title="Review", role="reviewer", action_type="review")
    drain(env)
    t = get(env, rv)
    assert (t.status, t.last_error_kind) == ("failed", "nothing_to_review") and env.provider.calls == []


def test_invalid_model_output_is_corrected_once_with_feedback(migrated_db, tmp_path):
    env, pid, dev, qa, rv = pipeline(migrated_db, tmp_path, "ini bukan json", replies_extra=[review_json()])
    assert get(env, rv).status == "completed" and "Jawaban sebelumnya ditolak" in env.provider.calls[-1][1].prompt


def test_persistently_invalid_model_output_fails_without_a_half_finished_review(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=lambda p: "bukan json"), sandbox=FakeSandbox(pytest=[pytest_ok("test_add")]))
    pid = make_project(env)
    from app.workspace import git
    ws = workspace(env, pid)
    git.ensure_repo(ws.root)
    ws.write("calc.py", CALC)
    git.commit_all(ws.root, "awal")
    rv = add_task(env, pid, title="Review", role="reviewer", action_type="review", acceptance_criteria=["x"])
    drain(env)
    assert get(env, rv).status == "failed" and get(env, rv).last_error_kind == "invalid_review_output"
    with env.sf() as s:
        assert s.query(CodeReview).count() == 0                                    # tidak ada review setengah jadi


def test_model_must_use_only_the_criteria_ids_it_was_given(migrated_db, tmp_path):
    """Model yang mengarang id criteria ditolak dan dikoreksi sekali; jawaban berikutnya yang benar diterima."""
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC)),
                                                                        review_json(n=3), review_json(n=1)]),
                    sandbox=FakeSandbox(pytest=[pytest_ok("test_add")]))
    pid = make_project(env)
    dev = dev_task(env, pid)
    rv = add_task(env, pid, title="Review", role="reviewer", action_type="review", depends_on=[dev])
    drain(env)
    assert get(env, rv).status == "completed" and "ID criteria tidak dikenal" in env.provider.calls[-1][1].prompt


def test_reviewer_rejects_other_actions(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, sandbox=FakeSandbox())
    pid = make_project(env)
    tid = add_task(env, pid, role="reviewer", action_type="analysis")
    drain(env)
    assert (get(env, tid).status, get(env, tid).last_error_kind) == ("failed", "unsupported_action")


def test_reviewer_never_modifies_the_workspace(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=[gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC)), review_json(n=1)]),
                    sandbox=FakeSandbox(pytest=[pytest_ok("test_add")]))
    pid = make_project(env)
    dev = dev_task(env, pid)
    rv = add_task(env, pid, title="Review", role="reviewer", action_type="review", depends_on=[dev])
    drain(env)
    from app.workspace import git
    before = {f.path: workspace(env, pid).read(f.path) for f in workspace(env, pid).list()}
    assert before == {"calc.py": CALC, "tests/test_calc.py": TEST_CALC} and len(git.log(workspace(env, pid).root)) == 1
    assert get(env, rv).status == "completed"
