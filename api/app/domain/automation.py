"""Progressive automation — the policy gate for hands-off settlement.

Brewing keeps a human authoritative over settlement, but requiring a manual
decision on *every* objective does not scale and is not where the human's
judgment is actually needed. This module decides, deterministically, whether a
given objective has cleared a bar high enough that the workspace's standing
policy authorizes settlement without a fresh human decision.

The gate is intentionally conjunctive — every condition must hold:

  * the workspace opted in (``auto_settle_enabled``);
  * the *independent* validator recommended APPROVED (not merely
    "approved_with_conditions") at or above the workspace confidence floor;
  * every success criterion is satisfied by the recorded evidence;
  * the deliverable is grounded in at least one content-hashed source
    (proof-of-work, not asserted claims);
  * the value is within the workspace's auto-settle cap.

Anything short of all of these falls back to a human decision. Pure and
side-effect-free: it returns a decision object the caller acts on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass
class AutoSettleDecision:
    eligible: bool
    reasons: list[str] = field(default_factory=list)  # why it did/didn't qualify

    def as_dict(self) -> dict:
        return {"eligible": self.eligible, "reasons": self.reasons}


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def evaluate(
    *,
    enabled: bool,
    min_confidence: float,
    max_usdc: str | None,
    amount_usdc: str | None,
    validator_recommendation: str | None,
    validator_confidence: float | None,
    criteria_all_satisfied: bool,
    criteria_total: int,
    grounding_verified_sources: int,
) -> AutoSettleDecision:
    """Decide whether this objective may settle under the standing policy."""

    reasons: list[str] = []

    if not enabled:
        return AutoSettleDecision(False, ["automation disabled for this workspace"])

    if validator_recommendation != "approved":
        reasons.append(
            f"independent validator recommended '{validator_recommendation}', not 'approved'"
        )

    conf = validator_confidence if validator_confidence is not None else 0.0
    if conf < min_confidence:
        reasons.append(
            f"validator confidence {conf:.2f} below policy floor {min_confidence:.2f}"
        )

    if criteria_total <= 0:
        reasons.append("no success criteria were defined to gate on")
    elif not criteria_all_satisfied:
        reasons.append("not all success criteria are satisfied by the evidence")

    if grounding_verified_sources <= 0:
        reasons.append("deliverable is not grounded in any content-hashed source")

    cap = _to_decimal(max_usdc)
    amount = _to_decimal(amount_usdc)
    if cap is not None:
        if amount is None:
            reasons.append("objective value is unknown; cannot apply the auto-settle cap")
        elif amount > cap:
            reasons.append(f"value {amount} USDC exceeds the auto-settle cap {cap} USDC")

    if reasons:
        return AutoSettleDecision(False, reasons)

    return AutoSettleDecision(
        True,
        [
            "validator approved at/above the confidence floor",
            "all success criteria satisfied",
            "grounded in content-hashed proof-of-work",
            "value within the auto-settle cap",
        ],
    )
