from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/prisma_factsheet"
    redis_url: str = "redis://localhost:6379/0"

    # Cron runs after US market close (4 PM ET); timezone shifts it for Indian hours
    pipeline_cron: str = "0 22 * * 1-5"
    pipeline_timezone: str = "America/New_York"

    risk_free_rate: float = 0.05   # annual, used in Sharpe / Sortino / Treynor
    cache_ttl: int = 86400         # Redis TTL in seconds (24 h)
    admin_token: str = "changeme"  # set a strong secret before production

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
