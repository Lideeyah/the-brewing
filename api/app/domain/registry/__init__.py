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

from app.domain import payout as payout_proof
from app.models import (
    AgentIdentity,
    EscrowState,
    FeedbackCommitment,
    Objective,
    ObjectiveStatus,
    PayoutAddressEvent,
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


# Network-level executor agents, seeded per workspace on first use (mirrors the
# system-validator seeding) so a tenant always has a roster to assign roles to.
# Capabilities map onto the workflow ROLE_CATALOG keys. Validators are seeded
# separately (app.domain.validation); these are the *executing* counterparties.
SYSTEM_AGENTS: list[dict] = [
    {
        "owner": "system:atlas",
        "name": "Atlas Research Agent",
        "capabilities": ["research", "planner"],
        "description": (
            "Gathers the source material and evidence an objective depends on — "
            "market scans, competitor intelligence, and data collection."
        ),
    },
    {
        "owner": "system:vela",
        "name": "Vela Analysis Agent",
        "capabilities": ["analysis"],
        "description": (
            "Synthesizes raw findings into structured, decision-ready "
            "conclusions, comparisons, and recommendations."
        ),
    },
    {
        "owner": "system:forge",
        "name": "Forge Execution Agent",
        "capabilities": ["executor", "planner"],
        "description": (
            "Produces the primary deliverable an objective asks for — reports, "
            "drafts, briefs, documents, and decks."
        ),
    },
    {
        "owner": "system:sentinel",
        "name": "Sentinel Review Agent",
        "capabilities": ["reviewer"],
        "description": (
            "Checks a deliverable against the objective's quality bar before it "
            "is submitted for independent validation and settlement."
        ),
    },
]


def ensure_system_agents(session: Session, workspace_id: str) -> list[AgentIdentity]:
    """Idempotently seed the system executor agents for a workspace.

    Returns the full roster (existing + newly created). Deduplicated by name so
    repeated calls never mint duplicates. A workspace that already has agents
    simply gets nothing added.
    """
    existing = session.exec(
        select(AgentIdentity).where(AgentIdentity.workspace_id == workspace_id)
    ).all()
    names = {a.name for a in existing}
    for spec in SYSTEM_AGENTS:
        if spec["name"] in names:
            continue
        register_agent(
            session,
            workspace_id=workspace_id,
            owner=spec["owner"],
            name=spec["name"],
            capabilities=spec["capabilities"],
            service_endpoints=[],
            description=spec["description"],
            discoverable=True,
        )
    return session.exec(
        select(AgentIdentity).where(AgentIdentity.workspace_id == workspace_id)
    ).all()


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


# --- Payout destination & proof-of-control (Escrow V1.5) -------------------


def _ensure_aware(dt: datetime) -> datetime:
    """Normalize a possibly-naive DB datetime to aware UTC for comparison."""

    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _log_payout_event(
    session: Session,
    *,
    agent: AgentIdentity,
    action: str,
    old_address: str | None = None,
    new_address: str | None = None,
    verified: bool = False,
    actor: str | None = None,
    note: str | None = None,
) -> PayoutAddressEvent:
    event = PayoutAddressEvent(
        agent_id=agent.id,
        workspace_id=agent.workspace_id,
        action=action,
        old_address=old_address,
        new_address=new_address,
        verified=verified,
        actor=actor,
        note=note,
    )
    session.add(event)
    return event


def issue_payout_challenge(
    session: Session,
    *,
    agent: AgentIdentity,
    address: str,
    blockchain: str | None = None,
    actor: str | None = None,
) -> tuple[str, datetime]:
    """Begin proof-of-control for a candidate payout address.

    Validates the address format, mints a one-time, time-boxed challenge the
    wallet must sign, and stores it as the agent's single outstanding challenge.
    Returns ``(challenge, expires_at)``. Raises ``ValueError`` on a malformed
    address. Does not touch the agent's *active* payout address — that only
    changes once control is proven via :func:`verify_payout_address`.
    """

    normalized = payout_proof.normalize_address(address)  # raises ValueError
    challenge = payout_proof.new_challenge(normalized)
    expires_at = _now() + payout_proof.CHALLENGE_TTL
    agent.payout_challenge = challenge
    agent.payout_challenge_address = normalized
    agent.payout_challenge_expires_at = expires_at
    if blockchain:
        agent.payout_blockchain = blockchain  # tentative; confirmed on verify
    agent.updated_at = _now()
    session.add(agent)
    _log_payout_event(
        session,
        agent=agent,
        action="challenge_issued",
        new_address=normalized,
        actor=actor,
        note="proof-of-control challenge issued",
    )
    session.commit()
    session.refresh(agent)
    return challenge, expires_at


def verify_payout_address(
    session: Session,
    *,
    agent: AgentIdentity,
    signature: str,
    actor: str | None = None,
) -> AgentIdentity:
    """Complete proof-of-control: verify the signature over the live challenge.

    On success the candidate address becomes the agent's verified payout
    destination and the challenge is consumed. A change away from a previously
    verified address is recorded as an audited ``changed`` event. Raises
    ``ValueError`` if there is no live challenge, it has expired, or the
    signature does not verify. Failures are audited too.
    """

    challenge = agent.payout_challenge
    candidate = agent.payout_challenge_address
    expires_at = agent.payout_challenge_expires_at
    if not challenge or not candidate:
        raise ValueError("no outstanding payout challenge; request one first")

    if expires_at is not None and _ensure_aware(expires_at) < _now():
        agent.payout_challenge = None
        agent.payout_challenge_address = None
        agent.payout_challenge_expires_at = None
        session.add(agent)
        _log_payout_event(
            session,
            agent=agent,
            action="verification_failed",
            new_address=candidate,
            actor=actor,
            note="challenge expired",
        )
        session.commit()
        raise ValueError("payout challenge expired; request a new one")

    if not payout_proof.verify_control(candidate, challenge, signature):
        _log_payout_event(
            session,
            agent=agent,
            action="verification_failed",
            new_address=candidate,
            actor=actor,
            note="signature did not verify",
        )
        session.commit()
        raise ValueError("signature does not prove control of the payout address")

    old_address = agent.payout_address
    changed = bool(old_address) and old_address != candidate
    agent.payout_address = candidate
    agent.payout_address_verified = True
    agent.payout_address_verified_at = _now()
    agent.payout_challenge = None
    agent.payout_challenge_address = None
    agent.payout_challenge_expires_at = None
    agent.updated_at = _now()
    session.add(agent)
    _log_payout_event(
        session,
        agent=agent,
        action="changed" if changed else "registered",
        old_address=old_address,
        new_address=candidate,
        verified=True,
        actor=actor,
        note="payout address control proven",
    )
    session.commit()
    session.refresh(agent)
    return agent


def clear_payout_address(
    session: Session, *, agent: AgentIdentity, actor: str | None = None
) -> AgentIdentity:
    """Remove the verified payout destination (audited).

    Settlement reverts to the mint fallback for this agent until a new address
    is proven, so clearing can never silently misdirect funds.
    """

    old_address = agent.payout_address
    agent.payout_address = None
    agent.payout_address_verified = False
    agent.payout_address_verified_at = None
    agent.payout_challenge = None
    agent.payout_challenge_address = None
    agent.payout_challenge_expires_at = None
    agent.updated_at = _now()
    session.add(agent)
    _log_payout_event(
        session,
        agent=agent,
        action="cleared",
        old_address=old_address,
        actor=actor,
        note="payout address cleared",
    )
    session.commit()
    session.refresh(agent)
    return agent


def resolve_verified_payout_address(agent: AgentIdentity | None) -> str | None:
    """The settlement-usable payout address, or ``None`` if not proven.

    The single predicate settlement relies on: only a *verified* address is ever
    returned, so an unproven or absent address transparently falls back to the
    mint path inside the ``_resolve_payout_wallet`` seam.
    """

    if agent is None:
        return None
    if agent.payout_address and agent.payout_address_verified:
        return agent.payout_address
    return None


def payout_history(
    session: Session, agent: AgentIdentity
) -> list[PayoutAddressEvent]:
    """Append-only audit trail of this agent's payout-address lifecycle."""

    return session.exec(
        select(PayoutAddressEvent)
        .where(PayoutAddressEvent.agent_id == agent.id)
        .order_by(PayoutAddressEvent.created_at.desc())
    ).all()


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
        # Sub-tasks settled independently already attributed their outcome to the
        # assigned agent at sub-task settle time; don't double-count here.
        if getattr(role, "settlement_status", "pending") in ("settled", "slashed"):
            handled_agent_ids.add(agent_id)
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


def associated_objective_ids(session: Session, agent: AgentIdentity) -> set[str]:
    """Public accessor: every objective id this agent contributed to."""

    return _associated_objective_ids(session, agent)


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
