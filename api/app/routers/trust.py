"""Trust API — public reputation lookup for any registered agent.

The reputation feedback loop folds every settled/slashed outcome back into the
agent identity registry automatically (see ``registry.record_settlement_outcome``
wired into the settlement edge). This router exposes the *read* side: a
counterparty can query an agent's trust by its on-chain-ready identity token
before transacting, without needing the owning workspace's credentials.

Lookups are global by ``token_id`` (the ERC-8004-shaped agentId), not scoped to
a workspace — trust is a cross-tenant signal. Authentication is still required
so the endpoint is not anonymously scrapeable, but no workspace ownership of the
agent is required to read its score.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import AgentIdentity, ReputationEvent, User
from app.schemas import ReputationEventOut, TrustScoreOut

router = APIRouter(prefix="/trust", tags=["trust"])

# How many recent reputation events to surface alongside the score.
_RECENT_EVENT_LIMIT = 10


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


def _trust_out(agent: AgentIdentity, events: list[ReputationEvent]) -> TrustScoreOut:
    total = agent.jobs_completed + agent.jobs_failed
    success_rate = (
        round(agent.jobs_completed / total, 4) if total > 0 else None
    )
    last_outcome_at = events[0].created_at if events else None
    return TrustScoreOut(
        token_id=agent.token_id,
        name=agent.name,
        owner=agent.owner,
        reputation_score=agent.reputation_score,
        jobs_completed=agent.jobs_completed,
        jobs_failed=agent.jobs_failed,
        total_jobs=total,
        success_rate=success_rate,
        rated=total > 0,
        capabilities=list(agent.capabilities or []),
        service_endpoints=list(agent.service_endpoints or []),
        registry_chain=agent.registry_chain,
        registry_address=agent.registry_address,
        last_outcome_at=last_outcome_at,
        recent_events=[_event_out(e) for e in events],
    )


@router.get("/{token_id}", response_model=TrustScoreOut)
def get_trust_score(
    token_id: str,
    _user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> TrustScoreOut:
    """Return the reputation snapshot for an agent by its identity token."""

    agent = session.exec(
        select(AgentIdentity).where(AgentIdentity.token_id == token_id)
    ).first()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered agent found for that identity token.",
        )
    events = session.exec(
        select(ReputationEvent)
        .where(ReputationEvent.agent_id == agent.id)
        .order_by(ReputationEvent.created_at.desc())
        .limit(_RECENT_EVENT_LIMIT)
    ).all()
    return _trust_out(agent, list(events))
