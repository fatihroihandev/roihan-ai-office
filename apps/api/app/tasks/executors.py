"""Executor per role. Hanya role yang benar-benar dapat dikerjakan yang terdaftar; sisanya diblokir secara jujur."""
import json
import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select

from app.config import Settings
from app.db.models import ProjectFile, Task, TaskDependency
from app.projects.storage import ProjectStorage
from app.sandbox.base import Sandbox
from app.workspace import git as workspace_git
from app.workspace.files import WorkspaceFiles
from app.providers.base import GenerateRequest, GenerateResult
from app.providers.gateway import ModelGateway
from app.routing.router import ModelRouter, TaskSnapshot
from app.tasks.catalog import ACTIONS, PLANNABLE_ROLES
from app.tasks.service import create_task

MASTER_EXCERPT_CHARS = 3000
DEP_OUTPUT_CHARS = 1500
DEP_TOTAL_CHARS = 3000


class ExecutorError(Exception):
    """Kegagalan eksekusi yang dinormalisasi. `retryable` menentukan apakah retry otomatis layak dicoba."""

    def __init__(self, kind: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.kind, self.message, self.retryable = kind, message, retryable


class ExecutorBlocked(Exception):
    """Task tidak dapat dikerjakan karena prasyarat belum ada (mis. sandbox). Task diblokir, bukan gagal."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason, self.message = reason, message


@dataclass
class ExecutorOutcome:
    output: str
    verified: bool
    verification: dict
    result: dict


@dataclass
class ExecutionContext:
    task: TaskSnapshot
    attempt_id: str
    session_factory: object
    gateway: ModelGateway
    router: ModelRouter
    settings: Settings
    storage: ProjectStorage
    sandbox: Sandbox | None = None
    provider: str | None = None
    model: str | None = None
    usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "duration_ms": 0, "calls": 0})

    async def generate(self, system: str, prompt: str, max_tokens: int = 512, temperature: float = 0.2,
                       json_schema: dict | None = None) -> GenerateResult:
        est = (len(system) + len(prompt)) // 3 + 50  # perkiraan konservatif token (campuran Indonesia/Inggris)
        decision = await self.router.choose(self.task, self.attempt_id, est, max_tokens)
        self.provider, self.model = decision.provider, decision.model
        req = GenerateRequest(prompt=prompt, system=system, max_tokens=max_tokens, temperature=temperature,
                              num_ctx=decision.num_ctx, request_id=self.attempt_id, json_schema=json_schema)
        res = await self.gateway.generate(decision.provider, decision.model, req, purpose=f"task:{self.task.role}")
        self.usage["calls"] += 1
        for k in ("prompt_tokens", "completion_tokens", "duration_ms"):
            self.usage[k] += getattr(res.usage, k) or 0
        return res

    def workspace(self) -> WorkspaceFiles:
        """Workspace proyek (workspace/source-code) beserta repositori Git-nya."""
        root = self.storage.project_dir(self.task.project_id) / "workspace" / "source-code"
        try:
            workspace_git.ensure_repo(root)
        except (workspace_git.GitError, OSError) as e:
            raise ExecutorError("git_error", f"Git tidak dapat disiapkan: {e}", retryable=False) from e
        return WorkspaceFiles(root)

    async def require_sandbox(self) -> Sandbox:
        if self.sandbox is None:
            raise ExecutorBlocked("sandbox_disabled", "Sandbox belum dikonfigurasi")
        st = await self.sandbox.status()
        if not st.available:
            raise ExecutorBlocked(st.reason or "sandbox_unavailable", st.message or "Sandbox tidak tersedia")
        return self.sandbox

    def master_excerpt(self) -> str:
        return read_master_excerpt(self.session_factory, self.storage, self.task.project_id)


class Executor(Protocol):
    idempotent: bool

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome: ...


# ---------------------------------------------------------------- konteks proyek

def read_master_excerpt(session_factory, storage: ProjectStorage, project_id: str, limit: int = MASTER_EXCERPT_CHARS) -> str:
    with session_factory() as s:
        f = s.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id, ProjectFile.kind == "master",
                                                ProjectFile.deleted_at.is_(None))
                      .order_by(ProjectFile.created_at.desc()).limit(1)).first()
        rel = f.relative_path if f else None
    if rel is None:
        return ""
    try:
        text = storage.resolve_file(project_id, rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text if len(text) <= limit else text[:limit] + "\n[...dipotong: hanya bagian awal dokumen yang disertakan...]"


def dependency_outputs(session_factory, task_id: str) -> str:
    with session_factory() as s:
        deps = s.scalars(select(Task).join(TaskDependency, TaskDependency.depends_on_id == Task.id)
                         .where(TaskDependency.task_id == task_id, Task.status == "completed")).all()
        chunks, total = [], 0
        for d in deps:
            out = ((d.result or {}).get("output") or "")[:DEP_OUTPUT_CHARS]
            if not out or total + len(out) > DEP_TOTAL_CHARS:
                continue
            chunks.append(f"### Hasil task '{d.title}' ({d.role})\n{out}")
            total += len(out)
    return "\n\n".join(chunks)


# ---------------------------------------------------------------- Manager: perencanaan

class PlanItem(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    role: Literal[tuple(PLANNABLE_ROLES)]  # type: ignore[valid-type]
    action_type: Literal[tuple(ACTIONS)]  # type: ignore[valid-type]
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=8)
    depends_on: list[str] = Field(default_factory=list)
    factors: dict | list[int] | None = None  # dict bernama, atau daftar ringkas 6 angka (urutan FACTOR_ORDER)

    @field_validator("title", "key")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tidak boleh kosong")
        return v


class Plan(BaseModel):
    tasks: list[PlanItem] = Field(min_length=1, max_length=12)


FACTOR_ORDER = ["complexity", "uncertainty", "technical_risk", "scope", "reasoning", "context_requirement"]


def factors_dict(raw) -> dict | None:
    """Terima dict atau daftar 6 angka ringkas (hemat token); selain itu abaikan agar jatuh ke nilai default."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and len(raw) == len(FACTOR_ORDER):
        return dict(zip(FACTOR_ORDER, raw))
    return None


def extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Tidak ada objek JSON pada jawaban")
    return json.loads(text[start:end + 1])


def parse_plan(text: str) -> Plan:
    """Validasi rencana: skema, kunci unik, dan dependensi hanya ke task sebelumnya (menjamin tidak ada siklus)."""
    try:
        plan = Plan.model_validate(extract_json(text))
    except ValidationError as e:
        detail = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:3])
        raise ExecutorError("invalid_plan", f"Rencana tidak valid: {detail}"[:400]) from e
    except ValueError as e:
        raise ExecutorError("invalid_plan", f"Rencana tidak valid: {str(e)[:300]}") from e
    seen: set[str] = set()
    for item in plan.tasks:
        if item.key in seen:
            raise ExecutorError("invalid_plan", f"Kunci task ganda: {item.key}")
        bad = [d for d in item.depends_on if d not in seen]
        if bad:
            raise ExecutorError("invalid_plan", f"Task '{item.key}' bergantung pada task yang belum didefinisikan: {bad}")
        seen.add(item.key)
    return plan


