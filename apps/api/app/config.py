from functools import lru_cache
from pathlib import Path
from typing import Literal

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

    database_url: str = "postgresql+psycopg://roihan:roihan@127.0.0.1:5432/roihan"

    ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_default_model: str = "qwen2.5-coder:7b"
    ollama_timeout_s: int = 600
    ai_max_tokens_cap: int = 2048
    ai_max_prompt_chars: int = 20000

    sandbox_backend: str = "none"  # none | wsl
    sandbox_wsl_distro: str = "Ubuntu"
    sandbox_timeout_s: int = 60
    sandbox_memory_mb: int = 768
    sandbox_max_output_kb: int = 64

    approval_ttl_hours: int = 24

    # Kebijakan data prospek (Bagian 5 dan 15). Nilai bawaan adalah USULAN yang dapat diubah CEO lewat konfigurasi.
    lead_allowed_sources: str = "public_website,public_registry,referral,inbound,event,manual"
    lead_retention_no_interaction_days: int = 180
    lead_retention_after_interaction_days: int = 730
    lead_retention_auto_apply: bool = False   # bawaan: tandai yang jatuh tempo, anonimisasi menunggu keputusan CEO
    lead_min_score_for_sales: int = 40

    # Aktivitas eksternal (Phase 9): usulan bawaan yang dapat diubah CEO. Tidak ada konektor pengiriman otomatis.
    outreach_allowed_channels: str = "email"
    outreach_min_days_between_contacts: int = 14   # jarak minimal antar pesan keluar ke prospek yang sama
    outreach_max_per_day: int = 10
    content_allowed_channels: str = "blog,website,linkedin,instagram,newsletter"
    content_max_publish_per_day: int = 5

    worker_enabled: bool = True
    worker_poll_interval_s: float = 1.0
    retry_backoff_base_s: float = 5.0

    power_pause_grace_s: float = 20.0          # lama menunggu task aktif selesai sendiri sebelum dihentikan saat OFF
    power_interrupt_wait_s: float = 10.0       # lama menunggu task benar-benar berhenti setelah sinyal pembatalan
    power_checkpoint_interval_s: float = 20.0  # jeda checkpoint berkala selama task berjalan (0 = nonaktif)
    power_checkpoint_keep: int = 5             # jumlah checkpoint terbaru per task yang disimpan

    web_access_enabled: bool = False       # akses web agent: mati secara bawaan, dinyalakan CEO di AI Control Center
    web_daily_limit: int = 100             # maks. permintaan web (cari + ambil halaman) per hari
    web_search_provider: Literal["brave", "tavily"] = "brave"
    brave_api_key: str = ""
    tavily_api_key: str = ""
    web_timeout_s: float = 15.0
    web_max_bytes: int = 500_000
    web_max_page_chars: int = 6000

    backup_keep: int = 14
    backup_include_projects: bool = True
    backup_max_project_mb: int = 500

    openai_enabled: bool = False
    openai_api_key: str = ""
    gemini_enabled: bool = False
    gemini_api_key: str = ""
    gemini_default_model: str = "gemini-3.5-flash-lite"
    gemini_pro_model: str = "gemini-3.5-flash-lite"
    anthropic_enabled: bool = False
    anthropic_api_key: str = ""

    budget_currency: str = "IDR"
    budget_monthly_limit: int = 0
    budget_allow_paid_calls: bool = False

    max_retries_per_task: int = 2
    max_concurrent_tasks: int = 1

    restrict_workspace_access: bool = True
    require_approval_for_external_actions: bool = True
    require_approval_for_paid_calls: bool = True
    redact_secrets_in_logs: bool = True

    data_dir: Path = REPO_ROOT / "data"
    max_upload_mb: int = 10

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Single-Owner Authentication (Addendum v2.1)
    owner_email: str = ""
    bootstrap_token: str = ""
    session_ttl_days: int = 30
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    max_failed_logins: int = 5
    lockout_minutes: int = 15

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
        if self.sandbox_backend not in {"none", "wsl"}:
            raise ValueError("SANDBOX_BACKEND harus 'none' atau 'wsl'")
        if self.sandbox_timeout_s < 1 or self.sandbox_memory_mb < 64 or self.sandbox_max_output_kb < 1:
            raise ValueError("SANDBOX_TIMEOUT_S >= 1, SANDBOX_MEMORY_MB >= 64, SANDBOX_MAX_OUTPUT_KB >= 1")
        allowed = {"public_website", "public_registry", "referral", "inbound", "event", "manual"}
        listed = {x.strip() for x in self.lead_allowed_sources.split(",") if x.strip()}
        if not listed or not listed <= allowed:
            raise ValueError(f"LEAD_ALLOWED_SOURCES harus himpunan bagian dari {sorted(allowed)} dan tidak boleh kosong")
        if self.lead_retention_no_interaction_days < 1 or self.lead_retention_after_interaction_days < 1:
            raise ValueError("LEAD_RETENTION_* harus >= 1 hari")
        if not 0 <= self.lead_min_score_for_sales <= 100:
            raise ValueError("LEAD_MIN_SCORE_FOR_SALES harus 0..100")
        for name in ("outreach_allowed_channels", "content_allowed_channels"):
            if not [c for c in getattr(self, name).split(",") if c.strip()]:
                raise ValueError(f"{name.upper()} tidak boleh kosong")
        if self.outreach_min_days_between_contacts < 0 or self.outreach_max_per_day < 0 or self.content_max_publish_per_day < 0:
            raise ValueError("OUTREACH_* dan CONTENT_MAX_PUBLISH_PER_DAY tidak boleh negatif")
        if self.approval_ttl_hours < 1:
            raise ValueError("APPROVAL_TTL_HOURS harus >= 1")
        if self.power_pause_grace_s < 0 or self.power_interrupt_wait_s <= 0 or self.power_checkpoint_interval_s < 0 or self.power_checkpoint_keep < 1:
            raise ValueError("POWER_* tidak valid")
        if not 1 <= self.web_daily_limit <= 5000 or self.web_timeout_s <= 0 or self.web_max_bytes < 1000 or self.web_max_page_chars < 500:
            raise ValueError("WEB_* tidak valid")
        if self.backup_keep < 1 or self.backup_max_project_mb < 1:
            raise ValueError("backup_keep dan backup_max_project_mb harus positif")
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
        values = [self.app_local_token, self.openai_api_key, self.gemini_api_key, self.anthropic_api_key,
                  self.brave_api_key, self.tavily_api_key, self.bootstrap_token]
        return [v for v in values if v]


@lru_cache
def get_settings() -> Settings:
    return Settings()
