"""Coordination Copilot.

Turns a raw operational *intent* into a structured coordination architecture:
governance rules, SLA, settlement terms, and an execution-orchestration plan.
This is the "Intent -> Governance" edge of the objective lifecycle.

Design notes:
- Provider-agnostic output: the Copilot proposes *terms*, never chain/Circle
  specifics. Settlement amounts are plain USDC decimals as strings.
- A 3.5s pacemaker lock serializes downstream Claude calls to avoid 429s.
- Fully degradable: with no ANTHROPIC_API_KEY (or on any error) it returns a
  deterministic heuristic structure so the app loop always works offline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from app.config import get_settings

logger = logging.getLogger("brewing.copilot")

# Serializes downstream model calls across the process (rate-limit pacemaker).
_pacemaker = asyncio.Lock()

_SYSTEM = """You are the Brewing Coordination Copilot.

Brewing is governed coordination and settlement infrastructure for autonomous
systems. The unit of coordination is the OBJECTIVE, not the agent. You convert
a raw operational intent into a structured, enforceable coordination
architecture for the lifecycle: Intent -> Governance -> Escrow -> Execution ->
Validation -> Settlement.

Return ONLY a JSON object (no prose, no markdown) with exactly these keys:
{
  "title": short imperative objective title,
  "summary": one-paragraph restatement of the objective and its success condition,
  "governance_config": {
     "approval_policy": "auto" | "single_reviewer" | "multi_reviewer",
     "validation_criteria": [3-5 concrete, checkable acceptance criteria],
     "dispute_policy": short string
  },
  "sla_config": {
     "deadline_hours": integer,
     "checkpoints": [2-4 short milestone strings]
  },
  "settlement_config": {
     "recommended_escrow_usdc": decimal string (total budget to lock),
     "currency": "USDC",
     "release_condition": short string describing what triggers settlement
  },
  "orchestration_plan": {
     "steps": [ {"title": short step title, "detail": one sentence} ]  // 3-6 steps
  }
}

Frame execution as ORCHESTRATION of work toward the objective. Do not invent an
agent marketplace, registry, or scheduler. Be concrete and concise."""


def _heuristic_structure(intent: str, title: str | None) -> dict:
    """Deterministic fallback used when the model is unavailable."""
    derived_title = title or (intent.strip().split("\n")[0][:80] or "New objective")
    return {
        "title": derived_title,
        "summary": (
            f"Coordinate and settle the following operational intent: {intent.strip()}. "
            "Success is defined by satisfying the validation criteria below."
        ),
        "governance_config": {
            "approval_policy": "single_reviewer",
            "validation_criteria": [
                "Deliverable matches the stated intent",
                "Outputs are complete and self-consistent",
                "No unmet constraints from the intent remain",
            ],
            "dispute_policy": "Escalate to workspace owner on reviewer rejection.",
        },
        "sla_config": {
            "deadline_hours": 48,
            "checkpoints": ["Plan confirmed", "Work in progress", "Ready for audit"],
        },
        "settlement_config": {
            "recommended_escrow_usdc": "100",
            "currency": "USDC",
            "release_condition": "Audit approval against validation criteria.",
        },
        "orchestration_plan": {
            "steps": [
                {"title": "Decompose intent", "detail": "Break the intent into concrete work items."},
                {"title": "Execute work", "detail": "Produce the deliverables for each work item."},
                {"title": "Self-validate", "detail": "Check outputs against the validation criteria."},
                {"title": "Submit for audit", "detail": "Hand off results for governance review."},
            ]
        },
        "_source": "heuristic",
    }


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Tolerate stray code fences or leading prose.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


async def structure_intent(intent: str, title: str | None = None) -> dict:
    """Structure a raw intent into a coordination architecture."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _heuristic_structure(intent, title)

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        user_msg = f"Operational intent:\n{intent}"
        if title:
            user_msg += f"\n\nProposed title: {title}"

        async with _pacemaker:
            await asyncio.sleep(settings.orchestration_pacemaker_seconds)
            resp = await client.messages.create(
                model=settings.copilot_model,
                max_tokens=1500,
                system=_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        structured = _extract_json(text)
        structured["_source"] = settings.copilot_model
        return structured
    except Exception as exc:  # noqa: BLE001 — never let coordination hard-fail
        logger.warning("Copilot structuring fell back to heuristic: %s", exc)
        fallback = _heuristic_structure(intent, title)
        fallback["_source"] = "heuristic_fallback"
        return fallback
