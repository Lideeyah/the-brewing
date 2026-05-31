"""Payout-address proof-of-control.

Settlement must land in an account the payee actually owns. Before an agent's
payout wallet can be used as a release destination, the agent proves it controls
that wallet by signing a server-issued challenge with the wallet's private key.

This is *real* proof-of-control, not a server-side stand-in: on Solana an address
is the base58 encoding of the wallet's ed25519 public key, so a signature over the
challenge is verified directly against the address. Brewing never holds the key —
the wallet signs client-side (e.g. in the agent's agentic wallet / Phantom) and
submits only the signature. A wrong or unproven address can therefore never become
a settlement destination, which is what makes external payout safe.

--- Chain-specific verification boundary -----------------------------------
This module is the single place a chain assumption lives. The proof mechanism
here is Solana-shaped: an address is the base58 encoding of a 32-byte ed25519
public key, so the pubkey is recovered from the address and an ed25519 signature
is verified directly against it. Everything above this module is provider-neutral
— the model (`payout_address` + a free-text `payout_blockchain` discriminator),
the registry lifecycle, the `_resolve_payout_wallet` seam, the API contract, and
the settlement layer all deal in opaque strings and never reference ed25519,
base58, or Solana.

Deliberately NOT generalized yet: no verifier dispatch, no EVM/secp256k1 branch,
no multi-chain strategy registry. Adding a second chain (e.g. EVM, where an
address is a truncated keccak hash and control is proven via ecrecover/EIP-191)
is a localized change *inside this module* — dispatch on `payout_blockchain` —
and touches nothing above it. Introduce that dispatch when a second chain is a
real requirement, not before.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Base58 (Bitcoin/Solana) alphabet — no 0, O, I, l.
_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(_B58_ALPHABET)}

# An ed25519 public key (a Solana address) is exactly 32 bytes; a signature is 64.
_PUBKEY_LEN = 32
_SIG_LEN = 64

# How long a payout-control challenge stays valid once issued.
CHALLENGE_TTL = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def b58decode(value: str) -> bytes:
    """Decode a base58 string to raw bytes. Raises ValueError on bad input."""

    if not value:
        raise ValueError("empty base58 string")
    num = 0
    for ch in value:
        idx = _B58_INDEX.get(ch)
        if idx is None:
            raise ValueError(f"invalid base58 character: {ch!r}")
        num = num * 58 + idx
    # Reconstruct big-endian bytes.
    full = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    # Leading '1's in base58 encode leading zero bytes.
    pad = len(value) - len(value.lstrip("1"))
    return b"\x00" * pad + full


def is_valid_solana_address(address: str) -> bool:
    """True iff `address` is a syntactically valid 32-byte base58 ed25519 pubkey."""

    if not address or not isinstance(address, str):
        return False
    try:
        raw = b58decode(address.strip())
    except ValueError:
        return False
    return len(raw) == _PUBKEY_LEN


def normalize_address(address: str) -> str:
    """Trim and validate a payout address, raising ValueError if malformed."""

    addr = (address or "").strip()
    if not is_valid_solana_address(addr):
        raise ValueError(
            "Payout address must be a valid Solana wallet address "
            "(base58-encoded, 32-byte ed25519 public key)."
        )
    return addr


def new_challenge(address: str) -> str:
    """Build a unique, human-readable challenge string for an address.

    The address and a timestamp are embedded so a captured signature cannot be
    replayed for a different wallet, and a fresh nonce makes each challenge
    one-time-use. The full string is what the wallet must sign.
    """

    nonce = secrets.token_hex(16)
    issued = _now().isoformat()
    return (
        "Brewing payout-address control proof\n"
        f"address: {address}\n"
        f"issued: {issued}\n"
        f"nonce: {nonce}"
    )


def _decode_signature(signature: str) -> bytes:
    """Decode a 64-byte signature from base58 or hex; raise ValueError otherwise."""

    sig = (signature or "").strip()
    if not sig:
        raise ValueError("empty signature")
    # Try hex first (wallets often emit hex); fall back to base58.
    raw: bytes | None = None
    hex_candidate = sig[2:] if sig.lower().startswith("0x") else sig
    try:
        decoded = bytes.fromhex(hex_candidate)
        if len(decoded) == _SIG_LEN:
            raw = decoded
    except ValueError:
        raw = None
    if raw is None:
        raw = b58decode(sig)
    if len(raw) != _SIG_LEN:
        raise ValueError("signature must decode to 64 bytes")
    return raw


def verify_control(address: str, challenge: str, signature: str) -> bool:
    """Verify a wallet proved control of `address` by signing `challenge`.

    Real ed25519 verification against the address's public key. Never raises:
    any malformed input or failed verification returns False, so callers treat a
    bad proof identically to an absent one.
    """

    try:
        pubkey_bytes = b58decode(address.strip())
        if len(pubkey_bytes) != _PUBKEY_LEN:
            return False
        sig_bytes = _decode_signature(signature)
        public_key = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
        public_key.verify(sig_bytes, challenge.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError):
        return False
    except Exception:  # noqa: BLE001 — verification must never blow up settlement setup
        return False
