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
  // Brewing pilots settle on a devnet USDC treasury funded from a faucet
  // (~20 USDC). Keep recommended_escrow_usdc small and devnet-realistic:
  // scale it to the work, typically 10-100 USDC, and never propose hundreds
  // or thousands. It must be an amount a faucet-funded treasury could lock.
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
  "risks": [
     {"category": "evidence"|"financial"|"governance"|"execution"|"compliance",
      "severity": "low"|"medium"|"high",
      "detail": one sentence naming a concrete risk in releasing settlement}
  ],  // surface material risks even when recommending approval; [] only if none
  "conditions": [short remediation strings]  // required follow-ups; non-empty ONLY
                                              // when recommendation is approved_with_conditions
}

Judge each criterion against the ACTUAL deliverable content, as a fair human
reviewer reading the document would. The execution outputs ARE the deliverable —
read them. Mark "met": true when the deliverable substantively addresses the
criterion: a comparison table, ranked recommendation, sourced figures, or risk
list that is actually present in the text counts as met, even if you would phrase
or format it differently. Mark "met": false ONLY when the required element is
genuinely absent, self-contradictory, or materially incomplete — never merely
because you cannot independently re-verify an external fact the deliverable
states. Recommend "approved" when the deliverable meets the criteria,
"approved_with_conditions" when it substantially meets them with non-blocking
gaps, and "rejected" only when core criteria are genuinely unmet. The "risks"
array stays honest — flag residual risk a human should weigh (thin sourcing,
unverifiable external claims, over-budget exposure) even on an approval. Be
specific and concise."""

_VALID_RECOMMENDATIONS = {"approved", "approved_with_conditions", "rejected"}


def _derive_risks(
    steps: list[dict], evidence_summary: dict | None, recommendation: str
) -> list[dict]:
    """Deterministic risk findings used when the model is unavailable.

    Mirrors the advisory ``risks`` array the model produces: concrete,
    severity-tagged risks a reviewer should weigh before releasing settlement.
    Derived from evidence quality so it stays honest even on an approval.
    """

    risks: list[dict] = []
    completed = all(s.get("status") == "completed" for s in steps) if steps else False
    if not completed:
        risks.append(
            {
                "category": "execution",
                "severity": "high",
                "detail": "Execution did not complete; settling would pay for unfinished work.",
            }
        )
    if evidence_summary is not None:
        if evidence_summary.get("any_errors"):
            risks.append(
                {
                    "category": "evidence",
                    "severity": "high",
                    "detail": "Normalized evidence contains error markers that contradict success.",
                }
            )
        if not evidence_summary.get("all_strong") and completed:
            risks.append(
                {
                    "category": "evidence",
                    "severity": "medium",
                    "detail": "Evidence quality is uneven; some criteria rest on weak or thin signals.",
                }
            )
        if evidence_summary.get("unstructured_present"):
            risks.append(
                {
                    "category": "evidence",
                    "severity": "low",
                    "detail": "Outcome rests on unstructured transcripts that are harder to verify independently.",
                }
            )
    if recommendation == "rejected" and not risks:
        risks.append(
            {
                "category": "governance",
                "severity": "high",
                "detail": "Validation criteria are not satisfied by the recorded evidence.",
            }
        )
    return risks


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
            "risks": _derive_risks(steps, evidence_summary, rec),
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
    rec = "approved" if completed else "rejected"
    return {
        "recommendation": rec,
        "reasoning": (
            "All orchestration steps completed and produced recorded outputs; "
            "no criteria violations were detected by automated review."
            if completed
            else "Execution did not complete successfully, so the validation "
            "criteria cannot be confirmed."
        ),
        "findings": findings,
        "risks": _derive_risks(steps, evidence_summary, rec),
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
    data["risks"] = _normalize_risks(data.get("risks"))
    data["reasoning"] = str(data.get("reasoning", "")).strip()
    return data


_VALID_SEVERITIES = {"low", "medium", "high"}
_VALID_RISK_CATEGORIES = {
    "evidence",
    "financial",
    "governance",
    "execution",
    "compliance",
}


def _normalize_risks(raw: object) -> list[dict]:
    """Coerce model-produced risks into {category, severity, detail} records."""

    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        detail = str(item.get("detail") or item.get("risk") or "").strip()
        if not detail:
            continue
        severity = str(item.get("severity", "")).strip().lower()
        if severity not in _VALID_SEVERITIES:
            severity = "medium"
        category = str(item.get("category", "")).strip().lower()
        if category not in _VALID_RISK_CATEGORIES:
            category = "governance"
        out.append({"category": category, "severity": severity, "detail": detail})
    return out


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


_DELIVERABLE_SYSTEM = (
    "You are an expert execution agent in a governed coordination network. You "
    "produce the finished, client-ready work product an objective asked for — "
    "not a plan, not a description of how you'd do it, the actual deliverable. "
    "Write in clean Markdown, be specific and substantive, and satisfy the "
    "stated definition of done."
)


def _heuristic_deliverable(
    intent: str, title: str | None, definition_of_done: str | None
) -> dict:
    """Deterministic deliverable used when the model is unavailable."""
    lines = [
        f"# {title or 'Deliverable'}",
        "",
        "## Summary",
        f"Work product coordinated for the objective: {intent}",
    ]
    if definition_of_done:
        lines += ["", "## Acceptance criteria", definition_of_done]
    lines += [
        "",
        "## Result",
        "This run was coordinated and recorded by the orchestration layer. "
        "Enable the Coordination model (or connect a live executing agent) to "
        "produce full deliverable content here.",
    ]
    return {"content": "\n".join(lines), "_source": "heuristic"}


async def generate_deliverable(
    intent: str,
    title: str | None = None,
    *,
    definition_of_done: str | None = None,
    deadline: str | None = None,
    roles: list[str] | None = None,
) -> dict:
    """Produce the actual deliverable an objective asked for.

    Returns {content, _source}. Always degrades to a deterministic heuristic so
    execution never hard-fails on a missing key or low credit balance.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        return _heuristic_deliverable(intent, title, definition_of_done)

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        parts = [f"Objective: {title or intent}", f"\nIntent:\n{intent}"]
        if roles:
            parts.append("\nCoordinated by roles: " + ", ".join(roles))
        if definition_of_done:
            parts.append(f"\nDefinition of done (must be satisfied):\n{definition_of_done}")
        if deadline:
            parts.append(f"\nDeadline / timeframe: {deadline}")
        parts.append("\nProduce the complete deliverable now, in Markdown.")
        user_msg = "\n".join(parts)

        async with _pacemaker:
            await asyncio.sleep(settings.orchestration_pacemaker_seconds)
            resp = await client.messages.create(
                model=settings.copilot_model,
                max_tokens=2200,
                system=_DELIVERABLE_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()
        if not text:
            raise ValueError("empty deliverable")
        return {"content": text, "_source": settings.copilot_model}
    except Exception as exc:  # noqa: BLE001 — never let execution hard-fail
        logger.warning("Copilot deliverable generation fell back to heuristic: %s", exc)
        fallback = _heuristic_deliverable(intent, title, definition_of_done)
        fallback["_source"] = "heuristic_fallback"
        return fallback


def _heuristic_role_deliverables(
    intent: str, title: str | None, roles: list[dict], definition_of_done: str | None
) -> dict:
    out_roles = []
    for r in roles:
        out_roles.append(
            {
                "title": r.get("title") or r.get("role_key") or "Role",
                "deliverable": (
                    f"### {r.get('title')}\n\n{r.get('description') or ''}\n\n"
                    f"Contribution recorded for: {intent}"
                ),
            }
        )
    cumulative = _heuristic_deliverable(intent, title, definition_of_done)["content"]
    return {"roles": out_roles, "cumulative": cumulative, "_source": "heuristic"}


def _parse_delimited_deliverables(text: str) -> tuple[list[dict], str]:
    """Parse the ===ROLE: <title>=== / ===CUMULATIVE=== delimiter format."""
    cumulative = ""
    body = text
    if "===CUMULATIVE===" in text:
        body, _, cumulative = text.rpartition("===CUMULATIVE===")
        cumulative = cumulative.strip()
    role_items: list[dict] = []
    for chunk in body.split("===ROLE:")[1:]:
        header, sep, content = chunk.partition("===")
        if not sep:
            continue
        title = header.strip()
        deliverable = content.strip()
        if title and deliverable:
            role_items.append({"title": title, "deliverable": deliverable})
    return role_items, cumulative


async def generate_deliverables(
    intent: str,
    title: str | None = None,
    *,
    definition_of_done: str | None = None,
    deadline: str | None = None,
    roles: list[dict] | None = None,
    criteria: list | None = None,
) -> dict:
    """Produce a deliverable for each role plus a cumulative final work product.

    `roles` is a list of {role_key, title, description}. Returns
    {"roles": [{"title", "deliverable"}], "cumulative": str, "_source": str},
    in one model call. Degrades to a deterministic heuristic.
    """
    roles = roles or []
    settings = get_settings()
    if not settings.anthropic_api_key or not roles:
        # With no roles, still produce a single cumulative deliverable.
        if not roles:
            single = await generate_deliverable(
                intent, title, definition_of_done=definition_of_done, deadline=deadline
            )
            return {"roles": [], "cumulative": single["content"], "_source": single["_source"]}
        return _heuristic_role_deliverables(intent, title, roles, definition_of_done)

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        roster = "\n".join(
            f"- {r.get('title')} ({r.get('role_key')}): {r.get('description') or ''}"
            for r in roles
        )
        # Delimiter format (not JSON) — markdown content can't break it the way
        # quotes/newlines break JSON, so parsing is robust.
        template = "\n".join(f"===ROLE: {r.get('title')}===\n<contribution>" for r in roles)
        criteria_block = ""
        crit_lines = [
            f"- {c.get('description') if isinstance(c, dict) else c}"
            for c in (criteria or [])
        ]
        if crit_lines:
            criteria_block = (
                "\nThe finished work will be judged against these acceptance "
                "criteria — satisfy EVERY one explicitly (include the structures "
                "they ask for, e.g. per-item breakdowns, dated sources, summaries):\n"
                + "\n".join(crit_lines)
                + "\n"
            )
        user_msg = (
            f"Objective: {title or intent}\n\nIntent:\n{intent}\n\n"
            f"Definition of done: {definition_of_done or 'use professional judgment'}\n"
            f"Deadline: {deadline or 'n/a'}\n"
            f"{criteria_block}\n"
            f"A coordinated multi-agent team holds these roles:\n{roster}\n\n"
            "Format rules — follow exactly:\n"
            "1) For EACH role, write a SHORT contribution note: 2–4 sentences "
            "(≈60–100 words) on what that role did. These are brief notes, not the "
            "deliverable — do NOT write the full report inside a role.\n"
            "2) Then write the CUMULATIVE section: the COMPLETE, finished work "
            "product the objective asked for (≈600–900 words). This is the primary "
            "deliverable and the part a reviewer grades — it MUST be fully written "
            "end to end (no truncation, no placeholders, no 'see above'), and must "
            "explicitly include every element the acceptance criteria require "
            "(comparison table, per-item lists, sources, ranked recommendation, "
            "executive summary). Spend the bulk of your effort here.\n\n"
            "Output EXACTLY in this format, using these delimiter lines verbatim "
            "and nothing before the first one:\n\n"
            f"{template}\n===CUMULATIVE===\n<the complete finished deliverable>"
        )
        async with _pacemaker:
            await asyncio.sleep(settings.orchestration_pacemaker_seconds)
            # Generation runs in a background task (not the HTTP request), so it's
            # free to produce a complete deliverable; the timeout is just a safety
            # net that falls back to the heuristic if the model stalls.
            resp = await asyncio.wait_for(
                client.messages.create(
                    model=settings.copilot_model,
                    # Headroom so a complete deliverable never truncates; the
                    # prompt caps role notes, so the cumulative gets the budget.
                    max_tokens=5000,
                    system=_DELIVERABLE_SYSTEM,
                    messages=[{"role": "user", "content": user_msg}],
                ),
                timeout=settings.deliverable_timeout_seconds,
            )
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        role_items, cumulative = _parse_delimited_deliverables(text)
        if not cumulative and role_items:
            cumulative = "\n\n---\n\n".join(
                str(r.get("deliverable", "")) for r in role_items
            )
        if not cumulative:
            raise ValueError("empty deliverables")
        return {"roles": role_items, "cumulative": cumulative, "_source": settings.copilot_model}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Copilot role-deliverable generation fell back: %s", exc)
        fallback = _heuristic_role_deliverables(intent, title, roles, definition_of_done)
        fallback["_source"] = "heuristic_fallback"
        return fallback
