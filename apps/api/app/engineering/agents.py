"""Agent Developer dan QA. Keduanya hanya menulis file di workspace dan meminta perintah dari allowlist;
eksekusi selalu lewat sandbox dan tercatat. Status berhasil berdasarkan bukti eksekusi, bukan klaim model."""
import json

from pydantic import BaseModel, Field, ValidationError

from app.engineering import recorder
from app.engineering.junit import Summary
from app.sandbox.base import ExecResult, ExecSpec
from app.sandbox.commands import CommandError, build_command
from app.tasks.executors import (
    ExecutionContext, ExecutorError, ExecutorOutcome, dependency_outputs, extract_json,
)
from app.workspace import git as workspace_git
from app.workspace.files import CODE_EXTS, DOC_EXTS, WorkspaceError, WorkspaceFiles

MAX_FIX_ROUNDS = 2          # perbaikan setelah verifikasi gagal (1 penulisan awal + 2 perbaikan)
MAX_PARSE_ATTEMPTS = 2      # koreksi jika keluaran model tidak valid
MAX_FILES_PER_ROUND = 6
FEEDBACK_CHARS = 1500

CODE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "files": {"type": "array", "minItems": 1, "maxItems": MAX_FILES_PER_ROUND, "items": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        }},
    },
    "required": ["summary", "files"],
}


class GeneratedFile(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str


class Generated(BaseModel):
    summary: str = Field(default="", max_length=2000)
    files: list[GeneratedFile] = Field(min_length=1, max_length=MAX_FILES_PER_ROUND)


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or name.startswith("test_") or name.endswith("_test.py")


def parse_generated(text: str, files: WorkspaceFiles, allowed_exts: set[str], path_rule=None) -> Generated:
    """Validasi keluaran model: skema, path aman, ekstensi, dan aturan tambahan (mis. tes hanya di tests/)."""
    try:
        gen = Generated.model_validate(extract_json(text))
    except ValidationError as e:
        detail = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:3])
        raise ExecutorError("invalid_code_output", f"Keluaran tidak valid: {detail}"[:400]) from e
    except ValueError as e:
        raise ExecutorError("invalid_code_output", f"Keluaran tidak valid: {str(e)[:300]}") from e
    seen: set[str] = set()
    for f in gen.files:
        try:
            files.check_relative(f.path)
        except WorkspaceError as e:
            raise ExecutorError("invalid_code_output", f"Path ditolak: {e}") from e
        ext = f.path.rsplit(".", 1)[-1].lower() if "." in f.path else ""
        if ext not in allowed_exts:
            raise ExecutorError("invalid_code_output", f"Ekstensi file ditolak: {f.path} (diizinkan: {', '.join(sorted(allowed_exts))})")
        if path_rule and (msg := path_rule(f.path)):
            raise ExecutorError("invalid_code_output", msg)
        if f.path in seen:
            raise ExecutorError("invalid_code_output", f"Path ganda: {f.path}")
        seen.add(f.path)
    return gen


def apply_generated(files: WorkspaceFiles, gen: Generated, allowed_exts: set[str]) -> list[dict]:
    written = []
    for f in gen.files:
        try:
            is_new, size = files.write(f.path, f.content, allowed_exts)
        except WorkspaceError as e:
            raise ExecutorError("invalid_code_output", f"Gagal menulis {f.path}: {e}") from e
        written.append({"path": f.path, "bytes": size, "new": is_new})
    return written


async def generate_files(ctx: ExecutionContext, system: str, prompt: str, files: WorkspaceFiles,
                         allowed_exts: set[str], path_rule=None) -> Generated:
    error = None
    for _ in range(MAX_PARSE_ATTEMPTS):
        text = prompt + (f"\n\nJawaban sebelumnya ditolak: {error}\nPerbaiki dan balas JSON saja." if error else "")
        res = await ctx.generate(system, text, max_tokens=1500, temperature=0.2, json_schema=CODE_SCHEMA)
        try:
            if res.truncated:
                raise ExecutorError("invalid_code_output", "Jawaban terpotong oleh batas token; buat file lebih ringkas")
            return parse_generated(res.text, files, allowed_exts, path_rule)
        except ExecutorError as e:
            error = e.message
    raise ExecutorError("invalid_code_output", error or "Keluaran tidak valid")


