from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Credential fields that an empty-string environment variable must NOT shadow.
# Some shells export e.g. ANTHROPIC_API_KEY="" which pydantic prioritizes over
# the .env file; an explicitly-empty secret is never useful, so we backfill it
# from the .env file when present.
_BACKFILL_FIELDS = (
    "anthropic_api_key",
    "circle_api_key",
    "circle_entity_secret",
    "circle_wallet_set_id",
    "ata_funder_secret",
)


def _dotenv_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if not _ENV_FILE.exists():
        return values
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip().lower()] = val.strip()
    return values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    environment: str = "development"
    api_port: int = 8000

    # Persistence — defaults to local SQLite for zero-friction dev; use Postgres in prod.
    database_url: str = "sqlite:///./brewing.db"

    # Session validation (API is the identity source of truth). Shared secret with web.
    session_secret: str = "dev-insecure-change-me"
    session_algorithm: str = "HS256"

    # CORS
    web_origin: str = "http://localhost:3000"

    # Admin console is a *separate* surface from the product: it has no product
    # login and is gated by this shared secret (sent as X-Admin-Secret by the
    # standalone admin app). Blank = admin API disabled. Set ADMIN_SECRET.
    admin_secret: str = ""

    # Anthropic — Coordination Copilot + execution orchestration
    anthropic_api_key: str = ""
    copilot_model: str = "claude-opus-4-7"

    # Rate-limit pacemaker for downstream Claude calls (seconds)
    orchestration_pacemaker_seconds: float = 3.5
    # Hard cap on deliverable generation so a slow model can't hang the request
    # until an upstream proxy cuts it; on timeout execution uses the heuristic.
    deliverable_timeout_seconds: float = 28.0

    # Settlement provider selection (provider-agnostic domain; Circle is first impl)
    settlement_provider: str = "circle"

    # Circle Developer-Controlled Wallets (real testnet)
    circle_api_key: str = ""
    circle_entity_secret: str = ""
    circle_wallet_set_id: str = ""
    # USDC on Solana devnet via Circle DCW
    circle_blockchain: str = "SOL-DEVNET"

    # ATA pre-creation workaround. Circle's paymaster won't create destination
    # token accounts, so we create them ourselves with a funded devnet payer
    # (base58 secret) before depositing USDC. Blank = workaround disabled.
    ata_funder_secret: str = ""
    solana_rpc_url: str = "https://api.devnet.solana.com"

    # Platform revenue wallet. When set, the settlement fee is swept here on
    # release instead of being left in the per-objective escrow wallet. Blank =
    # fee stays in escrow (prior behaviour).
    platform_fee_wallet_address: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    dotenv = _dotenv_values()
    for field in _BACKFILL_FIELDS:
        if not getattr(settings, field) and dotenv.get(field):
            setattr(settings, field, dotenv[field])
    return settings
