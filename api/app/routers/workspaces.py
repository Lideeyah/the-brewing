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
from app.models import GovernanceEvent, Objective, ObjectiveStatus, User, Workspace
from app.routers.objectives import _event_out, _objective_out
from app.schemas import OverviewMetric, OverviewOut
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
    settled_count = 0
    for o in objectives:
        status_counts[o.status.value] = status_counts.get(o.status.value, 0) + 1
        if o.status in _LOCKED_STATES:
            try:
                locked_total += Decimal(o.escrow_amount_usdc or "0")
            except Exception:  # noqa: BLE001
                pass
        if o.status == ObjectiveStatus.SETTLED:
            settled_count += 1

    active_count = sum(status_counts.get(s.value, 0) for s in _ACTIVE_STATES)
    treasury_balance = _treasury_balance(session, workspace.id)

    obj_ids = [o.id for o in objectives]
    recent_events: list[GovernanceEvent] = []
    if obj_ids:
        recent_events = session.exec(
            select(GovernanceEvent)
            .where(GovernanceEvent.objective_id.in_(obj_ids))
            .order_by(GovernanceEvent.created_at.desc())
            .limit(12)
        ).all()

    metrics = [
        OverviewMetric(label="Active objectives", value=str(active_count)),
        OverviewMetric(
            label="Escrow locked", value=f"{locked_total} USDC", hint="Across active objectives"
        ),
        OverviewMetric(
            label="Treasury balance", value=f"{treasury_balance} USDC", hint="Live from settlement provider"
        ),
        OverviewMetric(label="Settled", value=str(settled_count)),
    ]

    return OverviewOut(
        metrics=metrics,
        status_counts=status_counts,
        treasury_balance_usdc=treasury_balance,
        objectives=[_objective_out(o) for o in objectives[:10]],
        recent_events=[_event_out(e) for e in recent_events],
    )