async def run_in_sandbox(ctx: ExecutionContext, files: WorkspaceFiles, kind: str, args: list[str] | None = None) -> tuple[ExecResult, str]:
    """Bentuk perintah dari allowlist, jalankan di sandbox, dan catat. Kembalikan (hasil, id_eksekusi)."""
    try:
        cmd = build_command(kind, args, files)
    except CommandError as e:
        raise ExecutorError("command_rejected", str(e), retryable=False) from e
    sandbox = await ctx.require_sandbox()
    s = ctx.settings
    result = await sandbox.run(ExecSpec(cmd.argv, files.root, timeout_s=s.sandbox_timeout_s, memory_mb=s.sandbox_memory_mb,
                                        max_output_bytes=s.sandbox_max_output_kb * 1024, collect_file=cmd.collect_file))
    exec_id = recorder.record_execution(
        ctx.session_factory, task_id=ctx.task.id, attempt_id=ctx.attempt_id, project_id=ctx.task.project_id, kind=kind,
        argv=cmd.argv, result=result, sandbox_name=sandbox.name, secrets=s.secret_values, redact_enabled=s.redact_secrets_in_logs)
    return result, exec_id


def _tail(text: str, limit: int = FEEDBACK_CHARS) -> str:
    return text if len(text) <= limit else "...\n" + text[-limit:]


def failure_text(result: ExecResult, summary: Summary | None) -> str:
    if result.timed_out:
        return "Eksekusi melewati batas waktu (kemungkinan loop tak berhenti)."
    if summary and summary.cases:
        bad = [c for c in summary.cases if c.outcome in {"failed", "error"}]
        lines = [f"- {c.name}: {c.message or c.outcome}" for c in bad[:5]]
        if lines:
            return "Tes gagal:\n" + "\n".join(lines)
    return _tail((result.stderr + "\n" + result.stdout).strip() or f"exit code {result.exit_code}")


# ---------------------------------------------------------------- Developer

DEV_SYSTEM = (
    "Kamu adalah Developer di software house AI. Tulis kode Python yang sederhana, benar, dan siap diuji. "
    "Balas HANYA dengan satu objek JSON berisi 'summary' dan 'files' (path relatif, tanpa awalan titik). "
    "Selalu tulis isi LENGKAP setiap file. Jangan menulis file di luar kebutuhan task."
)


def _task_block(ctx: ExecutionContext) -> str:
    t = ctx.task
    criteria = "\n".join(f"- {c}" for c in t.acceptance_criteria) or "- (tidak ada)"
    parts = [f"TASK: {t.title}", f"DESKRIPSI:\n{t.description or '-'}", f"ACCEPTANCE CRITERIA:\n{criteria}"]
    deps = dependency_outputs(ctx.session_factory, t.id)
    if deps:
        parts.append(f"HASIL TASK SEBELUMNYA:\n{deps}")
    return "\n\n".join(parts)


class DeveloperExecutor:
    idempotent = True  # menimpa file dengan keluaran baru dan commit; aman diulang

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        t = ctx.task
        if t.action_type == "documentation":
            return await self._document(ctx)
        if t.action_type != "code_change":
            raise ExecutorError("unsupported_action", f"Developer belum mendukung tindakan '{t.action_type}'", retryable=False)

        await ctx.require_sandbox()   # tanpa sandbox yang lolos uji, jangan menulis kode yang tidak bisa diverifikasi
        files = ctx.workspace()
        feedback = None
        for round_no in range(1 + MAX_FIX_ROUNDS):
            prompt = f"{_task_block(ctx)}\n\nISI WORKSPACE SAAT INI:\n{files.snapshot()}"
            if feedback:
                prompt += f"\n\nVERIFIKASI SEBELUMNYA GAGAL. Perbaiki kode:\n{feedback}"
            prompt += "\n\nTulis atau perbarui file yang diperlukan. Sertakan docstring singkat."
            gen = await generate_files(ctx, DEV_SYSTEM, prompt, files, CODE_EXTS)
            written = apply_generated(files, gen, CODE_EXTS)
            verification = await self._verify(ctx, files)
            if verification["passed"]:
                sha = workspace_git.commit_all(files.root, t.title, author="developer agent")
                return self._outcome(gen, written, sha, verification, round_no)
            feedback = verification["feedback"]

        sha = workspace_git.commit_all(files.root, f"{t.title} [belum terverifikasi]", author="developer agent")
        raise ExecutorError("verification_failed", f"Verifikasi gagal setelah {1 + MAX_FIX_ROUNDS} percobaan: {feedback}"[:600],
                            retryable=False)

    async def _verify(self, ctx: ExecutionContext, files: WorkspaceFiles) -> dict:
        compiled, _ = await run_in_sandbox(ctx, files, "compile")
        if compiled.exit_code != 0 or compiled.timed_out:
            return {"passed": False, "feedback": "Kode tidak dapat dikompilasi:\n" + failure_text(compiled, None)}
        info: dict = {"passed": True, "method": "compile", "tests_run": False}
        if any(is_test_path(f.path) and f.path.endswith(".py") for f in files.list()):
            result, exec_id = await run_in_sandbox(ctx, files, "pytest")
            summary = recorder.summarize(result)
            run_id = recorder.record_test_run(ctx.session_factory, task_id=ctx.task.id, attempt_id=ctx.attempt_id,
                                              project_id=ctx.task.project_id, execution_id=exec_id, summary=summary)
            ok = summary.status == "passed" and not result.timed_out
            info.update(method="compile+pytest", tests_run=True, test_run_id=run_id,
                        tests={"passed": summary.passed, "failed": summary.failed, "errors": summary.errors})
            if not ok:
                return {"passed": False, "feedback": failure_text(result, summary)}
        return info

    @staticmethod
    def _outcome(gen: Generated, written: list[dict], sha: str | None, verification: dict, round_no: int) -> ExecutorOutcome:
        names = ", ".join(f["path"] for f in written)
        text = f"{gen.summary.strip() or 'Perubahan kode selesai'}\n\nFile: {names}"
        return ExecutorOutcome(
            output=text, verified=True,
            verification={"method": verification["method"], "passed": True, "criteria_checked": False,
                          "tests_run": verification["tests_run"], "fix_rounds": round_no,
                          **({"test_run_id": verification["test_run_id"], "tests": verification["tests"]}
                             if verification["tests_run"] else {})},
            result={"output": text, "files": written, "commit": sha},
        )

    async def _document(self, ctx: ExecutionContext) -> ExecutorOutcome:
        files = ctx.workspace()
        prompt = (f"{_task_block(ctx)}\n\nISI WORKSPACE SAAT INI:\n{files.snapshot()}\n\n"
                  "Tulis dokumen Markdown (.md) di folder docs/. Hanya file .md atau .txt.")
        gen = await generate_files(ctx, DEV_SYSTEM, prompt, files, DOC_EXTS)
        written = apply_generated(files, gen, DOC_EXTS)
        sha = workspace_git.commit_all(files.root, ctx.task.title, author="developer agent")
        text = f"{gen.summary.strip() or 'Dokumen ditulis'}\n\nFile: {', '.join(f['path'] for f in written)}"
        return ExecutorOutcome(
            output=text, verified=True,
            verification={"method": "files_written", "passed": True, "criteria_checked": False},
            result={"output": text, "files": written, "commit": sha},
        )


