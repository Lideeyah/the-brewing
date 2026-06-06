"""Operator admin console — platform-wide metrics, revenue, and feedback.

Read-only and gated to the configured admin emails. This is the operator's view
*across all workspaces*, distinct from a workspace's own Mission Control.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import (
    AgentIdentity,
    Feedback,
    Objective,
    Settlement,
    SettlementStatus,
    User,
    Workspace,
)
from app.schemas import (
    AdminOverviewOut,
    AdminRecentObjective,
    AdminRecentSettlement,
    FeedbackOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.email.lower() not in get_settings().admin_email_set:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required."
        )
    return user


def _dec(value: str | None) -> Decimal:
    try:
        return Decimal(value or "0")
    except (InvalidOperation, TypeError):
        return Decimal("0")


@router.get("/overview", response_model=AdminOverviewOut)
def admin_overview(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AdminOverviewOut:
    users = list(session.exec(select(User)).all())
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    new_30d = sum(
        1 for u in users if (u.created_at and u.created_at.replace(tzinfo=u.created_at.tzinfo or timezone.utc) >= cutoff)
    )

    objectives = list(session.exec(select(Objective)).all())
    by_status: dict[str, int] = {}
    for o in objectives:
        key = o.status.value if hasattr(o.status, "value") else str(o.status)
        by_status[key] = by_status.get(key, 0) + 1

    settlements = list(session.exec(select(Settlement)).all())
    settled = [s for s in settlements if s.status == SettlementStatus.SETTLED]
    settled_total = sum((_dec(s.amount_usdc) for s in settled), Decimal("0"))
    fees_total = sum((_dec(s.fee_usdc) for s in settlements), Decimal("0"))

    ws_by_id = {w.id: w.name for w in session.exec(select(Workspace)).all()}

    recent_objs = sorted(objectives, key=lambda o: o.created_at, reverse=True)[:8]
    recent_setts = sorted(settlements, key=lambda s: s.created_at, reverse=True)[:8]

    return AdminOverviewOut(
        users_total=len(users),
        users_new_30d=new_30d,
        workspaces_total=len(ws_by_id),
        objectives_total=len(objectives),
        objectives_by_status=by_status,
        agents_total=len(list(session.exec(select(AgentIdentity)).all())),
        settled_usdc_total=str(settled_total),
        fees_usdc_total=str(fees_total),
        settlements_count=len(settled),
        recent_objectives=[
            AdminRecentObjective(
                id=o.id,
                title=o.title,
                status=o.status.value if hasattr(o.status, "value") else str(o.status),
                workspace=ws_by_id.get(o.workspace_id),
                created_at=o.created_at,
            )
            for o in recent_objs
        ],
        recent_settlements=[
            AdminRecentSettlement(
                objective_id=s.objective_id,
                status=s.status.value if hasattr(s.status, "value") else str(s.status),
                amount_usdc=s.amount_usdc,
                fee_usdc=s.fee_usdc,
                created_at=s.created_at,
            )
            for s in recent_setts
        ],
    )


@router.get("/feedback", response_model=list[FeedbackOut])
def admin_feedback(
    _: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[FeedbackOut]:
    rows = session.exec(
        select(Feedback).order_by(Feedback.created_at.desc())
    ).all()
    return [
        FeedbackOut(
            id=f.id,
            email=f.email,
            name=f.name,
            category=f.category,
            message=f.message,
            status=f.status,
            created_at=f.created_at,
        )
        for f in rows
    ]
