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
  },
  "workflow": [
     {"role_key": one of "planner"|"research"|"analysis"|"executor"|"reviewer"|"validator",
      "title": short role title,
      "description": one sentence on what this role delivers,
      "allocation_pct": number 0-100}      // 2-5 roles; allocation_pct should sum to ~100
  ]
}

The OBJECTIVE is the outcome; the workflow is the multi-role team that fulfills
it. Decompose into the smallest set of distinct roles the outcome actually
needs (a simple task may be a single executor + reviewer). Frame execution as
ORCHESTRATION of work toward the objective. Do not invent an agent marketplace
or scheduler. Be concrete and concise."""


_EVAL_SYSTEM = """You are the Brewing Coordination Copilot acting as a governance auditor.

You review the recorded EXECUTION of an objective against its governance
validation criteria and produce a structured, defensible governance evaluation.
You are advisory only: a human reviewer retains final approval authority and may
override your recommendation.

Return ONLY a JSON object (no prose, no markdown) with exactly these keys:
{
  "recommendation": "approved" | "approved_with_conditions" | "rejected",
  "reasoning": one short paragraph justifying the recommendation, grounded in the
               criteria and the actual execution outputs,
  "findings": [
     {"criterion": the criterion text, "met": true|false, "assessment": one sentence}
  ],
  "conditions": [short remediation strings]  // required follow-ups; non-empty ONLY
                                              // when recommendation is approved_with_conditions
}

