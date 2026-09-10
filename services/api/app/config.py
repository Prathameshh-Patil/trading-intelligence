from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# services/api/app/config.py -> app -> api -> services -> the repo root.
_REPO = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    anthropic_api_key: str

    # The served reach table. It lives under the desktop app today because
    # that app is the one that produced it by hand; `app/forecast.py` says
    # why this service reads that copy rather than making a second one, and
    # what is owed before the path stops looking like this.
    reach_table_path: Path = _REPO / "apps" / "desktop" / "public" / "fixtures" / "reach_table.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
