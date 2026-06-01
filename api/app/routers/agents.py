"""Agent identity registry routes (ERC-8004-shaped).

Register agents (minting an on-chain-ready identity token), read their identity
and reputation history, and run the blind-signature feedback flow that binds an
agent to its evaluation feedback before the outcome is revealed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.domain import registry
from app.models import (
    AgentIdentity,
    FeedbackCommitment,
    Objective,
    PayoutAddressEvent,
    ReputationEvent,
    User,
    Workspace,
)
from app.schemas import (
    AgentDetailOut,
    AgentFeedbackOut,
    AgentIdentityOut,
    AgentRegisterIn,
    FeedbackCommitIn,
    FeedbackCommitmentOut,
    FeedbackObjectiveOption,
    FeedbackRevealIn,
    PayoutAddressEventOut,
    PayoutChallengeIn,
    PayoutChallengeOut,
    PayoutVerifyIn,
    ReputationDimension,
    ReputationEventOut,
)
from app.services import workspace as workspace_service

router = APIRouter(prefix="/agents", tags=["agents"])


def current_workspace(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Workspace:
    return workspace_service.get_or_create_default_workspace(session, user)


def _agent_out(agent: AgentIdentity) -> AgentIdentityOut:
    total = agent.jobs_completed + agent.jobs_failed
    return AgentIdentityOut(
        id=agent.id,
        token_id=agent.token_id,
        owner=agent.owner,
        name=agent.name,
        description=agent.description,
        capabilities=list(agent.capabilities or []),
        service_endpoints=list(agent.service_endpoints or []),
        pricing=agent.pricing,
        discoverable=agent.discoverable,
        reputation_score=agent.reputation_score,
        jobs_completed=agent.jobs_completed,
        jobs_failed=agent.jobs_failed,
        rated=total > 0,
        success_rate=round(agent.jobs_completed / total, 4) if total > 0 else None,
        pricing_model=agent.pricing_model,
        min_objective_value_usdc=agent.min_objective_value_usdc,
        min_role_compensation_usdc=agent.min_role_compensation_usdc,
        availability=agent.availability,
        max_concurrent=agent.max_concurrent,
        metadata_uri=agent.metadata_uri,
        registry_chain=agent.registry_chain,
        registry_address=agent.registry_address,
        signing_pubkey=agent.signing_pubkey,
        payout_address=agent.payout_address,
        payout_blockchain=agent.payout_blockchain,
        payout_address_verified=agent.payout_address_verified,
        payout_address_verified_at=agent.payout_address_verified_at,
        created_at=agent.created_at,
    )


def _payout_event_out(ev: PayoutAddressEvent) -> PayoutAddressEventOut:
    return PayoutAddressEventOut(
        id=ev.id,
        action=ev.action,
        old_address=ev.old_address,
        new_address=ev.new_address,
        verified=ev.verified,
        actor=ev.actor,
        note=ev.note,
        created_at=ev.created_at,
    )


def _event_out(ev: ReputationEvent) -> ReputationEventOut:
    return ReputationEventOut(
        id=ev.id,
        objective_id=ev.objective_id,
        kind=ev.kind,
        delta=ev.delta,
        score_after=ev.score_after,
        note=ev.note,
        created_at=ev.created_at,
    )


def _commitment_out(
    c: FeedbackCommitment, objective_title: str | None = None
) -> FeedbackCommitmentOut:
    return FeedbackCommitmentOut(
        id=c.id,
        agent_id=c.agent_id,
        objective_id=c.objective_id,
        objective_title=objective_title,
        commitment_hash=c.commitment_hash,
        signature=c.signature,
        revealed=c.revealed,
        outcome=c.outcome,
        created_at=c.created_at,
        revealed_at=c.revealed_at,
    )


def _get_owned_agent(
    session: Session, workspace: Workspace, agent_id: str
) -> AgentIdentity:
    agent = session.get(AgentIdentity, agent_id)
    if agent is None or agent.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.post("", response_model=AgentIdentityOut, status_code=status.HTTP_201_CREATED)
def register_agent(
    body: AgentRegisterIn,
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> AgentIdentityOut:
    agent = registry.register_agent(
        session,
        workspace_id=workspace.id,
        owner=body.owner,
        name=body.name,
        description=body.description,
        capabilities=body.capabilities,
        service_endpoints=[e.model_dump() for e in body.service_endpoints],
        pricing=body.pricing,
        discoverable=body.discoverable,
        metadata_uri=body.metadata_uri,
        pricing_model=body.pricing_model,
        min_objective_value_usdc=body.min_objective_value_usdc,
        min_role_compensation_usdc=body.min_role_compensation_usdc,
        availability=body.availability,
        max_concurrent=body.max_concurrent,
    )
    return _agent_out(agent)


@router.get("", response_model=list[AgentIdentityOut])
def list_agents(
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> list[AgentIdentityOut]:
    agents = session.exec(
        select(AgentIdentity)
        .where(AgentIdentity.workspace_id == workspace.id)
        .order_by(AgentIdentity.created_at.desc())
    ).all()
    return [_agent_out(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentDetailOut)
def get_agent(
    agent_id: str,
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> AgentDetailOut:
    agent = _get_owned_agent(session, workspace, agent_id)
    history = session.exec(
        select(ReputationEvent)
        .where(ReputationEvent.agent_id == agent.id)
        .order_by(ReputationEvent.created_at.desc())
    ).all()
    base = _agent_out(agent)
    dimensions = registry.trust_dimensions(session, agent)
    payouts = registry.payout_history(session, agent)
    return AgentDetailOut(
        **base.model_dump(),
        reputation_history=[_event_out(e) for e in history],
        trust_dimensions=[ReputationDimension(**d) for d in dimensions],
        payout_history=[_payout_event_out(p) for p in payouts],
    )


@router.post("/{agent_id}/payout/challenge", response_model=PayoutChallengeOut)
def request_payout_challenge(
    agent_id: str,
    body: PayoutChallengeIn,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> PayoutChallengeOut:
    """Issue a proof-of-control challenge for a candidate payout address.

    The agent must sign the returned `challenge` with the payout wallet's
    private key and submit the signature to `/payout/verify`. Until that
    succeeds, the address is not usable as a settlement destination.
    """
    agent = _get_owned_agent(session, workspace, agent_id)
    try:
        challenge, expires_at = registry.issue_payout_challenge(
            session,
            agent=agent,
            address=body.address,
            blockchain=body.blockchain,
            actor=user.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    return PayoutChallengeOut(
        agent_id=agent.id,
        address=agent.payout_challenge_address or body.address,
        challenge=challenge,
        expires_at=expires_at,
    )


@router.post("/{agent_id}/payout/verify", response_model=AgentDetailOut)
def verify_payout_address(
    agent_id: str,
    body: PayoutVerifyIn,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> AgentDetailOut:
    """Verify the signed challenge and bind the proven payout address.

    On success the address becomes the agent's verified settlement destination;
    the change is recorded in the payout audit trail.
    """
    agent = _get_owned_agent(session, workspace, agent_id)
    try:
        agent = registry.verify_payout_address(
            session, agent=agent, signature=body.signature, actor=user.id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    history = session.exec(
        select(ReputationEvent)
        .where(ReputationEvent.agent_id == agent.id)
        .order_by(ReputationEvent.created_at.desc())
    ).all()
    base = _agent_out(agent)
    dimensions = registry.trust_dimensions(session, agent)
    payouts = registry.payout_history(session, agent)
    return AgentDetailOut(
        **base.model_dump(),
        reputation_history=[_event_out(e) for e in history],
        trust_dimensions=[ReputationDimension(**d) for d in dimensions],
        payout_history=[_payout_event_out(p) for p in payouts],
    )


@router.get("/{agent_id}/feedback", response_model=AgentFeedbackOut)
def list_feedback(
    agent_id: str,
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> AgentFeedbackOut:
    """Read model for the blind-signature feedback flow.

    Returns the agent's commitment audit trail (committed + revealed) plus the
    pick-list of associated objectives still available to commit feedback on, so
    the UI never has to ask for a raw objective id.
    """
    agent = _get_owned_agent(session, workspace, agent_id)

    commitments = session.exec(
        select(FeedbackCommitment)
        .where(FeedbackCommitment.agent_id == agent.id)
        .order_by(FeedbackCommitment.created_at.desc())
    ).all()

    # Resolve objective titles in one pass for readable display.
    associated = registry.associated_objective_ids(session, agent)
    needed_ids = associated | {c.objective_id for c in commitments}
    titles: dict[str, Objective] = {}
    if needed_ids:
        rows = session.exec(
            select(Objective).where(Objective.id.in_(needed_ids))
        ).all()
        titles = {o.id: o for o in rows}

    committed_ids = {c.objective_id for c in commitments}
    options = [
        FeedbackObjectiveOption(
            id=o.id,
            title=o.title,
            status=str(getattr(o.status, "value", o.status)),
            committed=o.id in committed_ids,
        )
        for oid in associated
        if (o := titles.get(oid)) is not None
    ]
    options.sort(key=lambda x: (x.committed, x.title.lower()))

    return AgentFeedbackOut(
        commitments=[
            _commitment_out(
                c, titles[c.objective_id].title if c.objective_id in titles else None
            )
            for c in commitments
        ],
        objectives=options,
    )


@router.post("/{agent_id}/feedback/commit", response_model=FeedbackCommitmentOut)
def commit_feedback(
    agent_id: str,
    body: FeedbackCommitIn,
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> FeedbackCommitmentOut:
    agent = _get_owned_agent(session, workspace, agent_id)
    obj = session.get(Objective, body.objective_id)
    if obj is None or obj.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found"
        )
    commitment = registry.commit_feedback(
        session, agent=agent, objective_id=body.objective_id
    )
    return _commitment_out(commitment, obj.title)


@router.post("/{agent_id}/feedback/reveal", response_model=FeedbackCommitmentOut)
def reveal_feedback(
    agent_id: str,
    body: FeedbackRevealIn,
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> FeedbackCommitmentOut:
    agent = _get_owned_agent(session, workspace, agent_id)
    commitment = session.get(FeedbackCommitment, body.commitment_id)
    if commitment is None or commitment.agent_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Commitment not found"
        )
    try:
        commitment = registry.reveal_feedback(
            session,
            agent=agent,
            commitment=commitment,
            success=body.success,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    obj = session.get(Objective, commitment.objective_id)
    return _commitment_out(commitment, obj.title if obj else None)
