import pytest
from pydantic import ValidationError

from app.config import Settings

TOKEN = "token-uji-1234567890"


def make(**kw):
    return Settings(_env_file=None, app_local_token=TOKEN, **kw)


def test_defaults_are_local_first_and_free():
    s = make()
    assert s.ollama_enabled and not s.budget_allow_paid_calls
    assert not (s.openai_enabled or s.gemini_enabled or s.anthropic_enabled)
    assert s.max_concurrent_tasks == 1 and s.max_retries_per_task == 2


def test_token_required():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_local_token="pendek")


def test_cloud_provider_requires_key():
    with pytest.raises(ValidationError):
        make(openai_enabled=True)


def test_paid_calls_require_budget():
    with pytest.raises(ValidationError):
        make(budget_allow_paid_calls=True, budget_monthly_limit=0)


def test_language_must_be_id_or_en():
    with pytest.raises(ValidationError):
        make(app_default_language="fr")
