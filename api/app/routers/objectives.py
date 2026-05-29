"""Objective lifecycle routes.

The objective is the unit of coordination. These routes cover the first edges
of the lifecycle — Intent (create) and Governance (Copilot structuring) — and
expose the append-only governance timeline that powers observability.
Authorization is enforced API-side: an objective is only ever reachable through
the caller's own workspace.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.domain import copilot
from app.domain.governance import log_event
from app.models import GovernanceEvent, Objective, ObjectiveStatus, User, Workspace
from app.schemas import (
    GovernanceEventOut,
    ObjectiveCreate,
    ObjectiveDetailOut,
    ObjectiveOut,
)
from app.services import workspace as workspace_service

router = APIRouter(prefix="/objectives", tags=["objectives"])


def current_workspace(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Workspace:
    return workspace_service.get_or_create_default_workspace(session, user)


def _objective_out(obj: Objective) -> ObjectiveOut:
    return ObjectiveOut(
        id=obj.id,
        workspace_id=obj.workspace_id,
        title=obj.title,
        intent=obj.intent,
        status=obj.status,
        summary=obj.summary,
        escrow_amount_usdc=obj.escrow_amount_usdc,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _event_out(ev: GovernanceEvent) -> GovernanceEventOut:
    return GovernanceEventOut(
        id=ev.id,
        kind=ev.kind,
        message=ev.message,
        actor=ev.actor,
        data=ev.data,
        created_at=ev.created_at,
    )


def _get_owned_objective(
    session: Session, workspace: Workspace, objective_id: str
) -> Objective:
    obj = session.get(Objective, objective_id)
    if obj is None or obj.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Objective not found"
        )
    return obj


@router.post("", response_model=ObjectiveDetailOut, status_code=status.HTTP_201_CREATED)
def create_objective(
    body: ObjectiveCreate,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    intent = body.intent.strip()
    if not intent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Intent is required"
        )
    title = (body.title or intent.split("\n")[0])[:120].strip()

    obj = Objective(
        workspace_id=workspace.id,
        created_by=user.id,
        title=title,
        intent=intent,
        status=ObjectiveStatus.DRAFT,
    )
    session.add(obj)
    session.flush()
    log_event(
        session,
        objective_id=obj.id,
        kind="objective.created",
        message="Objective drafted from operational intent.",
        actor=user.id,
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.get("", response_model=list[ObjectiveOut])
def list_objectives(
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> list[ObjectiveOut]:
    objectives = session.exec(
        select(Objective)
        .where(Objective.workspace_id == workspace.id)
        .order_by(Objective.created_at.desc())
    ).all()
    return [_objective_out(o) for o in objectives]


@router.get("/{objective_id}", response_model=ObjectiveDetailOut)
def get_objective(
    objective_id: str,
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    obj = _get_owned_objective(session, workspace, objective_id)
    return _detail(session, obj)


@router.post("/{objective_id}/structure", response_model=ObjectiveDetailOut)
async def structure_objective(
    objective_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    obj = _get_owned_objective(session, workspace, objective_id)

    structured = await copilot.structure_intent(obj.intent, obj.title)

    obj.title = structured.get("title") or obj.title
    obj.summary = structured.get("summary")
    obj.governance_config = structured.get("governance_config", {})
    obj.sla_config = structured.get("sla_config", {})
    obj.settlement_config = structured.get("settlement_config", {})
    obj.orchestration_plan = structured.get("orchestration_plan", {})
    obj.escrow_amount_usdc = str(
        obj.settlement_config.get("recommended_escrow_usdc", obj.escrow_amount_usdc)
    )
    obj.status = ObjectiveStatus.COPILOT_STRUCTURED
    from datetime import datetime, timezone

    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)

    log_event(
        session,
        objective_id=obj.id,
        kind="objective.structured",
        message="Coordination Copilot structured the objective into governance, SLA, and settlement terms.",
        actor="copilot",
        data={"source": structured.get("_source")},
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


def _detail(session: Session, obj: Objective) -> ObjectiveDetailOut:
    events = session.exec(
        select(GovernanceEvent)
        .where(GovernanceEvent.objective_id == obj.id)
        .order_by(GovernanceEvent.created_at.asc())
    ).all()
    base = _objective_out(obj)
    return ObjectiveDetailOut(
        **base.model_dump(),
        governance_config=obj.governance_config,
        sla_config=obj.sla_config,
        settlement_config=obj.settlement_config,
        orchestration_plan=obj.orchestration_plan,
        timeline=[_event_out(e) for e in events],
    )
