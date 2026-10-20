import asyncio
import hashlib

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.models import AppendOnlyError, ModelUsage
from app.db.session import create_db_engine, create_session_factory
from app.providers.base import GatewayBlocked, GenerateRequest, ProviderError, ProviderErrorKind as K
from app.providers.gateway import ModelGateway
from app.providers.registry import build_registry
from tests.conftest import TOKEN
from tests.fakes import FakeProvider


def make_gateway(migrated_db, tmp_path, providers, **settings_kw):
    settings = Settings(_env_file=None, app_local_token=TOKEN, database_url=migrated_db, data_dir=tmp_path, **settings_kw)
    factory = create_session_factory(create_db_engine(migrated_db))
    return ModelGateway(build_registry(settings, providers), settings, factory), factory


def rows(factory):
    with factory() as s:
        return list(s.scalars(select(ModelUsage).order_by(ModelUsage.created_at)))


def run(coro):
    return asyncio.run(coro)


def test_success_is_logged_without_storing_prompt(migrated_db, tmp_path):
    fake = FakeProvider()
    gw, factory = make_gateway(migrated_db, tmp_path, {"ollama": fake})
    res = run(gw.generate("ollama", "fake-model:1b", GenerateRequest("rahasia: sk-123"), purpose="uji"))
    assert res.text.startswith("jawaban:")
    [row] = rows(factory)
    assert (row.status, row.provider, row.purpose, row.is_paid, row.cost_idr) == ("ok", "ollama", "uji", False, 0.0)
    assert (row.prompt_tokens, row.completion_tokens, row.duration_ms) == (5, 7, 12)
    assert row.prompt_sha256 == hashlib.sha256(b"rahasia: sk-123").hexdigest()[:16] and row.prompt_chars == 15
    assert "sk-123" not in repr(vars(row))


def test_provider_errors_are_logged_and_reraised(migrated_db, tmp_path):
    fake = FakeProvider(error=ProviderError(K.unavailable, "mati"))
    gw, factory = make_gateway(migrated_db, tmp_path, {"ollama": fake})
    with pytest.raises(ProviderError):
        run(gw.generate("ollama", "m", GenerateRequest("hai")))
    [row] = rows(factory)
    assert (row.status, row.error_kind) == ("error", "unavailable")


def test_cancelled_is_logged_as_cancelled(migrated_db, tmp_path):
    fake = FakeProvider(error=ProviderError(K.cancelled, "batal"))
    gw, factory = make_gateway(migrated_db, tmp_path, {"ollama": fake})
    with pytest.raises(ProviderError):
        run(gw.generate("ollama", "m", GenerateRequest("hai")))
    assert rows(factory)[0].status == "cancelled"


def test_paid_provider_is_blocked_by_default_and_never_called(migrated_db, tmp_path):
    paid = FakeProvider(name="openai", is_paid=True)
    gw, factory = make_gateway(migrated_db, tmp_path, {"openai": paid}, openai_enabled=True, openai_api_key="k" * 10)
    with pytest.raises(GatewayBlocked) as e:
        run(gw.generate("openai", "gpt-x", GenerateRequest("hai")))
    assert e.value.reason == "paid_calls_disabled" and paid.calls == []
    [row] = rows(factory)
    assert (row.status, row.error_kind, row.is_paid) == ("blocked", "paid_calls_disabled", True)


def test_disabled_paid_provider_is_blocked_before_anything_else(migrated_db, tmp_path):
    paid = FakeProvider(name="openai", is_paid=True)
    gw, _ = make_gateway(migrated_db, tmp_path, {"openai": paid})
    with pytest.raises(GatewayBlocked) as e:
        run(gw.generate("openai", "gpt-x", GenerateRequest("hai")))
    assert e.value.reason == "provider_disabled" and paid.calls == []


def test_paid_provider_still_needs_approval_even_if_budget_allows(migrated_db, tmp_path):
    """Approval Center belum ada (Phase 6), jadi API berbayar tidak boleh jalan walau anggaran dibuka."""
    paid = FakeProvider(name="openai", is_paid=True)
    gw, _ = make_gateway(migrated_db, tmp_path, {"openai": paid}, budget_allow_paid_calls=True,
                         budget_monthly_limit=100000, openai_enabled=True, openai_api_key="k" * 10)
    with pytest.raises(GatewayBlocked) as e:
        run(gw.generate("openai", "gpt-x", GenerateRequest("hai")))
    assert e.value.reason == "approval_required" and paid.calls == []


def test_cloud_provider_without_adapter_is_blocked(migrated_db, tmp_path):
    gw, factory = make_gateway(migrated_db, tmp_path, {})
    for name in ("openai", "gemini", "anthropic"):
        with pytest.raises(GatewayBlocked):
            run(gw.generate(name, "m", GenerateRequest("hai")))
    assert [r.status for r in rows(factory)] == ["blocked"] * 3


def test_disabled_and_unknown_provider(migrated_db, tmp_path):
    fake = FakeProvider()
    gw, _ = make_gateway(migrated_db, tmp_path, {"ollama": fake}, ollama_enabled=False)
    with pytest.raises(GatewayBlocked) as e:
        run(gw.generate("ollama", "m", GenerateRequest("hai")))
    assert e.value.reason == "provider_disabled" and fake.calls == []
    with pytest.raises(ProviderError) as e2:
        run(gw.generate("tidak-ada", "m", GenerateRequest("hai")))
    assert e2.value.kind == K.invalid_request


def test_requests_are_serialised_by_max_concurrent_tasks(migrated_db, tmp_path):
    fake = FakeProvider(delay=0.05)
    gw, _ = make_gateway(migrated_db, tmp_path, {"ollama": fake}, max_concurrent_tasks=1)

    async def many():
        await asyncio.gather(*(gw.generate("ollama", "m", GenerateRequest(f"p{i}")) for i in range(4)))
    run(many())
    assert len(fake.calls) == 4 and fake.max_active == 1


def test_model_usage_is_append_only(migrated_db, tmp_path):
    gw, factory = make_gateway(migrated_db, tmp_path, {"ollama": FakeProvider()})
    run(gw.generate("ollama", "m", GenerateRequest("hai")))
    with factory() as s:
        row = s.scalars(select(ModelUsage)).one()
        row.status = "diubah"
        with pytest.raises(AppendOnlyError):
            s.commit()
        s.rollback()
        s.delete(row)
        with pytest.raises(AppendOnlyError):
            s.commit()
