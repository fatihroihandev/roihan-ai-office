"""Model Router (Bagian 9.4): memilih model berdasarkan kemampuan, konteks, risiko, dan anggaran."""
import asyncio
import re
from dataclasses import dataclass, field

from sqlalchemy import select

from app.config import Settings
from app.db.models import ModelCapability, RoutingDecision, Task
from app.providers.base import ProviderError, ProviderErrorKind
from app.providers.capabilities import sync_provider_models
from app.providers.registry import ProviderRegistry

MAX_NUM_CTX = 8192  # batas konteks yang dipakai: RAM perangkat terbatas (Bagian 11.2)
UNKNOWN_CONTEXT_CAP = 4096
NUM_CTX_STEPS = (4096, 6144, 8192)


@dataclass
class TaskSnapshot:
    """Salinan field task yang dibutuhkan router dan executor, agar tidak bergantung pada sesi DB."""

    id: str
    project_id: str
    title: str
    description: str
    role: str
    action_type: str
    acceptance_criteria: list
    risk_level: str
    requires_approval: bool
    approved: bool
    difficulty_score: float | None
    difficulty_category: str | None
    preferred_model: str | None
    requires_tools: bool
    priority: int
    params: dict | None = None
    parent_task_id: str | None = None
    created_by: str = "ceo"

    @classmethod
    def from_task(cls, t: Task) -> "TaskSnapshot":
        return cls(t.id, t.project_id, t.title, t.description, t.role, t.action_type, list(t.acceptance_criteria or []),
                   t.risk_level, t.requires_approval, t.approved, t.difficulty_score, t.difficulty_category,
                   t.preferred_model, t.requires_tools, t.priority, dict(t.params) if t.params else None,
                   getattr(t, "parent_task_id", None), getattr(t, "created_by", "ceo"))


class RoutingError(Exception):
    """Tidak ada rute yang sah. Tidak dapat di-retry tanpa perubahan konfigurasi atau persetujuan."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class RouteDecision:
    decision_id: str
    provider: str
    model: str
    num_ctx: int
    reasons: list = field(default_factory=list)


class ModelRouter:
    def __init__(self, registry: ProviderRegistry, settings: Settings, session_factory):
        self._registry = registry
        self._settings = settings
        self._session_factory = session_factory

    async def _healthy_providers(self):
        entries = [e for e in self._registry.all()
                   if e.enabled and e.implemented and e.provider is not None
                   and (not e.is_paid or self._settings.budget_allow_paid_calls)]
        if not entries:
            raise RoutingError("no_active_provider", "Tidak ada provider aktif yang diizinkan kebijakan anggaran")
        results = await asyncio.gather(*(e.provider.health_check() for e in entries))
        healthy = [e for e, h in zip(entries, results) if h.status == "up"]
        if not healthy:
            raise ProviderError(ProviderErrorKind.unavailable, "Semua provider aktif tidak dapat dihubungi")
        return healthy

    async def _ensure_registry(self, entries) -> None:
        for e in entries:
            with self._session_factory() as s:
                known = s.scalar(select(ModelCapability.id).where(ModelCapability.provider == e.name,
                                                                  ModelCapability.available.is_(True)).limit(1))
            if known is None:
                await sync_provider_models(self._session_factory, e, self._settings.data_dir)

    async def choose(self, task: TaskSnapshot, attempt_id: str | None, prompt_tokens: int, max_tokens: int) -> RouteDecision:
        # 5. risk policy: task yang butuh approval tidak boleh dieksekusi tanpa approval
        if task.requires_approval and not task.approved:
            raise RoutingError("approval_required", f"Task berisiko {task.risk_level} memerlukan approval")

        healthy = await self._healthy_providers()          # 1-2. provider aktif dan sehat
        await self._ensure_registry(healthy)
        names = [e.name for e in healthy]
        with self._session_factory() as s:                  # 3. kemampuan model
            rows = list(s.scalars(select(ModelCapability).where(ModelCapability.provider.in_(names),
                                                                ModelCapability.available.is_(True))))

        need = prompt_tokens + max_tokens
        candidates, eligible = [], []
        for m in rows:
            why = []
            if m.is_paid and not self._settings.budget_allow_paid_calls:
                why.append("paid_calls_disabled")
            if task.requires_tools and m.supports_tools is not True:
                why.append("tools_unsupported" if m.supports_tools is False else "tools_unknown")
            cap = min(MAX_NUM_CTX, m.context_limit or UNKNOWN_CONTEXT_CAP)  # 4. batas konteks
            if need > cap:
                why.append(f"context_exceeded(need={need},cap={cap})")
            candidates.append({"provider": m.provider, "model": m.model_id, "eligible": not why, "rejected_because": why})
            if not why:
                eligible.append((m, cap))

        if not eligible:
            raise RoutingError("no_eligible_model", "Tidak ada model yang memenuhi syarat: " + "; ".join(
                f"{c['model']} ({', '.join(c['rejected_because'])})" for c in candidates) if candidates
                else "Registri model kosong")

        heavy = task.difficulty_category in {"heavy", "critical"}
        light = task.difficulty_category == "light"
        default_model = self._settings.ollama_default_model

        def parameter_size(model) -> float | None:
            details = model.details or {}
            raw = details.get("parameter_size") or model.model_id
            match = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[bB](?:\b|$)", str(raw))
            return float(match.group(1)) if match else None

        def rank(item):
            m, _ = item
            size = parameter_size(m)
            # Task ringan menghemat memori/waktu dengan model kecil; task berat memakai model terbesar.
            size_rank = (size if light else -size if heavy else 0) if size is not None else 0
            return (m.model_id != task.preferred_model,                      # preferensi eksplisit
                    size_rank,
                    m.validation_status != "benchmarked",                    # hasil benchmark untuk tugas setara
                    -(m.context_limit or 0) if heavy else 0,                 # task berat: konteks terbesar
                    m.model_id != getattr(self._settings, f"{m.provider}_default_model", default_model), m.model_id)
        chosen, cap = sorted(eligible, key=rank)[0]

        reasons = [f"difficulty={task.difficulty_category}({task.difficulty_score})", f"risk={task.risk_level}",
                   f"validation={chosen.validation_status}"]
        if task.preferred_model == chosen.model_id:
            reasons.append("preferred_model")
        num_ctx = next((n for n in NUM_CTX_STEPS if n >= need and n <= cap), min(cap, MAX_NUM_CTX))

        with self._session_factory() as s:                  # 8. catat routing decision
            dec = RoutingDecision(task_id=task.id, attempt_id=attempt_id, difficulty_score=task.difficulty_score,
                                  difficulty_category=task.difficulty_category, risk_level=task.risk_level,
                                  provider=chosen.provider, model=chosen.model_id, num_ctx=num_ctx,
                                  candidates=candidates, reasons=reasons)
            s.add(dec)
            s.commit()
            decision_id = dec.id
        return RouteDecision(decision_id, chosen.provider, chosen.model_id, num_ctx, reasons)
