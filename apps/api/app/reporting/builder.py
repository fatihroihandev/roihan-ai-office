"""Pembuat laporan task (Bagian 17). SEMUA fakta berasal dari database; tidak ada yang ditulis atau ditebak model."""
import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Approval, CodeReview, Execution, ModelUsage, RoutingDecision, Task, TaskAttempt, TaskDependency, TestResult, TestRun,
)

NO_DATA = "_(tidak ada data)_"
MAX_TASKS_IN_PROJECT_REPORT = 10


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def gather_facts(session: Session, task_id: str) -> dict:
    t = session.get(Task, task_id)
    if t is None:
        raise LookupError("Task tidak ditemukan")
    attempts = list(session.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id).order_by(TaskAttempt.number)))
    deps = [session.get(Task, d) for d in session.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == t.id))]
    runs = list(session.scalars(select(TestRun).where(TestRun.task_id == t.id).order_by(TestRun.created_at)))
    reviews = [r for r in session.scalars(select(CodeReview).where(CodeReview.project_id == t.project_id).order_by(CodeReview.created_at))
               if r.task_id == t.id or t.id in (r.reviewed_task_ids or [])]
    attempt_ids = [a.id for a in attempts]
    usage = session.execute(
        select(func.count(), func.coalesce(func.sum(ModelUsage.prompt_tokens), 0), func.coalesce(func.sum(ModelUsage.completion_tokens), 0),
               func.coalesce(func.sum(ModelUsage.duration_ms), 0), func.coalesce(func.sum(ModelUsage.cost_idr), 0.0))
        .where(ModelUsage.request_id.in_(attempt_ids))).one() if attempt_ids else (0, 0, 0, 0, 0.0)
    result = t.result or {}
    return {
        "task": {"id": t.id, "title": t.title, "description": t.description, "role": t.role, "action_type": t.action_type,
                 "status": t.status, "risk_level": t.risk_level, "difficulty_category": t.difficulty_category,
                 "difficulty_score": t.difficulty_score, "attempt_count": t.attempt_count, "blocked_reason": t.blocked_reason,
                 "last_error": t.last_error, "last_error_kind": t.last_error_kind, "verification": t.verification,
                 "review_status": t.review_status, "acceptance_criteria": list(t.acceptance_criteria or []),
                 "created_at": _iso(t.created_at), "finished_at": _iso(t.finished_at), "project_id": t.project_id},
        "files": result.get("files") or [], "commit": result.get("commit"),
        "dependencies": [{"id": d.id, "title": d.title, "status": d.status} for d in deps if d],
        "attempts": [{"number": a.number, "status": a.status, "error_kind": a.error_kind, "model": a.model,
                      "duration_ms": (a.usage or {}).get("duration_ms")} for a in attempts],
        "executions": [{"kind": e.kind, "status": e.status, "exit_code": e.exit_code, "duration_ms": e.duration_ms, "sandbox": e.sandbox,
                        "argv": e.argv} for e in session.scalars(select(Execution).where(Execution.task_id == t.id).order_by(Execution.created_at))],
        "test_runs": [{"status": r.status, "total": r.total, "passed": r.passed, "failed": r.failed, "errors": r.errors,
                       "skipped": r.skipped, "source": r.source,
                       "failures": [{"name": x.name, "message": x.message} for x in session.scalars(
                           select(TestResult).where(TestResult.test_run_id == r.id, TestResult.outcome.in_(["failed", "error"])))]}
                      for r in runs],
        "reviews": [{"verdict": r.verdict, "summary": r.summary, "reasons": r.verdict_reasons, "criteria": r.criteria,
                     "findings": r.findings, "unresolved_risks": r.unresolved_risks, "is_review_task": r.task_id == t.id} for r in reviews],
        "approvals": [{"status": a.status, "risk_level": a.risk_level, "requested_by": a.requested_by, "decided_by": a.decided_by,
                       "decided_at": _iso(a.decided_at), "reason": a.decision_reason, "expires_at": _iso(a.expires_at), "used": a.used_at is not None}
                      for a in session.scalars(select(Approval).where(Approval.task_id == t.id).order_by(Approval.created_at))],
        "routing": [{"provider": r.provider, "model": r.model, "num_ctx": r.num_ctx} for r in session.scalars(
            select(RoutingDecision).where(RoutingDecision.task_id == t.id).order_by(RoutingDecision.created_at))],
        "usage": {"calls": usage[0], "prompt_tokens": usage[1], "completion_tokens": usage[2], "duration_ms": usage[3], "cost_idr": usage[4]},
    }


