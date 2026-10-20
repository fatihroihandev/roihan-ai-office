"""Agent Reporter. Laporan = fakta dari database (deterministik) + ringkasan opsional dari model yang divalidasi."""
import logging

from sqlalchemy import select

from app.db.models import Project, TaskDependency
from app.providers.base import GatewayBlocked, ProviderError
from app.reporting.builder import build_project_report, numbers_grounded, project_summary
from app.routing.router import RoutingError
from app.tasks.executors import ExecutionContext, Executor, ExecutorOutcome

logger = logging.getLogger("roihan.reporter")

NARRATIVE_SYSTEM = (
    "Kamu adalah Reporter di software house AI. Tulis ringkasan eksekutif 2 sampai 4 kalimat dalam bahasa Indonesia "
    "HANYA dari fakta yang diberikan. Dilarang menambahkan fakta, angka, atau kesimpulan yang tidak ada pada materi."
)


class ReporterExecutor:
    idempotent = True

    def __init__(self, text_executor: Executor):
        self._text = text_executor  # aksi lain (mis. documentation) memakai penulisan dokumen biasa

    async def run(self, ctx: ExecutionContext) -> ExecutorOutcome:
        t = ctx.task
        if t.action_type != "report":
            return await self._text.run(ctx)

        with ctx.session_factory() as s:
            deps = list(s.scalars(select(TaskDependency.depends_on_id).where(TaskDependency.task_id == t.id)))
            name = s.get(Project, t.project_id).name
            body, facts = build_project_report(s, t.project_id, deps or None, exclude=t.id, project_name=name)
        deterministic = project_summary(facts)

        summary, source = deterministic, "deterministik"
        try:
            res = await ctx.generate(NARRATIVE_SYSTEM, f"FAKTA:\n{body[:5000]}\n\nTulis ringkasan eksekutif.", max_tokens=300, temperature=0.1)
            text = res.text.strip()
            if text and not res.truncated and numbers_grounded(text, body):
                summary, source = text, "model (angka divalidasi terhadap fakta)"
        except (ProviderError, RoutingError, GatewayBlocked) as e:
            logger.info("narasi model dilewati: %s", e)  # laporan tetap dibuat dari fakta

        markdown = body.replace("\n## Daftar task", f"\n## Ringkasan\n\n{summary}\n\n_Sumber ringkasan: {source}._\n\n## Daftar task", 1)
        path = ctx.storage.write_report(t.project_id, f"laporan-{t.id}", markdown)
        return ExecutorOutcome(
            output=markdown, verified=True,
            verification={"method": "report_from_facts", "passed": True, "criteria_checked": False, "summary_source": source},
            result={"output": markdown, "report": path, "tasks_reported": len(facts)},
        )
