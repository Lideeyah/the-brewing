"""Pre-create a destination's USDC Associated Token Account (ATA).

Circle's paymaster refuses to create token accounts during a transfer
(PAYMASTER_SOL_ATA_CREATION_NOT_ALLOWED — gated, "contact support"). So before
Circle deposits USDC into a fresh wallet, we create that wallet's USDC ATA
ourselves, paid by a funded devnet keypair. Circle then only ever deposits into
an account that already exists; gas for the transfer itself stays sponsored by
Circle's paymaster.

Best-effort and fully isolated: libraries are imported lazily and every failure
is swallowed with a warning, so an unconfigured or offline ATA step never breaks
the app — the Circle transfer simply proceeds (and surfaces its own error if the
ATA truly couldn't be made).
"""

from __future__ import annotations

import logging

logger = logging.getLogger("brewing.settlement.ata")


def ensure_usdc_ata(
    owner_address: str,
    *,
    mint: str,
    rpc_url: str,
    payer_secret: str,
) -> bool:
    """Ensure ``owner_address`` has a USDC ATA, creating it if missing.

    Returns True if the ATA exists (or was created), False if it could not be
    ensured (unconfigured, libs missing, or an RPC/signing error). Never raises.
    """
    if not payer_secret:
        return False
    try:
        from solana.rpc.api import Client
        from solana.rpc.commitment import Confirmed
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        from spl.token.client import Token
        from spl.token.constants import TOKEN_PROGRAM_ID
        from spl.token.instructions import get_associated_token_address
    except Exception as exc:  # noqa: BLE001 — optional dependency
        logger.warning("solana libs unavailable; skipping ATA pre-create: %s", exc)
        return False

    try:
        client = Client(rpc_url, commitment=Confirmed)
        owner = Pubkey.from_string(owner_address)
        mint_pk = Pubkey.from_string(mint)
        ata = get_associated_token_address(owner, mint_pk)
        if client.get_account_info(ata).value is not None:
            return True  # already exists — nothing to do
        payer = Keypair.from_base58_string(payer_secret)
        token = Token(conn=client, pubkey=mint_pk, program_id=TOKEN_PROGRAM_ID, payer=payer)
        token.create_associated_token_account(owner)
        logger.info("Pre-created USDC ATA for %s", owner_address)
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("ATA pre-create failed for %s: %s", owner_address, exc)
        return False