PLAN_SCHEMA = {
    "type": "object",
    "properties": {"tasks": {"type": "array", "minItems": 1, "maxItems": 6, "items": {
        "type": "object",
        "properties": {
            "key": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"},
            "role": {"type": "string", "enum": PLANNABLE_ROLES},
            "action_type": {"type": "string", "enum": ACTIONS},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "factors": {"type": "array", "items": {"type": "integer"}, "minItems": 6, "maxItems": 6},
        },
        "required": ["key", "title", "description", "role", "action_type", "acceptance_criteria", "depends_on", "factors"],
    }}},
    "required": ["tasks"],
}  # membatasi keluaran model lokal kecil agar role/action hanya berisi nilai yang sah

PLANNER_SYSTEM = (
    "Kamu adalah Manager di sebuah software house AI. Tugasmu memecah tujuan menjadi task yang terukur. "
    "Balas HANYA dengan satu objek JSON, tanpa penjelasan."
)


def planner_prompt(goal: str, master: str, error: str | None = None) -> str:
    parts = [
        f"TUJUAN:\n{goal}",
        f"DOKUMEN PROYEK (ringkasan awal):\n{master}" if master else "DOKUMEN PROYEK: (belum ada)",
        "Buat 3 sampai 6 task yang SINGKAT (jawaban harus ringkas). Format JSON:\n"
        '{"tasks":[{"key":"t1","title":"...","description":"maks 20 kata","role":"<role>","action_type":"<action>",'
        '"acceptance_criteria":["..."],"depends_on":[],"factors":[4,3,2,3,4,2]}]}',
        "factors = 6 angka 1-5 berurutan: complexity, uncertainty, technical_risk, scope, reasoning, context_requirement.",
        f"role yang diizinkan: {', '.join(PLANNABLE_ROLES)}",
        f"action_type yang diizinkan: {', '.join(ACTIONS)}",
        "Aturan: key unik; depends_on hanya boleh berisi key task yang MUNCUL SEBELUMNYA; "
        "acceptance_criteria 1-2 butir singkat yang dapat diperiksa; "
        "gunakan action_type berisiko (misalnya external_outreach, publish, spend) hanya jika benar-benar diperlukan.",
    ]
    if error:
        parts.append(f"Jawaban sebelumnya ditolak: {error}\nPerbaiki dan balas JSON saja.")
    return "\n\n".join(parts)


