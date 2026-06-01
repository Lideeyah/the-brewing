"""Workspace observability — the dashboard's read model.

Aggregates the objective lifecycle into mission-control metrics. The treasury
balance is read live from the SettlementProvider (best-effort) rather than
stored as truth.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.domain.settlement import get_settlement_provider
from app.domain.settlement.provider import WalletRef
from app.models import (
    GovernanceEvent,
    Objective,
    ObjectiveStatus,
    Settlement,
    SettlementStatus,
    User,
    Workspace,
)
from app.routers.auth import _workspace_out
from app.routers.objectives import _event_out, _objective_out
from app.schemas import OverviewMetric, OverviewOut, WorkspaceOut, WorkspaceUpdateIn
from app.services import workspace as workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
logger = logging.getLogger("brewing.workspaces")

_ACTIVE_STATES = {
    ObjectiveStatus.ESCROW_LOCKED,
    ObjectiveStatus.EXECUTING,
    ObjectiveStatus.UNDER_AUDIT,
    ObjectiveStatus.GOVERNANCE_DECISION,
}
_LOCKED_STATES = _ACTIVE_STATES  # escrow is locked across the active span


def _as_decimal(value: str | None) -> Decimal:
    try:
        return Decimal(value or "0")
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _treasury_balance(session: Session, workspace_id: str) -> str:
    treasury = workspace_service.get_treasury(session, workspace_id)
    if not treasury or not treasury.provider_wallet_id:
        return "0"
    try:
        provider = get_settlement_provider()
        bal = provider.get_balance(
            WalletRef(
                provider_wallet_id=treasury.provider_wallet_id,
                address=treasury.address or "",
                blockchain=treasury.blockchain or "",
            )
        )
        return str(bal)
    except Exception as exc:  # noqa: BLE001 — balance read is best-effort
        logger.warning("Treasury balance read failed: %s", exc)
        return "0"


@router.get("/current", response_model=WorkspaceOut)
def get_current_workspace(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkspaceOut:
    """The caller's workspace with onboarding + treasury state. The web app
    reads this as the source of truth for first-run routing."""
    workspace = workspace_service.get_or_create_default_workspace(session, user)
    treasury = workspace_service.get_treasury(session, workspace.id)
    session.commit()
    return _workspace_out(workspace, treasury)


@router.patch("/current", response_model=WorkspaceOut)
def update_current_workspace(
    body: WorkspaceUpdateIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkspaceOut:
    """Onboarding Workspace Initialization — name the operational environment
    and set governance defaults. Replaces the auto-derived "X's Workspace"."""
    workspace = workspace_service.get_or_create_default_workspace(session, user)

    if body.name is not None and body.name.strip():
        workspace.name = body.name.strip()
    if body.org_name is not None:
        workspace.org_name = body.org_name.strip() or None
    if body.operational_type is not None:
        workspace.operational_type = body.operational_type.strip() or None
    if body.governance_require_auditor is not None:
        workspace.governance_require_auditor = body.governance_require_auditor
    if body.governance_human_authoritative is not None:
        workspace.governance_human_authoritative = body.governance_human_authoritative

    session.add(workspace)
    treasury = workspace_service.get_treasury(session, workspace.id)
    session.commit()
    session.refresh(workspace)
    return _workspace_out(workspace, treasury)


@router.post("/current/activate", response_model=WorkspaceOut)
def activate_current_workspace(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> WorkspaceOut:
    """Treasury activation — the gate that opens Mission Control. Idempotent:
    flips ``onboarding_completed`` true once the operator confirms the treasury
    is ready (funding is optional and can happen later)."""
    workspace = workspace_service.get_or_create_default_workspace(session, user)
    workspace.onboarding_completed = True
    session.add(workspace)
    treasury = workspace_service.get_treasury(session, workspace.id)
    session.commit()
    session.refresh(workspace)
    return _workspace_out(workspace, treasury)


@router.get("/current/overview", response_model=OverviewOut)
def overview(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> OverviewOut:
    workspace: Workspace = workspace_service.get_or_create_default_workspace(
        session, user
    )

    objectives = session.exec(
        select(Objective)
        .where(Objective.workspace_id == workspace.id)
        .order_by(Objective.created_at.desc())
    ).all()

    status_counts: dict[str, int] = {}
    locked_total = Decimal("0")
    for o in objectives:
        status_counts[o.status.value] = status_counts.get(o.status.value, 0) + 1
        if o.status in _LOCKED_STATES:
            try:
                locked_total += Decimal(o.escrow_amount_usdc or "0")
            except Exception:  # noqa: BLE001
                pass

    active_count = sum(status_counts.get(s.value, 0) for s in _ACTIVE_STATES)
    treasury_balance = _treasury_balance(session, workspace.id)

    obj_ids = [o.id for o in objectives]
    recent_events: list[GovernanceEvent] = []
    settlements: list[Settlement] = []
    if obj_ids:
        recent_events = session.exec(
            select(GovernanceEvent)
            .where(GovernanceEvent.objective_id.in_(obj_ids))
            .order_by(GovernanceEvent.created_at.desc())
            .limit(12)
        ).all()
        settlements = session.exec(
            select(Settlement).where(Settlement.objective_id.in_(obj_ids))
        ).all()

    # Realized settlement economics: net value released to counterparties, the
    # governed fees Brewing retained, and value slashed back to treasuries.
    settled_value = Decimal("0")
    fees_collected = Decimal("0")
    settled_count = 0
    for st in settlements:
        if st.status == SettlementStatus.SETTLED:
            settled_count += 1
            settled_value += _as_decimal(st.amount_usdc)
            fees_collected += _as_decimal(st.fee_usdc)

    metrics = [
        OverviewMetric(
            label="Active objectives",
            value=str(active_count),
            hint="In-flight coordination",
        ),
        OverviewMetric(
            label="Escrow locked",
            value=f"{locked_total} USDC",
            hint="Across active objectives",
        ),
        OverviewMetric(
            label="Treasury balance",
            value=f"{treasury_balance} USDC",
            hint="Live from settlement provider",
        ),
        OverviewMetric(
            label="Value settled",
            value=f"{settled_value} USDC",
            hint=(
                f"{settled_count} settled · {fees_collected} USDC fees"
                if settled_count
                else "Net released to counterparties"
            ),
        ),
    ]

    return OverviewOut(
        metrics=metrics,
        status_counts=status_counts,
        treasury_balance_usdc=treasury_balance,
        objectives=[_objective_out(o) for o in objectives[:10]],
        recent_events=[_event_out(e) for e in recent_events],
    )
