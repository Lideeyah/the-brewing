"""Independent validation layer.

The defining invariant of Brewing as a coordination network: **execution must
never equal validation**. Whoever executed an objective is structurally barred
from validating it. This module owns a registry of independent validators and
the deterministic engine that turns collected execution *evidence* into a
governance recommendation it is accountable for.

Flow:

    Execution Output -> Evidence Collection (oracle) -> Validation Engine (here)
    -> Governance Recommendation -> (human decision) -> Settlement

Each validation is tamper-evident: it binds a SHA-256 hash of the exact
evidence reasoned over, so the recommendation can be re-checked against the
evidence after the fact. Validator accuracy (upheld vs. overturned by the
authoritative human decision) accrues separately from agent execution
reputation — trust in *who validates* is its own dimension.

Pure and dependency-free; never raises into the settlement path.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import SettlementAuthorization, Validator, ValidationRecord

from . import criteria

logger = logging.getLogger("brewing.validation")

# Recommendation vocabulary, shared with the Copilot evaluation.
APPROVED = "approved"
APPROVED_WITH_CONDITIONS = "approved_with_conditions"
REJECTED = "rejected"


# Network-level independent validators. Seeded per workspace on first use so a
# tenant always has a validating counterparty distinct from its executors. The
# active validator for a given objective is chosen by the dominant evidence
# kind, mirroring how a real network routes work to a specialist verifier.
SYSTEM_VALIDATORS: list[dict] = [
    {
        "validator_key": "evidence-integrity",
        "name": "Evidence Integrity Validator",
        "kind": "evidence_engine",
        "description": (
            "General-purpose verifier. Checks that recorded evidence is "
            "complete, internally consistent, and free of contradiction before "
            "recommending settlement."
        ),
    },
    {
        "validator_key": "sla-compliance",
        "name": "SLA Compliance Validator",
        "kind": "policy_engine",
        "description": (
            "Specialist for browser-operating and unstructured execution. "
            "Confirms navigation transcripts reach the objective's success "
            "condition without error or abandonment."
        ),
    },
    {
        "validator_key": "output-consistency",
        "name": "Output Consistency Validator",
        "kind": "evidence_engine",
        "description": (
            "Specialist for structured/API execution. Verifies returned "
            "payloads carry success state and the fields the objective required."
        ),
    },
]

_KEY_BY_DOMINANT_KIND = {
    "web_navigation": "sla-compliance",
    "structured_api": "output-consistency",
    "free_text": "evidence-integrity",
    "empty": "evidence-integrity",
}


# --- Registry ---------------------------------------------------------------


def ensure_validators(session: Session, workspace_id: str) -> list[Validator]:
    """Idempotently seed the system validators for a workspace; return them."""

    existing = session.exec(
        select(Validator).where(Validator.workspace_id == workspace_id)
    ).all()
    by_key = {v.validator_key: v for v in existing}
    created = False
    for spec in SYSTEM_VALIDATORS:
        if spec["validator_key"] not in by_key:
            v = Validator(
                workspace_id=workspace_id,
                validator_key=spec["validator_key"],
                name=spec["name"],
                kind=spec["kind"],
                description=spec["description"],
                independent=True,
                active=True,
            )
            session.add(v)
            by_key[spec["validator_key"]] = v
            created = True
    if created:
        session.flush()
    return [by_key[s["validator_key"]] for s in SYSTEM_VALIDATORS]


def list_validators(session: Session, workspace_id: str) -> list[Validator]:
    ensure_validators(session, workspace_id)
    return session.exec(
        select(Validator)
        .where(Validator.workspace_id == workspace_id)
        .order_by(Validator.created_at.asc())
    ).all()


# --- Evidence binding -------------------------------------------------------


def evidence_hash(evidence_dicts: list[dict]) -> str:
    """Stable SHA-256 over the exact evidence reasoned over (tamper-evident)."""

    canonical = json.dumps(evidence_dicts, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dominant_kind(evidence_summary: dict) -> str:
    kinds: dict[str, int] = evidence_summary.get("kinds", {}) or {}
    if not kinds:
        return "empty"
    return max(kinds.items(), key=lambda kv: kv[1])[0]


def _select_validator(validators: list[Validator], evidence_summary: dict) -> Validator:
    key = _KEY_BY_DOMINANT_KIND.get(_dominant_kind(evidence_summary), "evidence-integrity")
    by_key = {v.validator_key: v for v in validators}
    return by_key.get(key) or validators[0]


# --- Validation engine ------------------------------------------------------


def assess(evidence: list[dict], evidence_summary: dict) -> tuple[str, float, str, list[dict]]:
    """Deterministically derive (recommendation, confidence, reasoning, findings).

    Confidence is the validator's certainty in its own recommendation given the
    quality of evidence — high when evidence is uniformly strong, low when it is
    missing, contradictory, or carries execution errors.
    """

    n = len(evidence)
    findings = [
        {
            "step_index": e.get("step_index"),
            "step_title": e.get("step_title"),
            "output_kind": e.get("output_kind"),
            "quality": e.get("quality"),
            "errors": bool((e.get("signals") or {}).get("error_markers")),
        }
        for e in evidence
    ]

    if n == 0:
        return (
            REJECTED,
            0.25,
            "No execution evidence was recorded; nothing to validate.",
            findings,
        )

    qualities: dict[str, int] = evidence_summary.get("qualities", {}) or {}
    strong = qualities.get("strong", 0)
    contradictory = qualities.get("contradictory", 0)
    missing = qualities.get("missing", 0)
    any_errors = bool(evidence_summary.get("any_errors"))
    strong_ratio = strong / n

    if missing > 0:
        rec = APPROVED_WITH_CONDITIONS if strong_ratio >= 0.5 else REJECTED
        conf = 0.40 + 0.30 * strong_ratio
        reason = (
            f"{missing} of {n} steps recorded no output; evidence is incomplete. "
            f"{strong} step(s) are strongly evidenced."
        )
    elif contradictory > 0:
        rec = APPROVED_WITH_CONDITIONS
        conf = 0.55 - 0.10 * (contradictory / n)
        reason = (
            f"{contradictory} step(s) show contradictory success/error markers; "
            "settlement should carry remediation conditions."
        )
    elif any_errors:
        rec = APPROVED_WITH_CONDITIONS if strong_ratio >= 0.5 else REJECTED
        conf = 0.45 + 0.25 * strong_ratio
        reason = (
            "Execution evidence contains error markers; "
            f"{strong}/{n} steps remain strongly evidenced."
        )
    elif strong_ratio >= 1.0:
        rec = APPROVED
        conf = 0.92
        reason = f"All {n} steps are strongly evidenced with no errors or contradictions."
    elif strong_ratio >= 0.6:
        rec = APPROVED
        conf = 0.70 + 0.20 * strong_ratio
        reason = f"{strong}/{n} steps are strongly evidenced; no errors detected."
    else:
        rec = APPROVED_WITH_CONDITIONS
        conf = 0.50 + 0.20 * strong_ratio
        reason = (
            f"Only {strong}/{n} steps are strongly evidenced; "
            "evidence is thin but non-conflicting."
        )

    # Proof-of-work grounding: a deliverable backed by sources that were fetched
    # live and bound to a content sha256 is independently checkable, so it earns
    # confidence. An unstructured deliverable that grounds nothing is, by the
    # same standard, unverifiable — the validator lowers its certainty and says
    # so rather than rubber-stamping asserted claims.
    grounding = evidence_summary.get("grounding") or {}
    verified = int(grounding.get("sources_verified", 0) or 0)
    if verified > 0:
        conf = min(0.99, conf + min(0.06, 0.02 * verified))
        reason += (
            f" Grounded in {verified} content-hashed source(s) fetched during "
            "execution, so the deliverable's claims are independently checkable."
        )
        findings.append(
            {
                "step_index": None,
                "step_title": "Proof-of-work grounding",
                "output_kind": "grounding",
                "quality": "strong",
                "errors": False,
            }
        )
    elif evidence_summary.get("unstructured_present"):
        conf = max(0.20, conf - 0.10)
        reason += (
            " No sources were fetched and content-hashed during execution; the "
            "free-text claims are not independently verifiable."
        )
        findings.append(
            {
                "step_index": None,
                "step_title": "Proof-of-work grounding",
                "output_kind": "grounding",
                "quality": "missing",
                "errors": False,
            }
        )

    return rec, round(max(0.20, min(0.99, conf)), 2), reason, findings


def run_validation(
    session: Session,
    *,
    objective_id: str,
    workspace_id: str,
    evidence: list[dict],
    evidence_summary: dict,
    executor_agent_id: str | None,
    evaluation_id: str | None = None,
    role_id: str | None = None,
) -> ValidationRecord:
    """Run an independent validation pass and persist a tamper-evident record.

    The selected validator is, by construction, never the executor agent: it is
    drawn from the workspace's system-validator set, a disjoint identity space
    from the agent registry.

    When ``role_id`` is given the record is scoped to one coordination sub-task,
    so the same engine validates an individual sub-task's evidence exactly as it
    validates the whole objective — no parallel sub-task validator.
    """

    validators = ensure_validators(session, workspace_id)
    validator = _select_validator(validators, evidence_summary)

    recommendation, confidence, reasoning, findings = assess(evidence, evidence_summary)
    digest = evidence_hash(evidence)

    record = ValidationRecord(
        objective_id=objective_id,
        role_id=role_id,
        validator_id=validator.id,
        evaluation_id=evaluation_id,
        recommendation=recommendation,
        confidence=confidence,
        reasoning=reasoning,
        findings=findings,
        evidence_hash=digest,
        evidence_summary=evidence_summary,
        executor_agent_id=executor_agent_id,
        independent_of_executor=True,  # validator identity is never an executor
    )
    session.add(record)

    # Update validator throughput + rolling mean confidence.
    prior = validator.validations_count
    validator.validations_count = prior + 1
    validator.mean_confidence = round(
        ((validator.mean_confidence * prior) + confidence) / validator.validations_count, 4
    )
    validator.updated_at = datetime.now(timezone.utc)
    session.add(validator)
    session.flush()
    return record


def latest_record(
    session: Session, objective_id: str, role_id: str | None = None
) -> ValidationRecord | None:
    """Most recent validation record for an objective, or a specific sub-task.

    Passing ``role_id`` returns the latest record scoped to that sub-task;
    omitting it returns the latest **objective-level** record (role_id is NULL),
    so sub-task validations never shadow the objective's own validation.
    """

    stmt = select(ValidationRecord).where(
        ValidationRecord.objective_id == objective_id
    )
    if role_id is None:
        stmt = stmt.where(ValidationRecord.role_id.is_(None))
    else:
        stmt = stmt.where(ValidationRecord.role_id == role_id)
    return session.exec(stmt.order_by(ValidationRecord.created_at.desc())).first()


def record_authorization(
    session: Session,
    *,
    objective_id: str,
    raw_criteria: object,
    evidence: list[dict],
    approved: bool,
    role_id: str | None = None,
    findings: list[dict] | None = None,
) -> SettlementAuthorization:
    """Persist the evidence-grounded authorization to settle an objective.

    This is the deterministic bridge from *success criteria* to *the specific
    evidence that satisfies them* to *payment*. It maps each criterion to the
    recorded evidence (via the criteria engine), rolls those per-criterion
    verdicts into an evidence-derived verdict, and binds the whole thing to the
    same ``evidence_hash`` the independent validator reasoned over so the
    authorization is tamper-evident and auditable after the fact.

    The human decision stays authoritative: ``authorized`` follows ``approved``.
    But ``evidence_verdict`` and ``aligned_with_evidence`` record whether the
    recorded evidence independently supported that decision — which is exactly
    the "why was this agent paid?" trail.
    """

    # Prefer the Copilot's semantic per-criterion verdicts (it read the real
    # deliverable) over the keyword engine, which can't recognize satisfaction
    # in free-text and returns a hollow 0/N. Falls back to keyword when no
    # findings are available.
    if findings:
        results = criteria.results_from_findings(raw_criteria, findings, evidence)
    else:
        results = criteria.evaluate_criteria(raw_criteria, evidence)
    summary = criteria.summarize_satisfaction(results)
    digest = evidence_hash(evidence)

    evidence_pass = summary["verdict"] != REJECTED
    aligned = evidence_pass == approved

    authorization = SettlementAuthorization(
        objective_id=objective_id,
        role_id=role_id,
        evidence_hash=digest,
        criteria_results=results,
        criteria_total=summary["total"],
        criteria_satisfied=summary["satisfied"],
        criteria_failed=summary["failed"],
        criteria_indeterminate=summary["indeterminate"],
        evidence_verdict=summary["verdict"],
        headline=summary["headline"],
        governance_approved=approved,
        aligned_with_evidence=aligned,
        authorized=approved,
    )
    session.add(authorization)
    session.flush()
    return authorization


def latest_authorization(
    session: Session, objective_id: str, role_id: str | None = None
) -> SettlementAuthorization | None:
    """Most recent settlement authorization for an objective, or a sub-task.

    Passing ``role_id`` scopes to one sub-task's authorization; omitting it
    returns the latest **objective-level** authorization (role_id is NULL).
    """

    stmt = select(SettlementAuthorization).where(
        SettlementAuthorization.objective_id == objective_id
    )
    if role_id is None:
        stmt = stmt.where(SettlementAuthorization.role_id.is_(None))
    else:
        stmt = stmt.where(SettlementAuthorization.role_id == role_id)
    return session.exec(
        stmt.order_by(SettlementAuthorization.created_at.desc())
    ).first()


def reconcile_outcome(
    session: Session, *, objective_id: str, approved: bool
) -> list[ValidationRecord]:
    """Reconcile validation records against the authoritative human decision.

    A record is *upheld* when its recommendation agreed with the final decision
    (recommended pass + approved, or recommended reject + rejected) and
    *overturned* otherwise. Validator accuracy counters are updated so trust in
    a validator reflects how often the network kept its call.
    """

    outcome = APPROVED if approved else REJECTED
    records = session.exec(
        select(ValidationRecord).where(
            ValidationRecord.objective_id == objective_id,
            ValidationRecord.outcome.is_(None),
        )
    ).all()
    reconciled: list[ValidationRecord] = []
    now = datetime.now(timezone.utc)
    for record in records:
        recommended_pass = record.recommendation != REJECTED
        upheld = recommended_pass == approved
        record.outcome = outcome
        record.upheld = upheld
        record.reconciled_at = now
        session.add(record)

        validator = session.get(Validator, record.validator_id)
        if validator is not None:
            if upheld:
                validator.upheld_count += 1
            else:
                validator.overturned_count += 1
            validator.updated_at = now
            session.add(validator)
        reconciled.append(record)
    if reconciled:
        session.flush()
    return reconciled
