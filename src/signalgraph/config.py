from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/signalgraph"
    test_database_url: str = "sqlite+aiosqlite:///test.db"

    anthropic_api_key: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    default_schedule_hours: int = 6
    backfill_days: int = 7

    model_config = {"env_prefix": "SIGNALGRAPH_", "extra": "ignore"}

    @model_validator(mode="before")
    @classmethod
    def _fill_from_unprefixed_env(cls, values):
        """Accept ANTHROPIC_API_KEY without the SIGNALGRAPH_ prefix."""
        import os

        if not values.get("anthropic_api_key"):
            values["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
        if not values.get("database_url") or values.get("database_url") == "postgresql+asyncpg://localhost:5432/signalgraph":
            val = os.environ.get("DATABASE_URL")
            if val:
                values["database_url"] = val
        return values


settings = Settings()
