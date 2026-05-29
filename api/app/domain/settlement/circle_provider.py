"""Circle Developer-Controlled Wallets implementation of SettlementProvider.

USDC settlement on Solana devnet. Escrow is wallet-based for the MVP: each
objective gets its own programmable escrow wallet, so lock/release/slash are
real, on-chain, explorer-visible transfers. A custom on-chain escrow program
is a later upgrade and does not change this interface.
"""

from __future__ import annotations

from decimal import Decimal

from app.config import get_settings
from app.domain.settlement.provider import (
    EscrowRef,
    SettlementProvider,
    TransferResult,
    WalletRef,
)


class SettlementConfigError(RuntimeError):
    """Raised when Circle credentials are not configured."""


class CircleSettlementProvider(SettlementProvider):
    name = "circle"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    def _client_or_raise(self):
        if self._client is not None:
            return self._client
        s = self.settings
        if not (s.circle_api_key and s.circle_entity_secret and s.circle_wallet_set_id):
            raise SettlementConfigError(
                "Circle credentials missing: set CIRCLE_API_KEY, "
                "CIRCLE_ENTITY_SECRET, CIRCLE_WALLET_SET_ID."
            )
        # Imported lazily so the app boots without the SDK configured.
        from circle.web3 import developer_controlled_wallets, utils

        self._client = utils.init_developer_controlled_wallets_client(
            api_key=s.circle_api_key, entity_secret=s.circle_entity_secret
        )
        self._dcw = developer_controlled_wallets
        return self._client

    def provision_treasury_wallet(self, workspace_id: str) -> WalletRef:
        raise NotImplementedError(
            "CircleSettlementProvider.provision_treasury_wallet pending wiring"
        )

    def get_balance(self, wallet: WalletRef) -> Decimal:
        raise NotImplementedError(
            "CircleSettlementProvider.get_balance pending wiring"
        )

    def lock_escrow(
        self, treasury: WalletRef, amount: Decimal, objective_id: str
    ) -> EscrowRef:
        raise NotImplementedError(
            "CircleSettlementProvider.lock_escrow pending wiring"
        )

    def release_escrow(self, escrow: EscrowRef, payee: WalletRef) -> TransferResult:
        raise NotImplementedError(
            "CircleSettlementProvider.release_escrow pending wiring"
        )

    def slash_escrow(self, escrow: EscrowRef, treasury: WalletRef) -> TransferResult:
        raise NotImplementedError(
            "CircleSettlementProvider.slash_escrow pending wiring"
        )
