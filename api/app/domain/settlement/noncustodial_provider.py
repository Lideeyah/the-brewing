"""Non-custodial settlement — the target trust model.

In the custodial Circle rail, Brewing (via Circle) holds the keys to escrow
funds. The non-custodial model inverts that: escrow is a tenant-scoped account
whose signing authority is the tenant's *own* agentic wallet. Brewing
references and observes the account but **cannot move the funds** — release and
slash are authorized by the controller wallet, never by Brewing.

This provider implements that boundary honestly:

  * Read-only methods that need no keys — balance and on-chain transaction
    proof — are real Solana JSON-RPC calls.
  * Value-moving methods (deploy escrow, lock, release, slash) deliberately do
    **not** sign on the server. They raise ``SettlementConfigError`` describing
    what the controller wallet must authorize, because performing them
    server-side would re-introduce custody — exactly what this model removes.

The seam is therefore selectable and exercisable today (``SETTLEMENT_PROVIDER=
noncustodial``) without faking custody. Wiring the controller-wallet
authorization flow (client-side signing or a delegated session key) is the
remaining work, and it requires the tenant's own wallet — see
``docs/non-custodial-architecture-review.md``.
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from app.config import get_settings
from app.domain.settlement.provider import (
    EscrowRef,
    NonCustodialSettlementProvider,
    SettlementConfigError,
    TenantEscrowAccount,
    TransferResult,
    TxProof,
    WalletRef,
)

_USDC_DECIMALS = 6
_RPC_TIMEOUT = 8.0

# What the controller wallet — not Brewing — must authorize. Shared message so
# every custody-moving method reads identically at the seam boundary.
_CUSTODY_BOUNDARY = (
    "Non-custodial settlement does not sign on the server: {action} must be "
    "authorized by the tenant's controller wallet, which holds the keys to the "
    "escrow account. Brewing never custodies these funds. Wire the controller "
    "authorization flow (client-side signing / delegated session key) to enable "
    "this — see docs/non-custodial-architecture-review.md."
)


class NonCustodialSolanaProvider(NonCustodialSettlementProvider):
    """Tenant-key-controlled escrow on Solana. Brewing never holds the keys."""

    name = "noncustodial-solana"

    def __init__(self) -> None:
        self._settings = get_settings()

    # --- Read paths: real, key-free chain reads ----------------------------

    def get_balance(self, wallet: WalletRef) -> Decimal:
        """Live USDC balance of an address, read straight from the chain."""
        mint = self._settings.usdc_mint
        if not mint:
            raise SettlementConfigError(
                "usdc_mint is not configured; cannot read on-chain USDC balance."
            )
        if not wallet.address:
            raise SettlementConfigError("Wallet address is required to read balance.")
        result = self._rpc(
            "getTokenAccountsByOwner",
            [
                wallet.address,
                {"mint": mint},
                {"encoding": "jsonParsed"},
            ],
        )
        total = Decimal("0")
        for acc in (result.get("value") or []):
            info = (
                acc.get("account", {})
                .get("data", {})
                .get("parsed", {})
                .get("info", {})
            )
            amt = info.get("tokenAmount", {}).get("uiAmountString")
            if amt is not None:
                total += Decimal(str(amt))
        return total

    def get_transaction_proof(self, tx_ref: str) -> TxProof:
        """Resolve a signature to its confirmation state + explorer URL."""
        if not tx_ref:
            raise SettlementConfigError("A transaction signature is required.")
        statuses = self._rpc(
            "getSignatureStatuses", [[tx_ref], {"searchTransactionHistory": True}]
        )
        value = (statuses.get("value") or [None])[0]
        state = "unknown"
        if value is not None:
            if value.get("err"):
                state = "failed"
            else:
                state = value.get("confirmationStatus") or "submitted"
        return TxProof(
            tx_ref=tx_ref,
            state=state,
            tx_hash=tx_ref,
            explorer_url=self._explorer_url(tx_ref),
        )

    # --- Custody boundary: never signed server-side ------------------------

    def provision_treasury_wallet(self, workspace_id: str) -> WalletRef:
        raise SettlementConfigError(
            "In the non-custodial model the tenant brings their own agentic "
            "wallet as the controller; Brewing does not provision custodial "
            "wallets. Register the controller wallet for the workspace instead."
        )

    def deploy_tenant_escrow(
        self, controller_wallet: WalletRef, amount: Decimal, objective_id: str
    ) -> TenantEscrowAccount:
        raise SettlementConfigError(
            _CUSTODY_BOUNDARY.format(action="deploying the tenant escrow account")
        )

    def lock_escrow(
        self, treasury: WalletRef, amount: Decimal, objective_id: str
    ) -> EscrowRef:
        raise SettlementConfigError(
            _CUSTODY_BOUNDARY.format(action="locking funds into escrow")
        )

    def release_escrow(self, escrow: EscrowRef, payee: WalletRef) -> TransferResult:
        raise SettlementConfigError(
            _CUSTODY_BOUNDARY.format(action="releasing escrow to the payee")
        )

    def slash_escrow(self, escrow: EscrowRef, treasury: WalletRef) -> TransferResult:
        raise SettlementConfigError(
            _CUSTODY_BOUNDARY.format(action="slashing escrow")
        )

    # --- internals ---------------------------------------------------------

    def _rpc(self, method: str, params: list) -> dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            with httpx.Client(timeout=_RPC_TIMEOUT) as client:
                resp = client.post(self._settings.solana_rpc_url, json=payload)
                resp.raise_for_status()
                body = resp.json()
        except Exception as exc:  # noqa: BLE001 — surface as a settlement config error
            raise SettlementConfigError(
                f"Solana RPC call {method} failed: {str(exc)[:160]}"
            ) from exc
        if "error" in body:
            raise SettlementConfigError(f"Solana RPC error: {body['error']}")
        return body.get("result", {}) or {}

    def _explorer_url(self, signature: str) -> str:
        cluster = "" if self._settings.circle_blockchain == "SOL" else "?cluster=devnet"
        return f"https://explorer.solana.com/tx/{signature}{cluster}"
