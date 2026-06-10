"""Settlement provider selection — keeps the domain provider-agnostic."""

from functools import lru_cache

from app.config import get_settings
from app.domain.settlement.provider import (
    CUSTODIAL,
    NON_CUSTODIAL,
    EscrowRef,
    NonCustodialSettlementProvider,
    SettlementConfigError,
    SettlementProvider,
    TenantEscrowAccount,
    TransferResult,
    TxProof,
    WalletRef,
)

__all__ = [
    "CUSTODIAL",
    "NON_CUSTODIAL",
    "EscrowRef",
    "NonCustodialSettlementProvider",
    "SettlementConfigError",
    "SettlementProvider",
    "TenantEscrowAccount",
    "TransferResult",
    "TxProof",
    "WalletRef",
    "get_settlement_provider",
]


@lru_cache
def get_settlement_provider() -> SettlementProvider:
    name = get_settings().settlement_provider.lower()
    if name == "circle":
        from app.domain.settlement.circle_provider import CircleSettlementProvider

        return CircleSettlementProvider()
    if name in ("noncustodial", "non_custodial", "noncustodial-solana"):
        from app.domain.settlement.noncustodial_provider import (
            NonCustodialSolanaProvider,
        )

        return NonCustodialSolanaProvider()
    raise ValueError(f"Unknown settlement provider: {name!r}")
