"""Satu-satunya jalur pemanggilan model. Menegakkan kebijakan biaya dan mencatat setiap pemanggilan."""
import asyncio
import hashlib
import logging

from app.config import Settings
from app.db.models import ModelUsage
from app.logging_config import correlation_id
from app.providers.base import GatewayBlocked, GenerateRequest, GenerateResult, ProviderError, ProviderErrorKind
from app.providers.registry import ProviderRegistry

logger = logging.getLogger("roihan.gateway")


class ModelGateway:
    def __init__(self, registry: ProviderRegistry, settings: Settings, session_factory):
        self._registry = registry
        self._settings = settings
        self._session_factory = session_factory
        # Model lokal berjalan di CPU yang sama; serialkan sesuai max_concurrent_tasks (Bagian 12.4)
        self._slots = asyncio.Semaphore(settings.max_concurrent_tasks)

    def _log(self, *, provider: str, model: str, req: GenerateRequest, purpose: str, status: str, is_paid: bool,
             error_kind: str | None = None, result: GenerateResult | None = None) -> None:
        row = ModelUsage(
            provider=provider, model=model, purpose=purpose, status=status, error_kind=error_kind,
            request_id=req.request_id, correlation_id=correlation_id.get(),
            prompt_sha256=hashlib.sha256(req.prompt.encode()).hexdigest()[:16], prompt_chars=len(req.prompt),
            prompt_tokens=result.usage.prompt_tokens if result else None,
            completion_tokens=result.usage.completion_tokens if result else None,
            duration_ms=result.usage.duration_ms if result else None,
            is_paid=is_paid, cost_idr=0.0,  # penyedia lokal tidak berbiaya; adapter berbayar harus mengisi biaya aktual
        )
        try:
            with self._session_factory() as s:
                s.add(row)
                s.commit()
        except Exception:
            logger.exception("gagal mencatat model_usage")

    def _block(self, name, model, req, purpose, is_paid, reason, message):
        self._log(provider=name, model=model, req=req, purpose=purpose, status="blocked", is_paid=is_paid, error_kind=reason)
        raise GatewayBlocked(reason, message)

    async def generate(self, provider_name: str, model: str, req: GenerateRequest, purpose: str = "adhoc") -> GenerateResult:
        entry = self._registry.get(provider_name)
        if entry is None:
            raise ProviderError(ProviderErrorKind.invalid_request, f"Provider '{provider_name}' tidak dikenal")
        args = (provider_name, model, req, purpose, entry.is_paid)

        if not entry.enabled:
            self._block(*args, "provider_disabled", f"Provider '{provider_name}' dinonaktifkan")
        if entry.is_paid and not self._settings.budget_allow_paid_calls:
            self._block(*args, "paid_calls_disabled", "Pemanggilan API berbayar dinonaktifkan oleh kebijakan anggaran")
        if entry.is_paid and getattr(self._settings, "require_approval_for_paid_calls", True):
            # Persetujuan manusia (Approval Center) baru tersedia di Phase 6: selalu tahan sampai ada.
            self._block(*args, "approval_required", "Pemanggilan API berbayar memerlukan approval")
        if not entry.implemented or entry.provider is None:
            self._block(*args, "not_implemented", f"Adapter untuk '{provider_name}' belum tersedia")

        async with self._slots:
            try:
                result = await entry.provider.generate(model, req)
            except ProviderError as e:
                status = "cancelled" if e.kind == ProviderErrorKind.cancelled else "error"
                self._log(provider=provider_name, model=model, req=req, purpose=purpose, status=status,
                          is_paid=False, error_kind=e.kind.value)
                raise
        self._log(provider=provider_name, model=model, req=req, purpose=purpose, status="ok", is_paid=False, result=result)
        return result

    async def cancel(self, request_id: str) -> bool:
        for e in self._registry.all():
            if e.provider is not None and await e.provider.cancel(request_id):
                return True
        return False