def unresolved_issues(f: dict) -> list[str]:
    t, out = f["task"], []
    if t["status"] == "failed":
        out.append(f"Task gagal ({t['last_error_kind']}): {t['last_error']}")
    if t["status"] == "blocked":
        out.append(f"Task terblokir ({t['blocked_reason']}): {t['last_error'] or 'lihat alasan'}")
    for run in f["test_runs"]:
        out += [f"Tes gagal: {x['name']} — {x['message'] or 'tanpa pesan'}" for x in run["failures"]][:5]
    for r in f["reviews"]:
        out += [f"Temuan {x['severity']} ({x['category']}): {x['description']}" for x in r["findings"] if x["severity"] in {"medium", "high", "critical"}]
        out += [f"Risiko belum selesai: {x}" for x in r["unresolved_risks"]]
        out += [f"Criteria belum terbukti: {c['criterion']}" for c in r["criteria"] if c.get("met") is not True]
    if any(a["status"] == "pending" for a in f["approvals"]):
        out.append("Menunggu keputusan approval")
    return list(dict.fromkeys(out))


def next_steps(f: dict) -> list[str]:
    t, steps = f["task"], []
    st, role, review = t["status"], t["role"], t["review_status"]
    if st == "failed":
        steps.append("Periksa error terakhir, perbaiki penyebabnya, lalu coba ulang (retry).")
        if t["last_error_kind"] == "tests_failed":
            steps.append("Developer memperbaiki kode yang gagal diuji, kemudian QA mengulang pengujian.")
    elif st == "blocked":
        steps.append(f"Selesaikan penyebab pemblokiran ({t['blocked_reason']}), lalu coba ulang.")
    elif st == "pending_approval":
        steps.append("Menunggu keputusan CEO di Approval Center; approval kedaluwarsa jika tidak diputuskan.")
    elif st == "cancelled":
        steps.append("Tidak ada; task dibatalkan.")
    elif st == "completed":
        if role in {"developer", "qa"} and review is None:
            steps.append("Jalankan review independen (Reviewer) sebelum hasil dianggap diterima.")
        elif review == "changes_requested":
            steps.append("Perbaiki temuan Reviewer lalu minta review ulang.")
        else:
            steps.append("Tidak ada tindak lanjut teknis yang tercatat.")
    elif st in {"queued", "running", "draft"}:
        steps.append("Task belum selesai; laporan ini bersifat sementara.")
    return steps


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else NO_DATA


