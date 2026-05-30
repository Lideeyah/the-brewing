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
    ReputationEvent,
    User,
    Workspace,
)
from app.schemas import (
    AgentDetailOut,
    AgentIdentityOut,
    AgentRegisterIn,
    FeedbackCommitIn,
    FeedbackCommitmentOut,
    FeedbackRevealIn,
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
        created_at=agent.created_at,
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


def _commitment_out(c: FeedbackCommitment) -> FeedbackCommitmentOut:
    return FeedbackCommitmentOut(
        id=c.id,
        agent_id=c.agent_id,
        objective_id=c.objective_id,
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
    return AgentDetailOut(
        **base.model_dump(),
        reputation_history=[_event_out(e) for e in history],
        trust_dimensions=[ReputationDimension(**d) for d in dimensions],
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
    return _commitment_out(commitment)


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
    return _commitment_out(commitment)
