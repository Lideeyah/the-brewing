"""Circle Developer-Controlled Wallets implementation of SettlementProvider.

USDC settlement on Solana devnet. Escrow is wallet-based for the MVP: each
objective gets its own programmable escrow wallet, so lock/release/slash are
real, on-chain, explorer-visible transfers. A custom on-chain escrow program
is a later upgrade and does not change this interface.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.config import get_settings
from app.domain.settlement.provider import (
    EscrowRef,
    SettlementProvider,
    TransferResult,
    WalletRef,
)

# USDC mint on Solana devnet (Circle's testnet USDC).
USDC_SOL_DEVNET_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"


class SettlementConfigError(RuntimeError):
    """Raised when Circle credentials are not configured."""


def _explorer_url(signature: str | None) -> str | None:
    if not signature:
        return None
    return f"https://explorer.solana.com/tx/{signature}?cluster=devnet"


class CircleSettlementProvider(SettlementProvider):
    name = "circle"

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        self._dcw = None

    # --- SDK plumbing -------------------------------------------------------

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

    def _create_wallet(self, ref_id: str, name: str) -> WalletRef:
        """Create a single Solana-devnet wallet in the configured wallet set."""
        client = self._client_or_raise()
        dcw = self._dcw
        api = dcw.WalletsApi(client)
        resp = api.create_wallet(
            dcw.CreateWalletRequest(
                idempotency_key=str(uuid.uuid4()),
                account_type="EOA",
                blockchains=[self.settings.circle_blockchain],
                count=1,
                wallet_set_id=self.settings.circle_wallet_set_id,
                metadata=[dcw.WalletMetadata(name=name, ref_id=ref_id)],
            )
        )
        wallet = resp.data.wallets[0]
        return WalletRef(
            provider_wallet_id=wallet.id,
            address=wallet.address,
            blockchain=getattr(wallet.blockchain, "value", str(wallet.blockchain)),
        )

    def _transfer(
        self, source: WalletRef, destination_address: str, amount: Decimal, ref_id: str
    ) -> TransferResult:
        """Move USDC from a source wallet to a destination address."""
        client = self._client_or_raise()
        dcw = self._dcw
        api = dcw.TransactionsApi(client)
        resp = api.create_developer_transaction_transfer(
            dcw.CreateTransferTransactionForDeveloperRequest(
                idempotency_key=str(uuid.uuid4()),
                wallet_id=source.provider_wallet_id,
                destination_address=destination_address,
                amounts=[str(amount)],
                token_address=USDC_SOL_DEVNET_MINT,
                blockchain=self.settings.circle_blockchain,
                fee_level="MEDIUM",
                ref_id=ref_id,
            )
        )
        # Circle returns its internal transaction id immediately; the on-chain
        # signature appears once the transaction confirms (poll get_transaction).
        tx_id = resp.data.id
        tx_hash = getattr(resp.data, "tx_hash", None)
        return TransferResult(
            tx_ref=tx_id,
            amount=amount,
            explorer_url=_explorer_url(tx_hash),
        )

    # --- SettlementProvider contract ----------------------------------------

    def provision_treasury_wallet(self, workspace_id: str) -> WalletRef:
        return self._create_wallet(
            ref_id=f"treasury:{workspace_id}", name="brewing-treasury"
        )

    def get_balance(self, wallet: WalletRef) -> Decimal:
        client = self._client_or_raise()
        dcw = self._dcw
        api = dcw.WalletsApi(client)
        resp = api.list_wallet_balance(wallet.provider_wallet_id)
        total = Decimal("0")
        for tb in resp.data.token_balances or []:
            token = getattr(tb, "token", None)
            symbol = getattr(token, "symbol", "") or ""
            if symbol.upper().startswith("USDC"):
                total += Decimal(str(tb.amount))
        return total

    def lock_escrow(
        self, treasury: WalletRef, amount: Decimal, objective_id: str
    ) -> EscrowRef:
        # Each objective gets a dedicated programmable escrow wallet; locking is
        # a real treasury -> escrow USDC transfer.
        escrow_wallet = self._create_wallet(
            ref_id=f"escrow:{objective_id}", name="brewing-escrow"
        )
        transfer = self._transfer(
            source=treasury,
            destination_address=escrow_wallet.address,
            amount=amount,
            ref_id=f"lock:{objective_id}",
        )
        return EscrowRef(
            provider_escrow_id=escrow_wallet.provider_wallet_id,
            address=escrow_wallet.address,
            amount=amount,
            lock_tx_ref=transfer.tx_ref,
        )

    def release_escrow(self, escrow: EscrowRef, payee: WalletRef) -> TransferResult:
        return self._transfer(
            source=WalletRef(
                provider_wallet_id=escrow.provider_escrow_id,
                address=escrow.address,
                blockchain=self.settings.circle_blockchain,
            ),
            destination_address=payee.address,
            amount=escrow.amount,
            ref_id=f"release:{escrow.provider_escrow_id}",
        )

    def slash_escrow(self, escrow: EscrowRef, treasury: WalletRef) -> TransferResult:
        return self._transfer(
            source=WalletRef(
                provider_wallet_id=escrow.provider_escrow_id,
                address=escrow.address,
                blockchain=self.settings.circle_blockchain,
            ),
            destination_address=treasury.address,
            amount=escrow.amount,
            ref_id=f"slash:{escrow.provider_escrow_id}",
        )
