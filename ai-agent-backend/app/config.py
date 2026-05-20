"""Application settings loaded from environment / .env file."""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Postgres ----
    postgres_user: str = "kofon"
    postgres_password: str = "kofon_dev_password"
    postgres_db: str = "kofon_chatbot"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Direct override; if unset we compose from the parts above.
    database_url: str | None = None

    # ---- App ----
    app_env: str = Field(default="development")
    app_log_level: str = Field(default="INFO")

    # ---- DeepSeek (LLM provider) ----
    # Default models follow BACKEND_PLAN §3.5 — cheap model for narrow nodes,
    # reasoner kept available for harder reasoning in Phase 3.
    deepseek_api_key: str = ""
    deepseek_chat_model: str = "deepseek-chat"
    deepseek_reasoner_model: str = "deepseek-reasoner"

    # ---- Embeddings (Phase 3) ----
    # Provider for product/problem text embeddings. Three values:
    #   'hash'      — deterministic, non-semantic. Zero-config; CI/dev default.
    #   'bge-m3'    — local via `sentence-transformers`. Production-quality;
    #                  first run downloads ~2 GB.
    #   'dashscope' — Alibaba Qwen text-embedding-v3 (requires DASHSCOPE_API_KEY).
    # See `app/embeddings.py` and `memory/project-china-llm-constraint.md`.
    embedding_provider: str = "hash"

    # ---- Phase 4: side effects (CRM + email) ----
    # CRM provider. Default `log` writes only to the `crm_calls` audit
    # table — fine for demo / CI. Set `zoho` to enable the real adapter.
    # See `app/crm/` and `memory/project-kofon-chatbot.md` Phase 4 notes.
    crm_provider: str = "log"

    # Zoho — required when CRM_PROVIDER=zoho. Get these from
    # https://api-console.zoho.com (or zoho.com.cn for China).
    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_refresh_token: str = ""
    # Region: us | eu | in | au | jp | cn. Kofon will likely use 'cn'.
    zoho_region: str = "us"
    # Optional explicit overrides — handy for sandbox / proxy setups.
    zoho_accounts_url: str | None = None
    zoho_api_url: str | None = None

    # Email provider. Default `log` records would-be sends in
    # `email_calls`. `aliyun` enables Aliyun DirectMail.
    mail_provider: str = "log"

    aliyun_access_key_id: str = ""
    aliyun_access_key_secret: str = ""
    aliyun_dm_region: str = "cn-hangzhou"
    aliyun_dm_account_name: str = ""
    aliyun_dm_from_alias: str = ""

    # Side-effect orchestration knobs.
    # When True (default), CRM / email failures are swallowed and logged
    # — the user still sees the terminal card. Flip to False in
    # production-with-monitoring once alerting is in place.
    sideeffects_soft_fail: bool = True
    # Path to the routing matrix YAML; resolved relative to the backend
    # working directory if not absolute.
    routing_matrix_path: str = "app/sideeffects/routing.yaml"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def checkpointer_database_url(self) -> str:
        """Sync-style URL for langgraph-checkpoint-postgres (psycopg driver).

        The checkpointer uses psycopg, not asyncpg, so the URL scheme is
        plain `postgresql://`. Same database as the app — just a different
        driver pointing at it.
        """
        if self.database_url:
            return self.database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