def render_task_report(f: dict) -> str:
    t = f["task"]
    verification = t["verification"]
    L: list[str] = [f"# Laporan Task: {t['title']}", ""]

    L += ["## 1. Task ID dan tujuan", f"- ID: `{t['id']}`", f"- Role: {t['role']} · Aksi: {t['action_type']}",
          f"- Tujuan: {t['description'] or '(tidak ada deskripsi)'}",
          "- Acceptance criteria:" if t["acceptance_criteria"] else "- Acceptance criteria: (tidak ada)"]
    L += [f"  - {c}" for c in t["acceptance_criteria"]]

    L += ["", "## 2. Status akhir", f"- Status: **{t['status']}**" + (f" · review: **{t['review_status']}**" if t["review_status"] else ""),
          f"- Percobaan: {t['attempt_count']}" + (f" · selesai: {t['finished_at']}" if t["finished_at"] else "")]

    ok_runs = [r for r in f["test_runs"] if r["status"] == "passed"]
    summary = {"completed": "Task selesai dan lolos verifikasi sistem.", "failed": "Task gagal; lihat bagian masalah.",
               "blocked": "Task terblokir dan belum dikerjakan.", "pending_approval": "Task menunggu approval dan belum berjalan.",
               "cancelled": "Task dibatalkan."}.get(t["status"], "Task belum selesai.")
    if f["files"]:
        summary += f" {len(f['files'])} file ditulis."
    if ok_runs:
        summary += f" Pengujian terakhir lulus ({ok_runs[-1]['passed']} tes)."
    L += ["", "## 3. Ringkasan pekerjaan", summary]

    L += ["", "## 4. File yang berubah", _bullets([f"`{x['path']}` ({x['bytes']} B{', baru' if x.get('new') else ''})" for x in f["files"]])
          + (f"\n- Commit: `{f['commit']}`" if f["commit"] else "")]

    L += ["", "## 5. Dependensi dan konfigurasi penting",
          _bullets([f"{d['title']} — {d['status']}" for d in f["dependencies"]]),
          f"- Risiko: {t['risk_level']} · Tingkat kesulitan: {t['difficulty_category'] or '?'} ({t['difficulty_score']})"]

    L += ["", "## 6. Pengujian yang dijalankan",
          _bullets([f"`{' '.join(e['argv'][:4])}` di {e['sandbox']} → {e['status']} (exit {e['exit_code']}, {e['duration_ms']} ms)"
                    for e in f["executions"]])]

    L += ["", "## 7. Hasil pengujian", _bullets([
        f"{r['status']}: {r['passed']} lulus, {r['failed']} gagal, {r['errors']} error, {r['skipped']} dilewati (sumber: {r['source']})"
        for r in f["test_runs"]])]

    rev = []
    for r in f["reviews"]:
        rev.append(f"Verdict **{r['verdict']}**: {r['summary']}")
        rev += [f"  - {x['severity']} / {x['category']}: {x['description']}" for x in r["findings"]]
    L += ["", "## 8. Hasil review", _bullets(rev)]

    L += ["", "## 9. Masalah yang belum terselesaikan", _bullets(unresolved_issues(f))]

    L += ["", "## 10. Risiko", f"- Level risiko tindakan: **{t['risk_level']}**"
          + (" (memerlukan approval manusia)" if t["risk_level"] in {"high", "critical"} else ""),
          *[f"- {x}" for r in f["reviews"] for x in r["unresolved_risks"]]]

    models = list(dict.fromkeys(f"{r['provider']}/{r['model']} (konteks {r['num_ctx']})" for r in f["routing"]))
    L += ["", "## 11. Model dan provider yang digunakan", _bullets(models)]

    u = f["usage"]
    L += ["", "## 12. Penggunaan model atau biaya",
          f"- Pemanggilan: {u['calls']} · token prompt: {u['prompt_tokens']} · token jawaban: {u['completion_tokens']} · durasi: {u['duration_ms']} ms",
          f"- Biaya tercatat: IDR {u['cost_idr']:g} (provider lokal tidak berbiaya)"]

    L += ["", "## 13. Approval yang diperlukan atau diperoleh",
          _bullets([f"{a['status']} (risiko {a['risk_level']}, diminta {a['requested_by']}"
                    + (f", diputuskan {a['decided_by']} pada {a['decided_at']}" if a["decided_by"] else "")
                    + (f", alasan: {a['reason']}" if a["reason"] else "") + (", sudah dipakai" if a["used"] else "") + ")" for a in f["approvals"]])
          if f["approvals"] else ("- Tidak diperlukan (risiko rendah atau sedang)" if t["risk_level"] in {"low", "medium"} else NO_DATA)]

    ver = []
    if verification:
        ver.append(f"Verifikasi sistem: `{verification.get('method')}` → {'lulus' if verification.get('passed') else 'tidak lulus'}")
        if verification.get("criteria_checked") is False:
            ver.append("Acceptance criteria belum diverifikasi otomatis oleh task ini (perlu review independen).")
    ver += [f"Eksekusi tercatat: {len(f['executions'])} · tes: {len(f['test_runs'])} · review: {len(f['reviews'])}"]
    L += ["", "## 14. Bukti verifikasi", _bullets(ver)]

    L += ["", "## 15. Langkah berikutnya", _bullets(next_steps(f))]
    return "\n".join(L).strip() + "\n"


