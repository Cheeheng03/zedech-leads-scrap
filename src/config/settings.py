"""Application settings via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )

    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'leads.db'}"

    # Session limits (0 = unlimited, runs until all jobs done or manually stopped)
    session_limit: int = 0
    delay_min_ms: int = 2000
    delay_max_ms: int = 5000

    # Browser
    headless: bool = False

    # Scoring
    min_score_for_google_check: int = 5

    # Layers to scrape (comma-separated: "layer_1,layer_2,layer_3")
    scrape_layers: str = "layer_1"


settings = Settings()
