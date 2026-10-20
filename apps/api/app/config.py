from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Konfigurasi aplikasi (Bagian 20). Divalidasi saat aplikasi mulai."""

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_mode: str = "local"
    app_env: str = "development"
    app_local_token: str = ""
    app_default_language: str = "id"

    database_url: str = f"sqlite:///{(REPO_ROOT / 'data' / 'database' / 'roihan.db').as_posix()}"

    ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = "qwen2.5-coder:7b"
    ollama_timeout_s: int = 600
    ai_max_tokens_cap: int = 2048
    ai_max_prompt_chars: int = 20000

    worker_enabled: bool = True
    worker_poll_interval_s: float = 1.0
    retry_backoff_base_s: float = 5.0

    openai_enabled: bool = False
    openai_api_key: str = ""
    gemini_enabled: bool = False
    gemini_api_key: str = ""
    anthropic_enabled: bool = False
    anthropic_api_key: str = ""

    budget_currency: str = "IDR"
    budget_monthly_limit: int = 0
    budget_allow_paid_calls: bool = False

    max_retries_per_task: int = 2
    max_concurrent_tasks: int = 1

    restrict_workspace_access: bool = True
    require_approval_for_external_actions: bool = True
    redact_secrets_in_logs: bool = True

    data_dir: Path = REPO_ROOT / "data"
    max_upload_mb: int = 10

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if len(self.app_local_token) < 16:
            raise ValueError("APP_LOCAL_TOKEN wajib diisi minimal 16 karakter (lihat .env.example)")
        if self.app_default_language not in {"id", "en"}:
            raise ValueError("APP_DEFAULT_LANGUAGE harus 'id' atau 'en'")
        for name in ("openai", "gemini", "anthropic"):
            if getattr(self, f"{name}_enabled") and not getattr(self, f"{name}_api_key"):
                raise ValueError(f"{name.upper()}_ENABLED=true memerlukan {name.upper()}_API_KEY")
        if self.budget_allow_paid_calls and self.budget_monthly_limit <= 0:
            raise ValueError("BUDGET_ALLOW_PAID_CALLS=true memerlukan BUDGET_MONTHLY_LIMIT > 0")
        if self.max_concurrent_tasks < 1 or self.max_retries_per_task < 0:
            raise ValueError("MAX_CONCURRENT_TASKS >= 1 dan MAX_RETRIES_PER_TASK >= 0")
        if self.ollama_timeout_s < 1 or self.ai_max_tokens_cap < 1 or self.ai_max_prompt_chars < 1:
            raise ValueError("OLLAMA_TIMEOUT_S, AI_MAX_TOKENS_CAP, AI_MAX_PROMPT_CHARS harus >= 1")
        if self.worker_poll_interval_s <= 0 or self.retry_backoff_base_s < 0:
            raise ValueError("WORKER_POLL_INTERVAL_S harus > 0 dan RETRY_BACKOFF_BASE_S >= 0")
        if self.max_upload_mb < 1:
            raise ValueError("MAX_UPLOAD_MB harus >= 1")
        return self

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def secret_values(self) -> list[str]:
        values = [self.app_local_token, self.openai_api_key, self.gemini_api_key, self.anthropic_api_key]
        return [v for v in values if v]


@lru_cache
def get_settings() -> Settings:
    return Settings()
