"""Operator admin console — platform-wide metrics, revenue, and feedback.

A *separate* surface from the product: no product login is involved. Gated by a
shared secret (X-Admin-Secret) so the standalone admin app — not workspace users
— is the only caller. Read-only view across all workspaces.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session, select

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
from app.domain.settlement import get_settlement_provider
from app.domain.settlement.provider import WalletRef
from app.schemas import (
    AdminOverviewOut,
    AdminRecentObjective,
    AdminRecentSettlement,
    FeedbackOut,
    FeeWithdrawIn,
    FeeWithdrawOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(x_admin_secret: str | None = Header(default=None)) -> bool:
    """Gate admin endpoints by a shared secret — no product login involved."""
    secret = get_settings().admin_secret
    if not secret or x_admin_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required."
        )
    return True


def _dec(value: str | None) -> Decimal:
    try:
        return Decimal(value or "0")
    except (InvalidOperation, TypeError):
        return Decimal("0")


@router.get("/overview", response_model=AdminOverviewOut)
def admin_overview(
    _: bool = Depends(require_admin),
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

    # Live balance of the platform revenue wallet (best-effort).
    s = get_settings()
    fee_address = s.platform_fee_wallet_address or None
    fee_balance: str | None = None
    if fee_address and s.platform_fee_wallet_id:
        try:
            fee_balance = str(
                get_settlement_provider().get_balance(
                    WalletRef(
                        provider_wallet_id=s.platform_fee_wallet_id,
                        address=fee_address,
                        blockchain=s.circle_blockchain,
                    )
                )
            )
        except Exception:  # noqa: BLE001 — balance read is best-effort
            fee_balance = None

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
                objective_id=st.objective_id,
                status=st.status.value if hasattr(st.status, "value") else str(st.status),
                amount_usdc=st.amount_usdc,
                fee_usdc=st.fee_usdc,
                created_at=st.created_at,
            )
            for st in recent_setts
        ],
        platform_fee_wallet_address=fee_address,
        platform_fee_balance_usdc=fee_balance,
    )


@router.get("/feedback", response_model=list[FeedbackOut])
def admin_feedback(
    _: bool = Depends(require_admin),
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


@router.post("/fee-wallet/withdraw", response_model=FeeWithdrawOut)
def withdraw_fees(
    body: FeeWithdrawIn,
    _: bool = Depends(require_admin),
) -> FeeWithdrawOut:
    """Withdraw USDC from the platform revenue wallet to an external address."""
    s = get_settings()
    if not (s.platform_fee_wallet_address and s.platform_fee_wallet_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform fee wallet is not configured.",
        )
    dest = (body.destination_address or "").strip()
    if not dest:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Destination address is required.",
        )
    provider = get_settlement_provider()
    src = WalletRef(
        provider_wallet_id=s.platform_fee_wallet_id,
        address=s.platform_fee_wallet_address,
        blockchain=s.circle_blockchain,
    )
    if body.amount_usdc and body.amount_usdc.strip():
        try:
            amount = Decimal(body.amount_usdc.strip())
        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid amount.",
            )
    else:
        amount = provider.get_balance(src)
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to withdraw."
        )
    try:
        result = provider.withdraw(src, dest, amount)
    except Exception as exc:  # noqa: BLE001 — surface the provider error to the admin
        return FeeWithdrawOut(
            ok=False, amount_usdc=str(amount), destination_address=dest, message=str(exc)[:200]
        )
    return FeeWithdrawOut(
        ok=True,
        amount_usdc=str(amount),
        destination_address=dest,
        explorer_url=result.explorer_url,
    )
