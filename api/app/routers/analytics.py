"""KPI analytics — the operator's read model for governed settlement health.

Computes the board-level metrics that describe Brewing's coordination network
live from the lifecycle tables (no warehouse, no stored aggregates):

  - Governed Transaction Volume — gross USDC that passed through governed
    settlement (net released + fees retained + value slashed).
  - Mean Time to Settlement — average wall-clock from escrow lock to settlement.
  - Attestation Discrepancy Rate — share of audits where the human overrode the
    AI attestation.
  - Active Escrow Accounts — escrow states currently locked.
  - Take-Rate Drag — governed fees as a share of governed volume (the effective
    take rate dragging on settled value).

All metrics are workspace-scoped to the caller's default workspace.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import (
    AuditReview,
    EscrowState,
    EscrowStatus,
    Objective,
    Settlement,
    SettlementStatus,
    User,
    Workspace,
)
from app.schemas import KpiMetric, KpiOut
from app.services import workspace as workspace_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _as_decimal(value: str | None) -> Decimal:
    try:
        return Decimal(value or "0")
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _humanize_seconds(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


@router.get("/kpis", response_model=KpiOut)
def kpis(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> KpiOut:
    workspace: Workspace = workspace_service.get_or_create_default_workspace(
        session, user
    )

    obj_rows = session.exec(
        select(Objective.id, Objective.created_at).where(
            Objective.workspace_id == workspace.id
        )
    ).all()
    obj_ids = [row[0] for row in obj_rows]
    obj_created_at: dict[str, datetime] = {row[0]: row[1] for row in obj_rows}

    settlements: list[Settlement] = []
    escrows: list[EscrowState] = []
    audits: list[AuditReview] = []
    if obj_ids:
        settlements = session.exec(
            select(Settlement).where(Settlement.objective_id.in_(obj_ids))
        ).all()
        escrows = session.exec(
            select(EscrowState).where(EscrowState.objective_id.in_(obj_ids))
        ).all()
        audits = session.exec(
            select(AuditReview).where(AuditReview.objective_id.in_(obj_ids))
        ).all()

    # Earliest escrow lock time per objective — the clock start for settlement.
    lock_at: dict[str, datetime] = {}
    for e in escrows:
        existing = lock_at.get(e.objective_id)
        if existing is None or e.created_at < existing:
            lock_at[e.objective_id] = e.created_at

    # --- Governed Transaction Volume + Take-Rate Drag ----------------------
    settled_net = Decimal("0")
    fees_collected = Decimal("0")
    slashed_value = Decimal("0")
    settled_count = 0
    slashed_count = 0
    durations: list[float] = []
    for st in settlements:
        if st.status == SettlementStatus.SETTLED:
            settled_count += 1
            settled_net += _as_decimal(st.amount_usdc)
            fees_collected += _as_decimal(st.fee_usdc)
        elif st.status == SettlementStatus.SLASHED:
            slashed_count += 1
            slashed_value += _as_decimal(st.amount_usdc)

        # Mean Time to Settlement: prefer escrow-lock start, fall back to
        # objective creation if no escrow record exists.
        start = lock_at.get(st.objective_id) or obj_created_at.get(st.objective_id)
        if start is not None and st.created_at is not None:
            delta = (st.created_at - start).total_seconds()
            if delta >= 0:
                durations.append(delta)

    governed_volume = settled_net + fees_collected + slashed_value
    take_rate_drag = (
        float(fees_collected / governed_volume) if governed_volume > 0 else 0.0
    )

    # --- Mean Time to Settlement -------------------------------------------
    mtts_seconds = sum(durations) / len(durations) if durations else None

    # --- Attestation Discrepancy Rate --------------------------------------
    # Only audits that recorded an AI recommendation are eligible — those are
    # the ones where a human attestation could diverge from the AI one.
    eligible_audits = [a for a in audits if a.recommendation is not None]
    overridden = sum(1 for a in eligible_audits if a.overridden)
    attestation_discrepancy_rate = (
        overridden / len(eligible_audits) if eligible_audits else 0.0
    )

    # --- Active Escrow Accounts --------------------------------------------
    active_escrows = sum(1 for e in escrows if e.status == EscrowStatus.LOCKED)

    metrics = [
        KpiMetric(
            key="governed_transaction_volume",
            label="Governed Transaction Volume",
            value=f"{governed_volume} USDC",
            hint="Net released + fees + slashed across governed settlements",
            raw=float(governed_volume),
        ),
        KpiMetric(
            key="mean_time_to_settlement",
            label="Mean Time to Settlement",
            value=_humanize_seconds(mtts_seconds) or "—",
            hint=(
                f"Avg over {len(durations)} settlement(s), escrow lock → settle"
                if durations
                else "No settlements yet"
            ),
            raw=mtts_seconds,
        ),
        KpiMetric(
            key="attestation_discrepancy_rate",
            label="Attestation Discrepancy Rate",
            value=f"{attestation_discrepancy_rate * 100:.1f}%",
            hint=(
                f"{overridden} of {len(eligible_audits)} audits overrode the AI attestation"
                if eligible_audits
                else "No attested audits yet"
            ),
            raw=attestation_discrepancy_rate,
        ),
        KpiMetric(
            key="active_escrow_accounts",
            label="Active Escrow Accounts",
            value=str(active_escrows),
            hint="Escrow states currently locked",
            raw=float(active_escrows),
        ),
        KpiMetric(
            key="take_rate_drag",
            label="Take-Rate Drag",
            value=f"{take_rate_drag * 100:.3f}%",
            hint=f"{fees_collected} USDC fees on {governed_volume} USDC volume",
            raw=take_rate_drag,
        ),
    ]

    return KpiOut(
        generated_at=datetime.now(timezone.utc),
        window="all-time",
        governed_transaction_volume_usdc=str(governed_volume),
        mean_time_to_settlement_seconds=mtts_seconds,
        mean_time_to_settlement_human=_humanize_seconds(mtts_seconds),
        attestation_discrepancy_rate=attestation_discrepancy_rate,
        active_escrow_accounts=active_escrows,
        take_rate_drag=take_rate_drag,
        settled_count=settled_count,
        slashed_count=slashed_count,
        total_settlements=len(settlements),
        fees_collected_usdc=str(fees_collected),
        metrics=metrics,
    )
