"""Settlement provider selection — keeps the domain provider-agnostic."""

from functools import lru_cache

from app.config import get_settings
from app.domain.settlement.provider import (
    EscrowRef,
    SettlementProvider,
    TransferResult,
    WalletRef,
)

__all__ = [
    "EscrowRef",
    "SettlementProvider",
    "TransferResult",
    "WalletRef",
    "get_settlement_provider",
]


@lru_cache
def get_settlement_provider() -> SettlementProvider:
    name = get_settings().settlement_provider.lower()
    if name == "circle":
        from app.domain.settlement.circle_provider import CircleSettlementProvider

        return CircleSettlementProvider()
    raise ValueError(f"Unknown settlement provider: {name!r}")