Judge strictly against the provided validation criteria and execution outputs.
Be specific, conservative, and concise. If an output is missing or insufficient
to verify a criterion, mark it not met and say why. Use "approved_with_conditions"
when the objective is substantially met but non-blocking follow-ups remain."""

_VALID_RECOMMENDATIONS = {"approved", "approved_with_conditions", "rejected"}


def _heuristic_evaluation(
    criteria: list[str], steps: list[dict], evidence_summary: dict | None = None
) -> dict:
    """Deterministic governance evaluation used when the model is unavailable.

    When the SLA oracle has supplied an evidence summary, judge on evidence
    quality (so browser-agent / free-text outputs are handled), not just on
    step status. Otherwise fall back to "all steps completed".
    """
    completed = all(s.get("status") == "completed" for s in steps) if steps else False

    if evidence_summary is not None:
        any_errors = bool(evidence_summary.get("any_errors"))
        all_strong = bool(evidence_summary.get("all_strong"))
        met = completed and all_strong and not any_errors
        if met:
            assessment = "Normalized evidence is strong and error-free for this criterion."
            reasoning = (
                "The SLA oracle normalized all execution outputs (including any "
                "unstructured browser-agent transcripts) to strong, error-free "
                "evidence covering the validation criteria."
            )
            rec = "approved"
        elif completed and not any_errors:
            assessment = "Evidence is present but not uniformly strong for this criterion."
            reasoning = (
                "Execution completed and the oracle found no error markers, but "
                "evidence quality is uneven; non-blocking verification follow-ups remain."
            )
            rec = "approved_with_conditions"
        else:
            assessment = (
                "Oracle detected execution errors or missing evidence for this criterion."
                if any_errors
                else "Execution did not complete; criterion cannot be verified."
            )
            reasoning = (
                "The SLA oracle surfaced error markers or insufficient evidence in "
                "the normalized outputs, so the validation criteria cannot be confirmed."
            )
            rec = "rejected"
        conditions = (
            ["Re-verify uneven-quality evidence before settlement."]
            if rec == "approved_with_conditions"
            else []
        )
        findings = [
            {"criterion": c, "met": rec != "rejected", "assessment": assessment}
            for c in (criteria or ["Deliverable matches the stated intent"])
        ]
        return {
            "recommendation": rec,
            "reasoning": reasoning,
            "findings": findings,
            "conditions": conditions,
            "_source": "heuristic",
        }

    findings = [
        {
            "criterion": c,
            "met": completed,
            "assessment": (
                "Recorded execution outputs cover this criterion."
                if completed
                else "Execution did not complete; criterion cannot be verified."
            ),
        }
        for c in (criteria or ["Deliverable matches the stated intent"])
    ]
    return {
        "recommendation": "approved" if completed else "rejected",
        "reasoning": (
            "All orchestration steps completed and produced recorded outputs; "
            "no criteria violations were detected by automated review."
            if completed
            else "Execution did not complete successfully, so the validation "
            "criteria cannot be confirmed."
        ),
        "findings": findings,
        "conditions": [],
        "_source": "heuristic",
    }


def _normalize_evaluation(data: dict) -> dict:
    rec = str(data.get("recommendation", "")).strip().lower().replace(" ", "_")
    if rec not in _VALID_RECOMMENDATIONS:
        rec = "approved_with_conditions"
    data["recommendation"] = rec
    if not isinstance(data.get("findings"), list):
        data["findings"] = []
    conditions = data.get("conditions")
    data["conditions"] = (
        [str(c) for c in conditions] if isinstance(conditions, list) else []
    )
    if rec != "approved_with_conditions":
        data["conditions"] = []
    data["reasoning"] = str(data.get("reasoning", "")).strip()
    return data


async def evaluate_governance(
    *,
    intent: str,
    summary: str | None,
    criteria: list[str],
    steps: list[dict],
    evidence_block: str | None = None,
    evidence_summary: dict | None = None,
) -> dict:
    """Evaluate recorded execution against governance criteria.

    When the SLA oracle has normalized the execution outputs, ``evidence_block``
    carries the auditor-readable rendering (handles unstructured browser-agent
    transcripts and free text, not just clean API JSON) and ``evidence_summary``
    feeds the deterministic fallback. Returns {recommendation, reasoning,
    findings, conditions, _source}. Always degrades to a deterministic heuristic
    so the audit stage never hard-fails.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _heuristic_evaluation(criteria, steps, evidence_summary)

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        criteria_block = "\n".join(f"- {c}" for c in criteria) or "- (none specified)"
        outputs_block = evidence_block or (
            "\n".join(
                f"{i + 1}. [{s.get('status', 'unknown')}] {s.get('title', 'step')}: "
                f"{s.get('output') or '(no output recorded)'}"
                for i, s in enumerate(steps)
            )
            or "(no execution steps recorded)"
        )
        oracle_note = (
            "\n\nNote: execution outputs below were normalized by the SLA oracle. "
            "Each line is tagged with [status · output_kind · evidence:quality]. "
            "Outputs may be unstructured (browser-agent transcripts, free text), "
            "not clean API responses — judge the substance, not the format."
            if evidence_block
            else ""
        )
        user_msg = (
            f"Operational intent:\n{intent}\n\n"
            f"Objective summary:\n{summary or '(none)'}\n\n"
            f"Governance validation criteria:\n{criteria_block}\n\n"
            f"Recorded execution outputs:\n{outputs_block}{oracle_note}"
        )

        async with _pacemaker:
            await asyncio.sleep(settings.orchestration_pacemaker_seconds)
            resp = await client.messages.create(
                model=settings.copilot_model,
                max_tokens=1500,
                system=_EVAL_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        evaluation = _normalize_evaluation(_extract_json(text))
        evaluation["_source"] = settings.copilot_model
        return evaluation
    except Exception as exc:  # noqa: BLE001 — never let governance hard-fail
        logger.warning("Copilot governance evaluation fell back to heuristic: %s", exc)
        fallback = _heuristic_evaluation(criteria, steps, evidence_summary)
        fallback["_source"] = "heuristic_fallback"
        return fallback


def _heuristic_structure(intent: str, title: str | None) -> dict:
    """Deterministic fallback used when the model is unavailable."""
    from decimal import Decimal

    from app.domain import workflow as workflow_domain

    derived_title = title or (intent.strip().split("\n")[0][:80] or "New objective")
    default_workflow = [
        {
            "role_key": r["role_key"],
            "title": r["title"],
            "description": r["description"],
            # Express as a percent of the default 100 USDC budget.
            "allocation_pct": round(float(Decimal(r["allocation_usdc"])), 2),
        }
        for r in workflow_domain.generate_workflow(intent, Decimal("100"))
    ]
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
        "workflow": default_workflow,
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
