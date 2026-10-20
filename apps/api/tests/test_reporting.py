import re

import pytest
from sqlalchemy import select

from app.db.models import Task
from app.providers.base import ProviderError, ProviderErrorKind as K
from app.reporting.builder import (
    build_project_report, build_task_report, fact_numbers, gather_facts, next_steps, numbers_grounded, project_summary, unresolved_issues,
)
from app.sandbox.base import ExecResult
from tests.fakes import FakeProvider, FakeSandbox, pytest_fail, pytest_ok
from tests.helpers import add_task, build_env, drain, get, make_project
from tests.test_engineering_agents import CALC, TEST_CALC, dev_task, gen, qa_task


def finished_dev(migrated_db, tmp_path, sandbox=None, replies=None):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=list(replies or [gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC), summary="calc")])),
                    sandbox=sandbox or FakeSandbox(pytest=[pytest_ok("test_add", "test_zero")]))
    pid = make_project(env)
    tid = dev_task(env, pid)
    drain(env)
    return env, pid, tid


def section(md: str, n: int) -> str:
    m = re.search(rf"## {n}\. .*?\n(.*?)(?=\n## \d+\. |\Z)", md, re.S)
    assert m, f"bagian {n} tidak ditemukan"
    return m.group(1).strip()


def test_report_has_all_15_sections_from_the_spec_in_order(migrated_db, tmp_path):
    env, pid, tid = finished_dev(migrated_db, tmp_path)
    with env.sf() as s:
        md, _ = build_task_report(s, tid)
    titles = re.findall(r"^## (\d+)\. (.+)$", md, re.M)
    assert [int(n) for n, _ in titles] == list(range(1, 16))
    assert [t for _, t in titles] == [
        "Task ID dan tujuan", "Status akhir", "Ringkasan pekerjaan", "File yang berubah", "Dependensi dan konfigurasi penting",
        "Pengujian yang dijalankan", "Hasil pengujian", "Hasil review", "Masalah yang belum terselesaikan", "Risiko",
        "Model dan provider yang digunakan", "Penggunaan model atau biaya", "Approval yang diperlukan atau diperoleh",
        "Bukti verifikasi", "Langkah berikutnya"]


def test_report_facts_come_from_the_database_not_from_a_model(migrated_db, tmp_path):
    env, pid, tid = finished_dev(migrated_db, tmp_path)
    with env.sf() as s:
        md, facts = build_task_report(s, tid)
    t = get(env, tid)
    assert f"`{tid}`" in section(md, 1) and "Buat kalkulator" in md
    assert "**completed**" in section(md, 2)
    assert "`calc.py`" in section(md, 4) and "`tests/test_calc.py`" in section(md, 4) and t.result["commit"] in section(md, 4)
    assert "python3 -m compileall" in section(md, 6) and "python3 -m pytest" in section(md, 6) and "fake" in section(md, 6)
    assert "passed: 2 lulus, 0 gagal, 0 error" in section(md, 7)
    assert "ollama/fake-model:1b" in section(md, 11)
    assert "IDR 0" in section(md, 12) and "token prompt: 5" in section(md, 12)
    assert "Tidak diperlukan" in section(md, 13)
    assert "compile+pytest" in section(md, 14) and "belum diverifikasi otomatis" in section(md, 14)
    assert "review independen" in section(md, 15)
    assert facts["commit"] == t.result["commit"] and facts["usage"]["calls"] == 1      # hanya 1 panggilan model; compile/pytest bukan model


def test_report_for_a_failed_task_lists_the_real_problem_and_next_steps(migrated_db, tmp_path):
    sb = FakeSandbox(pytest=[pytest_fail(failed=[("test_add", "assert 3 == 4")])])
    env, pid, tid = finished_dev(migrated_db, tmp_path, sb, replies=[gen(("calc.py", CALC), ("tests/test_calc.py", TEST_CALC))] * 3)
    with env.sf() as s:
        md, facts = build_task_report(s, tid)
    assert "**failed**" in section(md, 2)
    assert "verification_failed" in section(md, 9) and "test_add" in section(md, 9)
    assert "failed: 0 lulus" not in md and "1 gagal" in section(md, 7)
    assert "coba ulang" in section(md, 15)
    assert any("test_add" in u for u in unresolved_issues(facts))


def test_report_shows_approvals_and_decisions(migrated_db, tmp_path):
    from tests.test_approvals import Recorder, decide, risky
    rec = Recorder()
    env = build_env(migrated_db, tmp_path, executors={"analyst": rec})
    pid = make_project(env)
    tid = risky(env, pid)
    with env.sf() as s:
        md, _ = build_task_report(s, tid)
    assert "pending" in section(md, 13) and "risiko critical" in section(md, 13) and "Menunggu keputusan approval" in section(md, 9)
    assert "Approval Center" in section(md, 15) and "memerlukan approval manusia" in section(md, 10)
    decide(env, tid, "approved", reason="sudah dicek")
    drain(env)
    with env.sf() as s:
        md, _ = build_task_report(s, tid)
    sec = section(md, 13)
    assert "approved" in sec and "diputuskan ceo" in sec and "alasan: sudah dicek" in sec and "sudah dipakai" in sec


