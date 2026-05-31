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


class SettlementConfigError(RuntimeError):
    """Raised when a settlement provider is not usably configured.

    Chain- and provider-neutral on purpose: the domain catches this without
    importing any concrete provider, so a provider swap never changes the
    error-handling surface above the SettlementProvider boundary.
    """


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


@dataclass(frozen=True)
class TxProof:
    """Resolved on-chain proof for a previously submitted settlement transfer.

    `tx_ref` is the provider's internal id; `tx_hash` is the on-chain signature
    that makes the movement independently verifiable on a block explorer.
    """

    tx_ref: str
    state: str
    tx_hash: str | None = None
    explorer_url: str | None = None


@dataclass(frozen=True)
class TenantEscrowAccount:
    """A tenant-scoped escrow account in the non-custodial model.

    Unlike the custodial `EscrowRef` (where the provider holds the keys), a
    tenant escrow account's signing authority is the tenant's own agentic
    wallet. Brewing only references the account; it never holds the keys.
    """

    address: str
    controller_wallet: str  # the agentic wallet that holds signing authority
    objective_id: str
    deploy_tx_ref: str | None = None


# Recognized custody models. "custodial": the provider holds keys to escrow
# funds (Circle Developer-Controlled Wallets today). "non_custodial": escrow is
# a tenant-scoped account controlled by the tenant's agentic wallet; Brewing
# never holds, transmits, or custodies the funds.
CUSTODIAL = "custodial"
NON_CUSTODIAL = "non_custodial"


class SettlementProvider(ABC):
    """Contract every settlement implementation must satisfy."""

    name: str
    # Declares whether this provider takes custody of funds. The domain stamps
    # this onto each escrow so the trust model is explicit and auditable.
    custody_model: str = CUSTODIAL

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

    @abstractmethod
    def get_transaction_proof(self, tx_ref: str) -> TxProof:
        """Resolve a submitted transfer to its on-chain proof (signature + URL)."""


class NonCustodialSettlementProvider(SettlementProvider, ABC):
    """Seam for providers where Brewing never holds the keys to escrow funds.

    Escrow is deployed as a tenant-scoped account (or per-tenant contract)
    whose signing authority is the tenant's own agentic wallet. Brewing
    references and observes the account but cannot move funds unilaterally —
    release/slash are authorized by the controller wallet. This is the target
    trust model; the full key-custody migration is a follow-on task. The
    abstraction is defined now so escrow, governance, and settlement logic can
    be written against it without coupling to a custodian.
    """

    custody_model: str = NON_CUSTODIAL

    @abstractmethod
    def deploy_tenant_escrow(
        self, controller_wallet: WalletRef, amount: Decimal, objective_id: str
    ) -> TenantEscrowAccount:
        """Deploy a tenant-scoped escrow controlled by the agentic wallet.

        The controller wallet — not Brewing — holds signing authority over the
        deployed account.
        """

