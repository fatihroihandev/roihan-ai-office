"""Agent Reviewer (Bagian 4.3 D): penilaian independen berdasarkan bukti, bukan persetujuan atas klaim Developer.

Urutan: kumpulkan bukti deterministik (diff Git, pemindaian statis, tes yang dijalankan ULANG di sandbox) -> minta model
menilai tiap acceptance criteria dan menulis temuan (keluaran dibatasi skema) -> hitung verdict secara deterministik.
Pernyataan "criteria terpenuhi" dari model hanya diterima jika bukti yang dikutipnya merujuk fakta nyata (nama tes atau file).
"""
import json
import re

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.db.models import CodeReview, Task, TaskDependency, TestResult, TestRun
from app.engineering import recorder
from app.engineering.agents import is_test_path, run_in_sandbox
from app.review.static_scan import scan_files
from app.tasks.executors import ExecutionContext, ExecutorError, ExecutorOutcome, dependency_outputs, extract_json
from app.tasks.state import add_event
from app.workspace import git as workspace_git
from app.workspace.files import WorkspaceError, WorkspaceFiles

MAX_PARSE_ATTEMPTS = 2
MAX_CRITERIA = 10
CATEGORIES = ["security", "maintainability", "correctness", "regression", "tests", "performance", "style"]
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "criteria": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "met": {"type": "boolean"}, "evidence": {"type": "string"}},
            "required": ["id", "met", "evidence"]}},
        "findings": {"type": "array", "maxItems": 8, "items": {"type": "object", "properties": {
            "severity": {"type": "string", "enum": list(SEVERITY_ORDER)}, "category": {"type": "string", "enum": CATEGORIES},
            "file": {"type": "string"}, "description": {"type": "string"}, "suggestion": {"type": "string"}},
            "required": ["severity", "category", "description"]}},
        "unresolved_risks": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
    },
    "required": ["summary", "criteria", "findings", "unresolved_risks"],
}


class CriterionOut(BaseModel):
    id: str
    met: bool
    evidence: str = Field(default="", max_length=600)


class FindingOut(BaseModel):
    severity: str
    category: str
    file: str | None = None
    description: str = Field(min_length=1, max_length=500)
    suggestion: str | None = Field(default=None, max_length=500)


class ModelReview(BaseModel):
    summary: str = Field(default="", max_length=1500)
    criteria: list[CriterionOut] = []
    findings: list[FindingOut] = Field(default=[], max_length=8)
    unresolved_risks: list[str] = Field(default=[], max_length=5)


def parse_review(text: str, criteria_ids: set[str]) -> ModelReview:
    try:
        rev = ModelReview.model_validate(extract_json(text))
    except ValidationError as e:
        detail = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:3])
        raise ExecutorError("invalid_review_output", f"Keluaran review tidak valid: {detail}"[:400]) from e
    except ValueError as e:
        raise ExecutorError("invalid_review_output", f"Keluaran review tidak valid: {str(e)[:300]}") from e
    for f in rev.findings:
        if f.severity not in SEVERITY_ORDER or f.category not in CATEGORIES:
            raise ExecutorError("invalid_review_output", f"Severity/kategori temuan tidak dikenal: {f.severity}/{f.category}")
    unknown = [c.id for c in rev.criteria if c.id not in criteria_ids]
    if unknown:
        raise ExecutorError("invalid_review_output", f"ID criteria tidak dikenal: {unknown}; gunakan {sorted(criteria_ids)}")
    return rev


def grounded(evidence: str, refs: set[str]) -> bool:
    """Bukti dianggap berdasar jika mengutip minimal satu fakta nyata (nama tes, path/nama file, atau hash commit)."""
    low = evidence.lower()
    return len(evidence.strip()) >= 10 and any(r and r.lower() in low for r in refs)


def finalize(model: ModelReview, criteria: dict[str, str], refs: set[str], rerun: dict | None, static: list[dict]) -> dict:
    """Verdict ditentukan di sini, deterministik. Model hanya memberi penilaian per criteria dan temuan tambahan."""
    by_id = {c.id: c for c in model.criteria}
    results = []
    for cid, text in criteria.items():
        c = by_id.get(cid)
        if c is None:
            results.append({"id": cid, "criterion": text, "met": None, "evidence": "Tidak dinilai oleh model", "grounded": False})
        elif c.met and not grounded(c.evidence, refs):
            results.append({"id": cid, "criterion": text, "met": None, "grounded": False,
                            "evidence": f"Klaim 'terpenuhi' ditolak karena bukti tidak merujuk tes atau file nyata: {c.evidence[:200]}"})
        else:
            results.append({"id": cid, "criterion": text, "met": c.met, "evidence": c.evidence, "grounded": grounded(c.evidence, refs)})

    findings = static + [{**f.model_dump(), "source": "model"} for f in model.findings]
    findings.sort(key=lambda f: -SEVERITY_ORDER.get(f["severity"], 0))

    reasons = []
    if rerun is None:
        reasons.append("tes tidak dijalankan ulang secara independen (tidak ada tes atau sandbox tidak dipakai)")
    elif rerun["status"] != "passed":
        reasons.append(f"tes gagal pada eksekusi ulang ({rerun['failed']} gagal, {rerun['errors']} error)")
    if not criteria:
        reasons.append("tidak ada acceptance criteria untuk diverifikasi")
    elif any(r["met"] is not True for r in results):
        reasons.append("sebagian acceptance criteria belum terbukti terpenuhi")
    serious = [f for f in findings if f["severity"] in {"high", "critical"}]
    if serious:
        reasons.append(f"ada {len(serious)} temuan berat (high/critical)")
    return {"verdict": "changes_requested" if reasons else "approved", "reasons": reasons, "criteria": results, "findings": findings}


