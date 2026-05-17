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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
