from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/signalgraph"
    test_database_url: str = "sqlite+aiosqlite:///test.db"

    anthropic_api_key: str = ""

    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    default_schedule_hours: int = 6
    backfill_days: int = 7

    model_config = {"env_prefix": "SIGNALGRAPH_"}


settings = Settings()