REVIEW_SYSTEM = (
    "Kamu adalah Reviewer di software house AI. Nilai perubahan kode HANYA berdasarkan bukti yang diberikan. "
    "Untuk tiap acceptance criteria, tulis met=true HANYA jika ada bukti konkret dan kutip nama tes atau file yang membuktikannya; "
    "jika bukti kurang atau ragu, tulis met=false. Jangan menyetujui hanya karena Developer mengklaim selesai. "
    "Balas HANYA dengan satu objek JSON sesuai skema."
)


def render_markdown(verdict: dict, summary: str, rerun: dict | None) -> str:
    L = [f"# Hasil Review: {verdict['verdict']}", "", summary or "(tanpa ringkasan)", ""]
    if verdict["reasons"]:
        L += ["## Alasan verdict", *[f"- {r}" for r in verdict["reasons"]], ""]
    if rerun:
        L += ["## Tes yang dijalankan ulang", f"- {rerun['status']}: {rerun['passed']} lulus, {rerun['failed']} gagal, {rerun['errors']} error", ""]
    L += ["## Acceptance criteria"] + [f"- [{'x' if c['met'] is True else ' '}] {c['criterion']} — {c['evidence']}" for c in verdict["criteria"]]
    L += ["", "## Temuan"] + ([f"- **{f['severity']}** ({f['category']}, {f['source']}) {f.get('file') or ''}{':' + str(f['line']) if f.get('line') else ''} — {f['description']}"
                              for f in verdict["findings"]] or ["- Tidak ada temuan"])
    return "\n".join(L) + "\n"