# ---------------------------------------------------------------- QA

QA_SYSTEM = (
    "Kamu adalah QA/Tester di software house AI. Tulis tes pytest yang menguji perilaku kode di workspace "
    "sesuai acceptance criteria. Impor modul langsung dari root workspace (mis. 'from calc import add'). "
    "Tes harus deterministik, tanpa jaringan dan tanpa file eksternal. "
    "Balas HANYA dengan satu objek JSON berisi 'summary' dan 'files'; semua path harus berbentuk tests/test_<nama>.py."
)


def _tests_only(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    if not (path.startswith("tests/") and path.count("/") == 1 and name.startswith("test_") and name.endswith(".py")):
        return f"QA hanya boleh menulis tests/test_*.py, bukan {path}"
    return None


class QAExecutor:
    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        t = ctx.task
        if t.action_type != "run_tests":
            raise ExecutorError("unsupported_action", f"QA belum mendukung tindakan '{t.action_type}'", retryable=False)
        await ctx.require_sandbox()
        files = ctx.workspace()
        if not any(f.path.endswith(".py") and not is_test_path(f.path) for f in files.list()):
            raise ExecutorError("nothing_to_test", "Workspace belum berisi kode Python untuk diuji", retryable=False)

        prompt = (f"{_task_block(ctx)}\n\nKODE DI WORKSPACE:\n{files.snapshot()}\n\n"
                  "Tulis tes pytest untuk kode di atas. Uji kasus normal, kasus tepi, dan kesalahan input.")
        gen = await generate_files(ctx, QA_SYSTEM, prompt, files, {"py"}, _tests_only)
        written = apply_generated(files, gen, {"py"})
        workspace_git.commit_all(files.root, f"tests: {t.title}", author="qa agent")

        result, exec_id = await run_in_sandbox(ctx, files, "pytest")
        summary = recorder.summarize(result)
        run_id = recorder.record_test_run(ctx.session_factory, task_id=t.id, attempt_id=ctx.attempt_id,
                                          project_id=t.project_id, execution_id=exec_id, summary=summary)
        counts = {"total": summary.total, "passed": summary.passed, "failed": summary.failed,
                  "errors": summary.errors, "skipped": summary.skipped}
        if summary.status != "passed" or result.timed_out:
            raise ExecutorError("tests_failed", f"{json.dumps(counts)} — {failure_text(result, summary)}"[:600], retryable=False)

        text = f"{summary.passed} tes lulus ({', '.join(f['path'] for f in written)})"
        return ExecutorOutcome(
            output=text, verified=True,
            verification={"method": "pytest", "passed": True, "criteria_checked": False, "test_run_id": run_id, "tests": counts},
            result={"output": text, "files": written, "test_run_id": run_id, "tests": counts},
        )
