"""Provider-agnostic settlement abstraction.

The domain depends on `SettlementProvider`, never on a concrete chain or
custodian. Circle is the first implementation; others can be added without
touching governance, escrow, or orchestration logic. Value objects below are
deliberately chain-neutral (no Circle/Solana types leak into the domain).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class WalletRef:
    """A settlement wallet, identified opaquely by the provider."""

    provider_wallet_id: str
    address: str
    blockchain: str


@dataclass(frozen=True)
class EscrowRef:
    """An objective-scoped governed escrow position."""

    provider_escrow_id: str
    address: str
    amount: Decimal
    lock_tx_ref: str | None = None


@dataclass(frozen=True)
class TransferResult:
    """Outcome of a value movement, with an observable settlement reference."""

    tx_ref: str
    amount: Decimal
    explorer_url: str | None = None


class SettlementProvider(ABC):
    """Contract every settlement implementation must satisfy."""

    name: str

    @abstractmethod
    def provision_treasury_wallet(self, workspace_id: str) -> WalletRef:
        """Create an isolated programmable settlement wallet for a workspace."""

    @abstractmethod
    def get_balance(self, wallet: WalletRef) -> Decimal:
        """Return the available USDC balance for a wallet."""

    @abstractmethod
    def lock_escrow(
        self, treasury: WalletRef, amount: Decimal, objective_id: str
    ) -> EscrowRef:
        """Move funds from the treasury into a governed objective-level escrow."""

    @abstractmethod
    def release_escrow(self, escrow: EscrowRef, payee: WalletRef) -> TransferResult:
        """Settle escrowed funds to the payee on governance approval."""

    @abstractmethod
    def slash_escrow(self, escrow: EscrowRef, treasury: WalletRef) -> TransferResult:
        """Return/redirect escrowed funds when execution is invalidated."""
