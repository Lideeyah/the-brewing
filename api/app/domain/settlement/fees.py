"""Hybrid settlement fee model.

Brewing's take-rate is intentionally *not* a flat percentage. It is a hybrid:

  1. A SaaS subscription tier that gates governance-dashboard access. This is
     recurring platform revenue, priced out-of-band and modeled here as a tier
     attached to the workspace.
  2. Tiered per-settlement *volume* fees that start at 0.50% and scale **down**
     as settlement size grows, with a fixed ``$0.001`` micro-fee floor so that
     high-frequency micropayments pay a flat, predictable fraction of a cent
     rather than a percentage that would round to dust (or punish small,
     frequent settlements).

This module is the single source of truth for settlement fees. Nothing else in
the codebase should hardcode a rate — import :func:`quote_settlement_fee`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

# USDC has 6 decimal places on-chain.
_USDC_QUANT = Decimal("0.000001")

# Fixed micro-fee floor (USDC) for high-frequency micropayments. This is the
# bottom of the fee scale: the percentage tiers scale *down* toward it.
MICRO_FEE_USDC = Decimal("0.001")

# At or below this settlement size we charge the flat micro-fee instead of a
# percentage — a percentage of a micropayment rounds to dust.
MICRO_PAYMENT_CEILING_USDC = Decimal("1")

# Tiered volume rates: (inclusive lower bound in USDC, fractional rate),
# evaluated highest-bound first. Starts at 0.50% and scales down with size.
_VOLUME_TIERS: list[tuple[Decimal, Decimal]] = [
    (Decimal("1000000"), Decimal("0.0010")),  # >= $1M   -> 0.10%
    (Decimal("100000"), Decimal("0.0020")),   # >= $100k -> 0.20%
    (Decimal("10000"), Decimal("0.0035")),    # >= $10k  -> 0.35%
    (Decimal("0"), Decimal("0.0050")),        # base     -> 0.50%
]


class SubscriptionTier(str, Enum):
    """SaaS plans that gate governance-dashboard access.

    Volume fees apply on top of the subscription; higher tiers exist to unlock
    dashboard surfaces and (in a fuller build) better volume rates, not to
    change the per-settlement math modeled here.
    """

    FREE = "free"
    STARTER = "starter"
    GROWTH = "growth"
    SCALE = "scale"


@dataclass(frozen=True)
class FeeQuote:
    """The resolved fee for a single settlement."""

    fee_usdc: Decimal
    rate: Decimal | None  # fractional rate applied, or None for the flat micro-fee
    basis: str  # human-readable label, e.g. "0.5% volume tier" / "$0.001 micro-fee"
    kind: str  # "percentage" | "micro" | "none"


def _rate_for(amount: Decimal) -> Decimal:
    for threshold, rate in _VOLUME_TIERS:
        if amount >= threshold:
            return rate
    return _VOLUME_TIERS[-1][1]


def quote_settlement_fee(amount: Decimal) -> FeeQuote:
    """Resolve the hybrid volume fee for a settlement of ``amount`` USDC."""

    if amount <= 0:
        return FeeQuote(Decimal("0"), Decimal("0"), "no settlement", "none")

    # High-frequency micropayments: flat, predictable micro-fee.
    if amount <= MICRO_PAYMENT_CEILING_USDC:
        return FeeQuote(
            MICRO_FEE_USDC.quantize(_USDC_QUANT),
            None,
            "$0.001 micro-fee",
            "micro",
        )

    rate = _rate_for(amount)
    fee = (amount * rate).quantize(_USDC_QUANT)
    # Never let the percentage fall below the micro-fee floor.
    if fee < MICRO_FEE_USDC:
        return FeeQuote(
            MICRO_FEE_USDC.quantize(_USDC_QUANT),
            None,
            "$0.001 micro-fee",
            "micro",
        )

    pct = (rate * Decimal("100")).normalize()
    return FeeQuote(fee, rate, f"{pct}% volume tier", "percentage")


def compute_settlement_fee(amount: Decimal) -> Decimal:
    """Convenience wrapper returning only the fee amount."""

    return quote_settlement_fee(amount).fee_usdc