def test_report_never_invents_missing_facts(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    tid = add_task(env, pid, role="market_research", action_type="analysis")      # tidak ada executor: tidak ada data apa pun
    with env.sf() as s:
        md, _ = build_task_report(s, tid)
    for n in (4, 6, 7, 8, 11):
        assert "tidak ada data" in section(md, n), n
    assert "0 · token prompt: 0" in section(md, 12) or "Pemanggilan: 0" in section(md, 12)
    assert "model" not in section(md, 11).replace("tidak ada data", "")


def test_next_steps_follow_the_state():
    base = {"task": {"status": "completed", "role": "developer", "review_status": None, "blocked_reason": None, "last_error_kind": None}}
    mk = lambda **kw: {"task": {**base["task"], **kw}}  # noqa: E731
    assert "review independen" in next_steps(mk())[0]
    assert "Perbaiki temuan" in next_steps(mk(review_status="changes_requested"))[0]
    assert "Tidak ada tindak lanjut" in next_steps(mk(review_status="approved"))[0]
    assert "Developer memperbaiki" in " ".join(next_steps(mk(status="failed", last_error_kind="tests_failed")))
    assert "executor_not_available" in next_steps(mk(status="blocked", blocked_reason="executor_not_available"))[0]
    assert "Approval Center" in next_steps(mk(status="pending_approval"))[0]
    assert "belum selesai" in next_steps(mk(status="running"))[0]


def test_numbers_must_be_grounded_in_the_facts():
    allowed = {"3", "2", "1", "5"}
    assert numbers_grounded("Dari 3 task, 2 selesai dan 1 gagal; 5 tes lulus.", allowed)
    assert numbers_grounded("Tidak ada angka di sini.", allowed)
    assert not numbers_grounded("Dari 3 task, 99 berhasil.", allowed)
    assert not numbers_grounded("Selesai dalam 7 hari.", allowed)


def test_digits_inside_ids_hashes_and_dates_never_ground_a_number():
    """Regresi: angka dicocokkan dengan seluruh teks laporan sehingga '42' atau '9' kebetulan lolos dari UUID/hash/jam."""
    assert not numbers_grounded("Sebanyak 42 task selesai dalam 9 jam.", {"1"})   # himpunan fakta tidak memuat 42 maupun 9
    assert numbers_grounded("Satu task selesai.", {"1"})
    from app.reporting.builder import _NUM
    # Potongan UUID, hash, dan tanggal yang menempel pada huruf atau tanda hubung bukan angka mandiri
    assert _NUM.findall("task 3d4291ab-4421-9f3e-1111-424242424242 commit de29eb1 tahun 2026-10-20 selesai") == []


def test_fact_numbers_come_only_from_structured_counts(migrated_db, tmp_path):
    env, pid, tid = finished_dev(migrated_db, tmp_path)
    with env.sf() as s:
        facts = [gather_facts(s, tid)]
    allowed = fact_numbers(facts)
    assert {"1", "2", "0"} <= allowed                           # 1 task, 2 tes lulus, 0 gagal
    assert not ({"42", "99", "123"} & allowed)                  # angka acak tidak ikut
    assert {"5", "7"} <= allowed                                # token prompt/jawaban (5 dan 7 dari provider uji) adalah fakta sah


@pytest.mark.parametrize("seed", range(25))
def test_invented_summary_is_always_discarded_regardless_of_random_ids(migrated_db, tmp_path, seed):
    """Uuid, hash, dan jam berbeda pada setiap eksekusi; karangan model tidak boleh lolos pada satu pun."""
    env, pid, dev = reporter_env(migrated_db, tmp_path, [gen(("calc.py", CALC)), "Sebanyak 42 task selesai dalam 9 jam."])
    rt = report_task(env, pid, dev)
    drain(env)
    assert get(env, rt).verification["summary_source"] == "deterministik"


def test_project_report_summarises_all_tasks(migrated_db, tmp_path):
    env, pid, dev = finished_dev(migrated_db, tmp_path)
    failed = add_task(env, pid, title="Tugas gagal", role="market_research", action_type="analysis")
    drain(env)
    with env.sf() as s:
        md, facts = build_project_report(s, pid, project_name="Proyek Uji")
    assert md.startswith("# Laporan Proyek: Proyek Uji") and "| Buat kalkulator | developer | completed |" in md
    assert "| Tugas gagal | market_research | blocked |" in md and md.count("### Task:") == 2
    assert project_summary(facts).startswith("Total 2 task: 1 blocked, 1 completed.")
    assert "1 eksekusi tes" in project_summary(facts)


# ================================================================== laporan otomatis dan agent Reporter

def report_file(env, pid, name):
    return env.storage.project_dir(pid) / "reports" / f"{name}.md"


def test_report_is_written_automatically_when_a_task_completes(migrated_db, tmp_path):
    env, pid, tid = finished_dev(migrated_db, tmp_path)
    text = report_file(env, pid, tid).read_text(encoding="utf-8")
    assert "# Laporan Task: Buat kalkulator" in text and "**completed**" in text and get(env, tid).result["commit"] in text


def test_report_is_written_automatically_when_a_task_fails(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(error=ProviderError(K.invalid_request, "model menolak")))
    pid = make_project(env)
    tid = add_task(env, pid, role="analyst", action_type="analysis")
    drain(env)
    text = report_file(env, pid, tid).read_text(encoding="utf-8")
    assert "**failed**" in text and "invalid_request" in text and "model menolak" in text


def test_no_report_is_written_for_tasks_that_will_retry(migrated_db, tmp_path):
    p = FakeProvider()
    p.errors = [ProviderError(K.unavailable, "mati")]
    env = build_env(migrated_db, tmp_path, provider=p, retry_backoff_base_s=600)
    pid = make_project(env)
    tid = add_task(env, pid, role="analyst", action_type="analysis")
    drain(env)
    assert get(env, tid).status == "queued" and not report_file(env, pid, tid).exists()


def reporter_env(migrated_db, tmp_path, replies):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=replies), sandbox=FakeSandbox(pytest=[pytest_ok("test_add")]))
    pid = make_project(env)
    dev = dev_task(env, pid)
    return env, pid, dev


