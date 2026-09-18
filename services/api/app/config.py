import json
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/api/app/config.py -> app -> api -> services -> the repo root.
_REPO = Path(__file__).resolve().parents[3]


class JwtKey(dict):
    """`{"kid": ..., "private_pem": ... | None, "public_pem": ...}`.

    A plain dict subclass so the JSON in `.env` round-trips without a schema
    the settings loader has to be taught about.
    """


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str
    anthropic_api_key: str

    # The served reach table. It lives under the desktop app today because
    # that app is the one that produced it by hand; `app/forecast.py` says
    # why this service reads that copy rather than making a second one, and
    # what is owed before the path stops looking like this.
    reach_table_path: Path = (
        _REPO / "apps" / "desktop" / "public" / "fixtures" / "reach_table.json"
    )

    # --- auth -----------------------------------------------------------
    # Ed25519 signing keys. A JSON list so rotation is "add the new key,
    # switch `jwt_active_kid`, drop the old one once every access token it
    # signed has expired (15 minutes later)". Old public keys stay in the
    # list so tokens they signed still verify during that window.
    #   [{"kid": "2026-09", "private_pem": "-----BEGIN PRIVATE KEY-----...",
    #     "public_pem": "-----BEGIN PUBLIC KEY-----..."}]
    # `uv run python -m app.cli gen-jwt-key` prints one.
    jwt_keys: list[dict[str, str | None]] = []
    jwt_active_kid: str = ""
    jwt_issuer: str = "vision-hub"
    jwt_audience: str = "vision-hub"
    access_ttl_seconds: int = 15 * 60
    refresh_ttl_days: int = 30
    refresh_cookie_name: str = "vh_refresh"
    # The cookie is scoped to this path so it is never sent to a data route.
    refresh_cookie_path: str = "/api/v1/auth"
    cookie_secure: bool = False
    cookie_domain: str | None = None

    # Browser origins that may call this API with credentials -- the customer
    # site and the admin portal. The extension/Tauri/localhost patterns in
    # `main.py` are kept separately as a regex.
    cors_origins: list[str] = []

    # Fernet key for licence keys at rest. `gen-jwt-key` prints one of these
    # too. Required outside tests because `/keys/mine` has to decrypt.
    key_encryption_secret: str = ""

    # Where payment-proof uploads land. Served back only to the owner or an
    # admin, never as a public static path.
    proof_dir: Path = Path("var/proofs")

    # Token buckets on the auth routes: N requests per window, per IP and per
    # email. In-memory -- one instance today; Redis is the multi-instance path.
    rate_limit_auth_per_minute: int = 10

    # Bootstrap: on startup, if this email exists, promote it to admin. A
    # convenience for a fresh deployment; `app.cli create-admin` is the
    # deliberate route.
    bootstrap_admin_email: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("jwt_keys", "cors_origins", mode="before")
    @classmethod
    def _parse_json_list(cls, value: object) -> object:
        # pydantic-settings already decodes JSON for complex fields, but an
        # empty string in `.env` should mean "none", not a parse error.
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return json.loads(value)
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()

if settings.is_production and not settings.cookie_secure:
    # Fail at import, not at the first login: a refresh cookie sent over plain
    # HTTP in production is a session handed to the network.
    raise RuntimeError("COOKIE_SECURE must be true when APP_ENV=production")
