"""Pencatatan eksekusi dan hasil tes (Bagian 14.1 dan 15). Semua tulisan append-only."""
from app.db.models import Execution, TestResult, TestRun
from app.engineering.junit import Summary, parse_junit, parse_pytest_stdout
from app.sandbox.base import ExecResult

MAX_LOG_CHARS = 20_000


def redact(text: str, secrets: list[str], enabled: bool = True) -> str:
    if enabled:
        for s in secrets:
            text = text.replace(s, "[REDACTED]")
    return text


def execution_status(r: ExecResult) -> str:
    if r.timed_out:
        return "timeout"
    if r.exit_code is None:
        return "error"
    return "ok" if r.exit_code == 0 else "failed"


def record_execution(session_factory, *, task_id: str, attempt_id: str | None, project_id: str, kind: str,
                     argv: list[str], result: ExecResult, sandbox_name: str, secrets: list[str],
                     redact_enabled: bool = True) -> str:
    row = Execution(
        task_id=task_id, attempt_id=attempt_id, project_id=project_id, kind=kind, argv=argv,
        status=execution_status(result), exit_code=result.exit_code, duration_ms=result.duration_ms,
        timed_out=result.timed_out, output_truncated=result.output_truncated or len(result.stdout) > MAX_LOG_CHARS,
        stdout=redact(result.stdout, secrets, redact_enabled)[:MAX_LOG_CHARS],
        stderr=redact(result.stderr, secrets, redact_enabled)[:MAX_LOG_CHARS], sandbox=sandbox_name,
    )
    with session_factory() as s:
        s.add(row)
        s.commit()
        return row.id


def summarize(result: ExecResult) -> Summary:
    """Utamakan laporan JUnit; jika tidak ada atau rusak, pakai ringkasan teks pytest."""
    if result.collected:
        try:
            summary = parse_junit(result.collected)
            if summary.total or not result.stdout:
                return summary
        except Exception:
            pass
    return parse_pytest_stdout(result.stdout)


def record_test_run(session_factory, *, task_id: str, attempt_id: str | None, project_id: str,
                    execution_id: str | None, summary: Summary) -> str:
    with session_factory() as s:
        run = TestRun(task_id=task_id, attempt_id=attempt_id, execution_id=execution_id, project_id=project_id,
                      status=summary.status, source=summary.source, total=summary.total, passed=summary.passed,
                      failed=summary.failed, errors=summary.errors, skipped=summary.skipped,
                      duration_ms=summary.duration_ms)
        s.add(run)
        s.flush()
        for c in summary.cases:
            s.add(TestResult(test_run_id=run.id, name=c.name, classname=c.classname, outcome=c.outcome,
                             message=c.message, duration_ms=c.duration_ms))
        s.commit()
        return run.id