class ReviewerExecutor:
    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        t = ctx.task
        if t.action_type != "review":
            raise ExecutorError("unsupported_action", f"Reviewer hanya mengerjakan aksi 'review', bukan '{t.action_type}'", retryable=False)
        files = ctx.workspace()

        with ctx.session_factory() as s:
            deps = [s.get(Task, d) for d in s.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == t.id))]
            # urutan eksplisit: nomor criteria (C1, C2, ...) dan daftar commit harus sama pada setiap review ulang
            reviewed = sorted((d for d in deps if d is not None and d.status == "completed" and d.role in {"developer", "qa"}),
                              key=lambda d: (d.created_at, d.id))
            commits = [d.result.get("commit") for d in reviewed if d.result and d.result.get("commit")]
            reviewed_info = [{"id": d.id, "title": d.title, "role": d.role, "criteria": list(d.acceptance_criteria or []),
                              "changed": [f["path"] for f in (d.result or {}).get("files", [])]} for d in reviewed]
            reviewed_ids = [d.id for d in reviewed]
            prior_runs = []
            for d in reviewed:
                for r in s.scalars(select(TestRun).where(TestRun.task_id == d.id)):
                    names = [x.name for x in s.scalars(select(TestResult).where(TestResult.test_run_id == r.id))]
                    prior_runs.append({"task": d.title, "status": r.status, "passed": r.passed, "failed": r.failed, "names": names})

        head = workspace_git.head(files.root)
        commits = list(dict.fromkeys(commits)) or ([head] if head else [])
        if not files.list() or not commits:
            raise ExecutorError("nothing_to_review", "Tidak ada perubahan kode di workspace untuk direview", retryable=False)

        has_tests = any(is_test_path(f.path) and f.path.endswith(".py") for f in files.list())
        rerun, rerun_names, rerun_ids = None, [], {}
        if has_tests:   # tes dijalankan ULANG sendiri; hasil milik QA/Developer tidak dipercaya begitu saja
            result, exec_id = await run_in_sandbox(ctx, files, "pytest")
            summary = recorder.summarize(result)
            run_id = recorder.record_test_run(ctx.session_factory, task_id=t.id, attempt_id=ctx.attempt_id, project_id=t.project_id,
                                              execution_id=exec_id, summary=summary)
            status = "failed" if result.timed_out and summary.status == "passed" else summary.status
            rerun = {"status": status, "passed": summary.passed, "failed": summary.failed, "errors": summary.errors, "test_run_id": run_id}
            rerun_names = [c.name for c in summary.cases]
            rerun_ids = {"test_run_id": run_id, "execution_id": exec_id}

        sources: dict[str, str] = {}
        for f in files.list():
            if f.path.endswith((".py", ".md", ".txt", ".json", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".csv")):
                try:
                    sources[f.path] = files.read(f.path)
                except WorkspaceError:
                    continue
        static = scan_files(sources)

        crit_texts = list(dict.fromkeys([c for r in reviewed_info for c in r["criteria"]] + list(t.acceptance_criteria)))[:MAX_CRITERIA]
        criteria = {f"C{i + 1}": c for i, c in enumerate(crit_texts)}
        diffs = []
        for sha in commits[:3]:
            try:
                diffs.append(workspace_git.show(files.root, sha, 2500))
            except workspace_git.GitError:
                continue
        refs = {*rerun_names, *(n for r in prior_runs for n in r["names"]), *sources, *(p.rsplit("/", 1)[-1] for p in sources), *commits}

        prompt = self._prompt(ctx, criteria, prior_runs, rerun, static, diffs, files)
        feedback, model_review = None, None
        for _ in range(MAX_PARSE_ATTEMPTS):
            res = await ctx.generate(REVIEW_SYSTEM, prompt + (f"\n\nJawaban sebelumnya ditolak: {feedback}\nPerbaiki dan balas JSON saja." if feedback else ""),
                                     max_tokens=1200, temperature=0.1, json_schema=REVIEW_SCHEMA)
            try:
                if res.truncated:
                    raise ExecutorError("invalid_review_output", "Jawaban terpotong oleh batas token; ringkas penilaian")
                model_review = parse_review(res.text, set(criteria))
                break
            except ExecutorError as e:
                feedback = e.message
        if model_review is None:
            raise ExecutorError("invalid_review_output", feedback or "Keluaran review tidak valid")

        verdict = finalize(model_review, criteria, refs, rerun, static)
        markdown = render_markdown(verdict, model_review.summary, rerun)
        with ctx.session_factory() as s:
            row = CodeReview(task_id=t.id, project_id=t.project_id, reviewed_task_ids=reviewed_ids, commit=commits[0] if commits else None,
                             verdict=verdict["verdict"], summary=model_review.summary, verdict_reasons=verdict["reasons"],
                             criteria=verdict["criteria"], findings=verdict["findings"], unresolved_risks=model_review.unresolved_risks,
                             evidence={"rerun": rerun, "commits": commits, "static_findings": len(static), "prior_test_runs": len(prior_runs), **rerun_ids})
            s.add(row)
            for d in reviewed_ids:
                task = s.get(Task, d)
                task.review_status = verdict["verdict"]
                add_event(s, task, "review.completed", actor="reviewer", payload={"verdict": verdict["verdict"], "review_task": t.id})
            s.commit()
            review_id = row.id

        return ExecutorOutcome(
            output=markdown, verified=True,
            verification={"method": "independent_review", "passed": verdict["verdict"] == "approved", "criteria_checked": True,
                          "verdict": verdict["verdict"], "reasons": verdict["reasons"], "rerun_tests": rerun is not None},
            result={"output": markdown, "review_id": review_id, "verdict": verdict["verdict"], "findings": len(verdict["findings"])},
        )

    @staticmethod
    def _prompt(ctx: ExecutionContext, criteria: dict[str, str], prior_runs: list[dict], rerun: dict | None, static: list[dict],
                diffs: list[str], files: WorkspaceFiles) -> str:
        t = ctx.task
        parts = [f"TASK REVIEW: {t.title}", f"DESKRIPSI:\n{t.description or '-'}",
                 "ACCEPTANCE CRITERIA (nilai satu per satu, pakai id):\n" + ("\n".join(f"{k}: {v}" for k, v in criteria.items()) or "(tidak ada)")]
        if rerun:
            parts.append(f"TES DIJALANKAN ULANG SECARA INDEPENDEN: {rerun['status']} ({rerun['passed']} lulus, {rerun['failed']} gagal, {rerun['errors']} error)")
        else:
            parts.append("TES DIJALANKAN ULANG: tidak (tidak ada tes di workspace)")
        if prior_runs:
            parts.append("HASIL TES SEBELUMNYA (klaim, belum tentu benar):\n" + "\n".join(
                f"- {r['task']}: {r['status']} ({r['passed']} lulus, {r['failed']} gagal); tes: {', '.join(r['names'][:8])}" for r in prior_runs))
        if static:
            parts.append("TEMUAN PEMINDAIAN STATIS:\n" + "\n".join(f"- {f['severity']} {f['file']}:{f.get('line')} {f['description']}" for f in static[:10]))
        if diffs:
            parts.append("PERUBAHAN (diff):\n" + "\n\n".join(diffs))
        parts.append("ISI WORKSPACE:\n" + files.snapshot(3000))
        deps = dependency_outputs(ctx.session_factory, t.id)
        if deps:
            parts.append(f"KLAIM TASK SEBELUMNYA:\n{deps}")
        parts.append("Nilai tiap criteria dan tulis temuan keamanan, kualitas, dan potensi regresi. Jawab dalam bahasa Indonesia.")
        return "\n\n".join(parts)