class ManagerPlanExecutor:
    idempotent = True  # perencanaan hanya menghasilkan draft task; aman diulang jika terinterupsi

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        if ctx.task.action_type != "planning":
            raise ExecutorError("unsupported_action", "Manager hanya mengerjakan task berjenis planning", retryable=False)
        goal, master, error = ctx.task.description or ctx.task.title, ctx.master_excerpt(), None
        plan = None
        for _ in range(2):  # satu kali koreksi dengan umpan balik galat
            res = await ctx.generate(PLANNER_SYSTEM, planner_prompt(goal, master, error), max_tokens=1500, temperature=0.2,
                                  json_schema=PLAN_SCHEMA)
            try:
                if res.truncated:
                    raise ExecutorError("invalid_plan", "Jawaban terpotong oleh batas token")
                plan = parse_plan(res.text)
                break
            except ExecutorError as e:
                error = e.message
        if plan is None:
            raise ExecutorError("invalid_plan", error or "Rencana tidak valid")

        with ctx.session_factory() as s:
            key_to_id: dict[str, str] = {}
            for item in plan.tasks:
                t = create_task(
                    s, project_id=ctx.task.project_id, title=item.title, description=item.description,
                    role=item.role, action_type=item.action_type, acceptance_criteria=item.acceptance_criteria,
                    depends_on=[key_to_id[d] for d in item.depends_on], factors=factors_dict(item.factors),
                    created_by="manager", parent_task_id=ctx.task.id,
                )
                key_to_id[item.key] = t.id
            s.commit()
        ids = list(key_to_id.values())
        return ExecutorOutcome(
            output=f"{len(ids)} task draft dibuat", verified=True,
            verification={"method": "plan_schema_and_dag", "passed": True},
            result={"output": f"{len(ids)} task draft dibuat", "created_task_ids": ids},
        )


# ---------------------------------------------------------------- Analyst dan Reporter: dokumen teks

ROLE_SYSTEM = {
    "analyst": "Kamu adalah Analyst di software house AI. Analisis kebutuhan, buat spesifikasi teknis ringkas, "
               "identifikasi risiko dan asumsi. Tandai informasi yang belum pasti sebagai 'belum terverifikasi'.",
    "reporter": "Kamu adalah Reporter/Documentation Agent di software house AI. Susun dokumentasi atau laporan yang "
                "akurat dan ringkas berdasarkan materi yang diberikan. Jangan menambahkan fakta yang tidak ada pada materi.",
}


class LLMTextExecutor:
    idempotent = True

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        t = ctx.task
        criteria = "\n".join(f"- {c}" for c in t.acceptance_criteria) or "- (tidak ada)"
        parts = [f"TASK: {t.title}", f"DESKRIPSI:\n{t.description or '-'}", f"ACCEPTANCE CRITERIA:\n{criteria}"]
        master = ctx.master_excerpt()
        if master:
            parts.append(f"DOKUMEN PROYEK:\n{master}")
        deps = dependency_outputs(ctx.session_factory, t.id)
        if deps:
            parts.append(f"HASIL TASK SEBELUMNYA:\n{deps}")
        parts.append("Jawab dalam bahasa Indonesia kecuali diminta lain. Tulis dalam format Markdown.")
        res = await ctx.generate(ROLE_SYSTEM[t.role], "\n\n".join(parts), max_tokens=768)

        text = res.text.strip()
        if not text:
            raise ExecutorError("empty_output", "Model menghasilkan jawaban kosong")
        if res.truncated:
            raise ExecutorError("output_truncated", "Jawaban terpotong oleh batas token; perkecil lingkup task", retryable=False)
        artifact = ctx.storage.write_artifact(t.project_id, t.id, text)
        return ExecutorOutcome(
            output=text, verified=True,
            # Hanya memeriksa kelengkapan keluaran; acceptance criteria belum diperiksa otomatis (Reviewer: Phase 6)
            verification={"method": "output_complete", "passed": True, "criteria_checked": False},
            result={"output": text, "artifact": artifact},
        )


def default_executors() -> dict[str, Executor]:
    # impor tunda: modul-modul ini bergantung pada berkas ini
    from app.engineering.agents import DeveloperExecutor, QAExecutor
    from app.reporting.agent import ReporterExecutor
    from app.marketing.agents import LeadIntakeExecutor, MarketResearchExecutor, SalesOutreachExecutor
    from app.review.reviewer import ReviewerExecutor

    text = LLMTextExecutor()
    return {"manager": ManagerPlanExecutor(), "analyst": text, "reporter": ReporterExecutor(text),
            "developer": DeveloperExecutor(), "qa": QAExecutor(), "reviewer": ReviewerExecutor(),
            "market_research": MarketResearchExecutor(), "lead_generation": LeadIntakeExecutor(),
            "sales_client_relations": SalesOutreachExecutor()}