def build_task_report(session: Session, task_id: str) -> tuple[str, dict]:
    facts = gather_facts(session, task_id)
    return render_task_report(facts), facts


def project_summary(facts_list: list[dict]) -> str:
    """Ringkasan deterministik tingkat proyek, dipakai langsung dan sebagai bahan pembanding narasi model."""
    by_status: dict[str, int] = {}
    for f in facts_list:
        by_status[f["task"]["status"]] = by_status.get(f["task"]["status"], 0) + 1
    parts = [f"{n} {s}" for s, n in sorted(by_status.items())]
    runs = [r for f in facts_list for r in f["test_runs"]]
    tests = f" Pengujian: {sum(r['passed'] for r in runs)} lulus, {sum(r['failed'] for r in runs)} gagal dari {len(runs)} eksekusi tes." if runs else ""
    reviews = [r for f in facts_list for r in f["reviews"] if r["is_review_task"]]
    rev = f" Review: {sum(1 for r in reviews if r['verdict'] == 'approved')} disetujui, {sum(1 for r in reviews if r['verdict'] != 'approved')} meminta perubahan." if reviews else ""
    return f"Total {len(facts_list)} task: " + (", ".join(parts) or "tidak ada") + "." + tests + rev


def build_project_report(session: Session, project_id: str, task_ids: list[str] | None = None, exclude: str | None = None,
                         project_name: str = "") -> tuple[str, list[dict]]:
    q = select(Task.id).where(Task.project_id == project_id).order_by(Task.created_at, Task.id)
    ids = [i for i in (task_ids or list(session.scalars(q))) if i != exclude][:MAX_TASKS_IN_PROJECT_REPORT]
    facts = [gather_facts(session, i) for i in ids]
    L = [f"# Laporan Proyek{(': ' + project_name) if project_name else ''}", "", "## Daftar task", "",
         "| Task | Role | Status | Review |", "| --- | --- | --- | --- |"]
    L += [f"| {f['task']['title']} | {f['task']['role']} | {f['task']['status']} | {f['task']['review_status'] or '-'} |" for f in facts]
    L += ["", "---", ""]
    L += ["\n\n---\n\n".join(render_task_report(f).replace("# Laporan Task:", "### Task:", 1) for f in facts)]
    return "\n".join(L).strip() + "\n", facts


# Angka mandiri saja: tidak ikut angka di dalam UUID, hash commit, atau tanggal (bagian yang dipisahkan huruf atau tanda hubung)
_NUM = re.compile(r"(?<![\w.-])\d+(?![\w-])")


def fact_numbers(facts_list: list[dict]) -> set[str]:
    """Angka yang boleh muncul pada ringkasan model: hanya hitungan terstruktur dari database.

    Sengaja BUKAN seluruh teks laporan: teks itu memuat UUID, hash, dan jam yang kebetulan mengandung angka kecil
    apa pun, sehingga karangan model dapat lolos.
    """
    nums: set[int] = {len(facts_list)}
    by_status: dict[str, int] = {}
    for f in facts_list:
        t = f["task"]
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        nums |= {t["attempt_count"], len(f["files"]), len(f["executions"]), len(f["test_runs"]), len(f["reviews"]),
                 len(f["approvals"]), len(f["acceptance_criteria"]) if "acceptance_criteria" in f else len(t["acceptance_criteria"])}
        for r in f["test_runs"]:
            nums |= {r["total"], r["passed"], r["failed"], r["errors"], r["skipped"]}
        for r in f["reviews"]:
            nums |= {len(r["criteria"]), len(r["findings"]), len(r["unresolved_risks"])}
        u = f["usage"]
        nums |= {u["calls"], u["prompt_tokens"], u["completion_tokens"]}
    nums |= set(by_status.values())
    return {str(n) for n in nums}


def numbers_grounded(narrative: str, allowed: set[str]) -> bool:
    """Setiap angka mandiri pada narasi model harus ada di himpunan fakta; jika tidak, narasi dibuang."""
    return all(n in allowed for n in _NUM.findall(narrative))
