from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Anthropic — Coordination Copilot + execution orchestration
    anthropic_api_key: str = ""
    copilot_model: str = "claude-opus-4-7"

    # Rate-limit pacemaker for downstream Claude calls (seconds)
    orchestration_pacemaker_seconds: float = 3.5

    # Settlement provider selection (provider-agnostic domain; Circle is first impl)
    settlement_provider: str = "circle"

    # Circle Developer-Controlled Wallets (real testnet)
    circle_api_key: str = ""
    circle_entity_secret: str = ""
    circle_wallet_set_id: str = ""
    # USDC on Solana devnet via Circle DCW
    circle_blockchain: str = "SOL-DEVNET"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
