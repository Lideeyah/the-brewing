"""Agent identity registry — ERC-8004-shaped, DB-backed.

Issues every registered agent a deterministic, on-chain-ready identity token
(owner, capabilities, service endpoints, reputation history) and provides the
blind-signature feedback flow: an agent signs a commitment *before* an
evaluation outcome is revealed, so it cannot selectively participate in only
positive reviews.

The "signing" here is an HMAC stand-in for the agent's agentic-wallet signature
so the sign-before-reveal invariant is demonstrable without a wallet in the
loop. In production the private key never leaves the agentic wallet; this
module's interfaces stay the same and the HMAC is swapped for a real signature
verification.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import (
    AgentIdentity,
    EscrowState,
    FeedbackCommitment,
    Objective,
    ObjectiveStatus,
    ReputationEvent,
    Settlement,
    SettlementStatus,
    ValidationRecord,
    WorkflowRole,
)

# Starting reputation baseline once an agent has at least one outcome.
_NEUTRAL_BASELINE = 50.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_token_id(owner: str, name: str, salt: str | None = None) -> str:
    """Deterministic, collision-resistant on-chain-ready identity token id.

    Mirrors how an ERC-8004 agentId would be derived from owner + agent card.
    """

    salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256(f"{owner}|{name}|{salt}".encode()).hexdigest()
    return f"0x{digest[:40]}"  # 20-byte, address-shaped for EVM mirroring


def register_agent(
    session: Session,
    *,
    workspace_id: str,
    owner: str,
    name: str,
    capabilities: list[str],
    service_endpoints: list[dict],
    metadata_uri: str | None = None,
    description: str | None = None,
    pricing: str | None = None,
    discoverable: bool = True,
    pricing_model: str = "fixed",
    min_objective_value_usdc: str | None = None,
    min_role_compensation_usdc: str | None = None,
    availability: str = "available",
    max_concurrent: int = 5,
) -> AgentIdentity:
    """Mint a new agent identity token within a workspace."""

    signing_secret = secrets.token_hex(32)
    signing_pubkey = hashlib.sha256(signing_secret.encode()).hexdigest()

    # Ensure token uniqueness (deterministic id + random salt makes clashes
    # vanishingly unlikely, but loop defensively).
    token_id = generate_token_id(owner, name)
    while session.exec(
        select(AgentIdentity).where(AgentIdentity.token_id == token_id)
    ).first():
        token_id = generate_token_id(owner, name)

    agent = AgentIdentity(
        workspace_id=workspace_id,
        token_id=token_id,
        owner=owner,
        name=name,
        description=description,
        capabilities=list(capabilities or []),
        service_endpoints=list(service_endpoints or []),
        pricing=pricing,
        discoverable=discoverable,
        metadata_uri=metadata_uri,
        pricing_model=pricing_model,
        min_objective_value_usdc=min_objective_value_usdc,
        min_role_compensation_usdc=min_role_compensation_usdc,
        availability=availability,
        max_concurrent=max_concurrent,
        signing_secret=signing_secret,
        signing_pubkey=signing_pubkey,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent


def _sign(agent: AgentIdentity, message: str) -> str:
    """HMAC stand-in for the agent's agentic-wallet signature."""

    key = (agent.signing_secret or "").encode()
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def commit_feedback(
    session: Session, *, agent: AgentIdentity, objective_id: str
) -> FeedbackCommitment:
    """Capture a blind, signed feedback commitment *before* outcome reveal.

    The commitment hash binds the agent + objective + a fresh nonce, but
    carries no outcome. The signature is taken now, so the agent is committed
    to the feedback whatever the result turns out to be.
    """

    nonce = secrets.token_hex(16)
    commitment_hash = hashlib.sha256(
        f"{agent.token_id}|{objective_id}|{nonce}".encode()
    ).hexdigest()
    signature = _sign(agent, commitment_hash)

    commitment = FeedbackCommitment(
        agent_id=agent.id,
        objective_id=objective_id,
        nonce=nonce,
        commitment_hash=commitment_hash,
        signature=signature,
        revealed=False,
    )
    session.add(commitment)
    session.commit()
    session.refresh(commitment)
    return commitment


def verify_commitment(agent: AgentIdentity, commitment: FeedbackCommitment) -> bool:
    """Recompute and verify the pre-reveal signature."""

    expected = _sign(agent, commitment.commitment_hash)
    return hmac.compare_digest(expected, commitment.signature)


def _recompute_score(agent: AgentIdentity) -> float:
    total = agent.jobs_completed + agent.jobs_failed
    if total == 0:
        return 0.0
    # Success ratio anchored around a neutral baseline so a single outcome does
    # not swing the score to an extreme.
    ratio = agent.jobs_completed / total
    return round(_NEUTRAL_BASELINE + (ratio - 0.5) * 100.0, 2)