def report_task(env, pid, dev):
    return add_task(env, pid, title="Laporan rilis", role="reporter", action_type="report", depends_on=[dev])


def test_reporter_builds_a_report_from_facts_with_a_validated_summary(migrated_db, tmp_path):
    env, pid, dev = reporter_env(migrated_db, tmp_path, [gen(("calc.py", CALC)), "Satu task selesai dan lolos verifikasi."])
    rt = report_task(env, pid, dev)
    drain(env)
    t = get(env, rt)
    assert t.status == "completed" and t.verification["method"] == "report_from_facts" and t.verification["summary_source"].startswith("model")
    text = report_file(env, pid, f"laporan-{rt}").read_text(encoding="utf-8")
    assert "## Ringkasan" in text and "Satu task selesai dan lolos verifikasi." in text and "| Buat kalkulator | developer | completed |" in text
    assert t.result["report"] == f"reports/laporan-{rt}.md" and t.result["tasks_reported"] == 1


def test_reporter_discards_a_summary_with_invented_numbers(migrated_db, tmp_path):
    env, pid, dev = reporter_env(migrated_db, tmp_path, [gen(("calc.py", CALC)), "Sebanyak 42 task selesai dalam 9 jam."])
    rt = report_task(env, pid, dev)
    drain(env)
    text = report_file(env, pid, f"laporan-{rt}").read_text(encoding="utf-8")
    assert "Sebanyak 42 task" not in text and "9 jam" not in text      # kalimat karangan model tidak masuk laporan
    assert get(env, rt).verification["summary_source"] == "deterministik" and "Total 1 task: 1 completed." in text


@pytest.mark.parametrize("failure", [ProviderError(K.unavailable, "mati"), ProviderError(K.timeout, "lambat")])
def test_reporter_still_reports_when_the_model_is_unavailable(migrated_db, tmp_path, failure):
    env, pid, dev = reporter_env(migrated_db, tmp_path, [gen(("calc.py", CALC))])
    rt = report_task(env, pid, dev)
    drain(env)                                                         # Developer selesai dulu
    env.provider.errors = [failure, failure, failure]
    with env.sf() as s:
        s.get(Task, rt).status = "queued"
        s.commit()
    drain(env)
    t = get(env, rt)
    assert t.status == "completed" and t.verification["summary_source"] == "deterministik"
    assert "Total 1 task" in report_file(env, pid, f"laporan-{rt}").read_text(encoding="utf-8")


def test_reporter_without_dependencies_reports_the_whole_project(migrated_db, tmp_path):
    env, pid, dev = reporter_env(migrated_db, tmp_path, [gen(("calc.py", CALC)), "Ringkas."])
    drain(env)
    rt = add_task(env, pid, title="Laporan", role="reporter", action_type="report")
    drain(env)
    assert get(env, rt).result["tasks_reported"] == 1
    assert "Buat kalkulator" in report_file(env, pid, f"laporan-{rt}").read_text(encoding="utf-8")


def test_reporter_documentation_action_still_writes_a_document(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path, provider=FakeProvider(reply=["# Panduan\nIsi panduan"]))
    pid = make_project(env)
    tid = add_task(env, pid, title="Panduan", role="reporter", action_type="documentation")
    drain(env)
    t = get(env, tid)
    assert t.status == "completed" and t.verification["method"] == "output_complete" and t.result["artifact"].startswith("artifacts/")


def test_report_name_cannot_escape_the_reports_folder(migrated_db, tmp_path):
    env = build_env(migrated_db, tmp_path)
    pid = make_project(env)
    from app.projects.storage import StorageError
    for bad in ("../x", "a/b", "a\\b", "", "x" * 81, "x.y", "..", "a b"):
        with pytest.raises(StorageError):
            env.storage.write_report(pid, bad, "x")
    assert env.storage.write_report(pid, "ok-1", "x") == "reports/ok-1.md"