def record_outcome(
    session: Session,
    *,
    agent: AgentIdentity,
    objective_id: str | None,
    success: bool,
    note: str | None = None,
) -> ReputationEvent:
    """Append an outcome to the agent's reputation history and update the score.

    This is the single mutation point for reputation; both the manual reveal
    flow and the automatic settlement wiring (Step 5) call it.
    """

    if success:
        agent.jobs_completed += 1
        kind = "job.completed"
        delta = 1.0
    else:
        agent.jobs_failed += 1
        kind = "job.failed"
        delta = -1.0

    agent.reputation_score = _recompute_score(agent)
    agent.updated_at = _now()
    session.add(agent)

    event = ReputationEvent(
        agent_id=agent.id,
        objective_id=objective_id,
        kind=kind,
        delta=delta,
        score_after=agent.reputation_score,
        note=note,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def record_settlement_outcome(
    session: Session, *, objective: Objective, success: bool
) -> list[AgentIdentity]:
    """Wire a settlement outcome back into the agent registry automatically.

    Called when an objective settles (success) or is slashed (failure). It:
      1. Auto-reveals any pending blind-signature commitments for the objective
         with the real outcome — closing the sign-before-reveal loop so a
         committed agent's reputation moves whether the result is good or bad.
      2. If the objective has an assigned agent that had no commitment, records
         the outcome directly.
      3. Attributes a per-role outcome to every agent bound to a workflow role,
         so a multi-agent objective moves the reputation of each contributor —
         crediting agents on released roles and debiting them on slashed ones.

    Returns the agent identities whose reputation was updated. Never raises on a
    missing/unregistered agent — settlement must not be blocked by the registry.
    """

    affected: list[AgentIdentity] = []
    revealed_agent_ids: set[str] = set()
    handled_agent_ids: set[str] = set()

    pending = session.exec(
        select(FeedbackCommitment).where(
            FeedbackCommitment.objective_id == objective.id,
            FeedbackCommitment.revealed == False,  # noqa: E712
        )
    ).all()
    for commitment in pending:
        agent = session.get(AgentIdentity, commitment.agent_id)
        if agent is None:
            continue
        try:
            reveal_feedback(
                session,
                agent=agent,
                commitment=commitment,
                success=success,
                note="auto-revealed on settlement",
            )
        except ValueError:
            # Signature failed to verify — skip rather than block settlement.
            continue
        revealed_agent_ids.add(agent.id)
        handled_agent_ids.add(agent.id)
        affected.append(agent)

    if objective.agent_id and objective.agent_id not in handled_agent_ids:
        agent = session.get(AgentIdentity, objective.agent_id)
        if agent is not None:
            record_outcome(
                session,
                agent=agent,
                objective_id=objective.id,
                success=success,
                note="settlement outcome",
            )
            handled_agent_ids.add(agent.id)
            affected.append(agent)

    # Per-role attribution: every agent bound to a workflow role earns the
    # role's outcome. A role marked "slashed" debits its agent even when the
    # objective as a whole settled (partial settlement), and vice versa. Each
    # agent is counted once per objective to avoid inflating from repeat roles.
    roles = session.exec(
        select(WorkflowRole).where(WorkflowRole.objective_id == objective.id)
    ).all()
    for role in roles:
        agent_id = role.assigned_agent_id
        if not agent_id or agent_id in handled_agent_ids:
            continue
        agent = session.get(AgentIdentity, agent_id)
        if agent is None:
            continue
        role_success = (
            role.outcome == "released" if role.outcome is not None else success
        )
        record_outcome(
            session,
            agent=agent,
            objective_id=objective.id,
            success=role_success,
            note=f"role settlement outcome ({role.role_key})",
        )
        handled_agent_ids.add(agent_id)
        affected.append(agent)

    return affected


def reveal_feedback(
    session: Session,
    *,
    agent: AgentIdentity,
    commitment: FeedbackCommitment,
    success: bool,
    note: str | None = None,
) -> FeedbackCommitment:
    """Reveal a previously committed outcome and fold it into reputation.

    Requires a verified pre-reveal signature, enforcing that the agent was
    bound to the feedback before it could see the result.
    """

    if commitment.revealed:
        return commitment
    if not verify_commitment(agent, commitment):
        raise ValueError("commitment signature does not verify")

    commitment.outcome = "success" if success else "failure"
    commitment.revealed = True
    commitment.revealed_at = _now()
    session.add(commitment)

    record_outcome(
        session,
        agent=agent,
        objective_id=commitment.objective_id,
        success=success,
        note=note or "blind-signature feedback revealed",
    )
    session.refresh(commitment)
    return commitment


def _associated_objective_ids(session: Session, agent: AgentIdentity) -> set[str]:
    """Every objective the agent contributed to — as executor or via a role."""

    ids: set[str] = set()
    direct = session.exec(
        select(Objective.id).where(Objective.agent_id == agent.id)
    ).all()
    ids.update(direct)
    role_objs = session.exec(
        select(WorkflowRole.objective_id).where(
            WorkflowRole.assigned_agent_id == agent.id
        )
    ).all()
    ids.update(role_objs)
    return ids


def trust_dimensions(session: Session, agent: AgentIdentity) -> list[dict]:
    """Decompose an agent's reputation into independent, evidence-backed axes.

    Reputation is more than a single success ratio. Each dimension is computed
    live from the lifecycle tables for the objectives this agent contributed to,
    and reports its own sample size so a consumer can weigh thin signals. A
    dimension with no sample yet returns ``value=None`` rather than a misleading
    zero.
    """

    obj_ids = _associated_objective_ids(session, agent)
    objectives = (
        session.exec(select(Objective).where(Objective.id.in_(obj_ids))).all()
        if obj_ids
        else []
    )

    # --- Delivery: completed vs. failed outcomes folded into reputation. ---
    delivered_total = agent.jobs_completed + agent.jobs_failed
    delivery = (
        agent.jobs_completed / delivered_total if delivered_total else None
    )

    # --- Settlement reliability: settled vs. slashed across objectives. ---
    settled = sum(1 for o in objectives if o.status == ObjectiveStatus.SETTLED)
    slashed = sum(1 for o in objectives if o.status == ObjectiveStatus.SLASHED)
    settle_total = settled + slashed
    settlement_reliability = settled / settle_total if settle_total else None

    # --- Dispute-free rate: share of objectives never disputed. ---
    disputed = sum(1 for o in objectives if o.status == ObjectiveStatus.DISPUTED)
    dispute_free = (
        1 - (disputed / len(objectives)) if objectives else None
    )

    # --- Validation integrity: independent validations that were upheld. ---
    upheld = 0
    reconciled = 0
    if obj_ids:
        records = session.exec(
            select(ValidationRecord).where(
                ValidationRecord.objective_id.in_(obj_ids),
                ValidationRecord.upheld != None,  # noqa: E711
            )
        ).all()
        reconciled = len(records)
        upheld = sum(1 for r in records if r.upheld)
    validation_integrity = upheld / reconciled if reconciled else None

    # --- SLA compliance: settled within the objective's stated deadline. ---
    on_time = 0
    sla_sample = 0
    for o in objectives:
        if o.status != ObjectiveStatus.SETTLED:
            continue
        try:
            deadline_hours = float((o.sla_config or {}).get("deadline_hours") or 0)
        except (TypeError, ValueError):
            deadline_hours = 0
        if deadline_hours <= 0:
            continue
        escrow = session.exec(
            select(EscrowState)
            .where(EscrowState.objective_id == o.id)
            .order_by(EscrowState.created_at.asc())
        ).first()
        settlement = session.exec(
            select(Settlement)
            .where(
                Settlement.objective_id == o.id,
                Settlement.status == SettlementStatus.SETTLED,
            )
            .order_by(Settlement.created_at.desc())
        ).first()
        if not escrow or not settlement:
            continue
        sla_sample += 1
        elapsed_hours = (
            settlement.created_at - escrow.created_at
        ).total_seconds() / 3600.0
        if elapsed_hours <= deadline_hours:
            on_time += 1
    sla_compliance = on_time / sla_sample if sla_sample else None

    return [
        {
            "key": "delivery",
            "label": "Delivery",
            "value": delivery,
            "sample_size": delivered_total,
            "hint": "Outcomes completed vs. failed.",
        },
        {
            "key": "settlement_reliability",
            "label": "Settlement reliability",
            "value": settlement_reliability,
            "sample_size": settle_total,
            "hint": "Objectives settled vs. slashed.",
        },
        {
            "key": "validation_integrity",
            "label": "Validation integrity",
            "value": validation_integrity,
            "sample_size": reconciled,
            "hint": "Independent validations upheld on reconciliation.",
        },
        {
            "key": "dispute_free",
            "label": "Dispute-free",
            "value": dispute_free,
            "sample_size": len(objectives),
            "hint": "Objectives that were never disputed.",
        },
        {
            "key": "sla_compliance",
            "label": "SLA compliance",
            "value": sla_compliance,
            "sample_size": sla_sample,
            "hint": "Settled within the objective's deadline.",
        },
    ]
