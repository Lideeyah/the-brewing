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
    AuditReview,
    EscrowState,
    EscrowStatus,
    Feedback,
    Objective,
    ObjectiveStatus,
    RoleStatus,
    Settlement,
    SettlementStatus,
    User,
    WorkflowRole,
    Workspace,
)
from app.domain import registry, requester, validation
from app.domain.governance import log_event
from app.domain.settlement import get_settlement_provider
from app.domain.settlement.fees import quote_settlement_fee
from app.domain.settlement.provider import EscrowRef, WalletRef
from app.schemas import (
    AdminDisputeOut,
    AdminDisputeResolveIn,
    AdminDisputeResolveOut,
    AdminOverviewOut,
    AdminRecentObjective,
    AdminRecentSettlement,
    FeedbackOut,
    FeeWithdrawIn,
    FeeWithdrawOut,
)

_USDC_QUANT = Decimal("0.000001")

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


# --- Dispute arbitration ----------------------------------------------------
# The arbiter is a network identity DISTINCT from the requester. This is the
# whole point of routing a rejection of validator-passed work to a held dispute
# rather than a unilateral slash: the party that rejected the work cannot also be
# the one who reclaims (or frees) the capital. The admin console — gated by the
# shared secret, no product login — is that neutral arbiter surface.


@router.get("/disputes", response_model=list[AdminDisputeOut])
def list_disputes(
    _: bool = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[AdminDisputeOut]:
    objectives = session.exec(
        select(Objective)
        .where(Objective.status == ObjectiveStatus.DISPUTED)
        .order_by(Objective.updated_at.desc())
    ).all()
    ws_by_id = {w.id: w for w in session.exec(select(Workspace)).all()}
    out: list[AdminDisputeOut] = []
    for obj in objectives:
        escrow = session.exec(
            select(EscrowState)
            .where(EscrowState.objective_id == obj.id)
            .order_by(EscrowState.created_at.desc())
        ).first()
        val = validation.latest_record(session, obj.id)
        review = session.exec(
            select(AuditReview)
            .where(AuditReview.objective_id == obj.id)
            .order_by(AuditReview.created_at.desc())
        ).first()
        ws = ws_by_id.get(obj.workspace_id)
        out.append(
            AdminDisputeOut(
                objective_id=obj.id,
                title=obj.title,
                workspace=ws.name if ws else None,
                workspace_id=obj.workspace_id,
                held_usdc=(escrow.amount_usdc if escrow else None) or "0",
                validator_recommendation=val.recommendation if val else None,
                validator_confidence=val.confidence if val else None,
                reviewer_rationale=review.notes if review else None,
                requester_reputation_score=ws.requester_reputation_score if ws else None,
                disputes_raised=ws.disputes_raised if ws else 0,
                disputes_lost=ws.disputes_lost if ws else 0,
                created_at=obj.updated_at,
            )
        )
    return out


@router.post("/disputes/{objective_id}/resolve", response_model=AdminDisputeResolveOut)
def resolve_dispute(
    objective_id: str,
    body: AdminDisputeResolveIn,
    _: bool = Depends(require_admin),
    session: Session = Depends(get_session),
) -> AdminDisputeResolveOut:
    """Arbiter-authoritative resolution of a held dispute.

    ``release`` pays the executor (the independent validator was right; the
    rejection was bad faith). ``uphold_rejection`` slashes the held escrow to the
    neutral pool (the rejection stands) — it is never refunded to the requester,
    so even a legitimate rejection cannot be used to take the result for free.
    """
    resolution = (body.resolution or "").strip().lower()
    if resolution not in ("release", "uphold_rejection"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="resolution must be 'release' or 'uphold_rejection'.",
        )

    obj = session.get(Objective, objective_id)
    if obj is None or obj.status != ObjectiveStatus.DISPUTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Objective is not in a disputed state.",
        )
    escrow = session.exec(
        select(EscrowState)
        .where(EscrowState.objective_id == obj.id)
        .order_by(EscrowState.created_at.desc())
    ).first()
    if escrow is None or escrow.status != EscrowStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No held escrow is available to resolve.",
        )
    try:
        amount = Decimal(escrow.amount_usdc or "0").quantize(_USDC_QUANT)
    except (InvalidOperation, TypeError):
        amount = Decimal("0")

    s = get_settings()
    provider = get_settlement_provider()
    now = datetime.now(timezone.utc)
    rationale = (body.rationale or "").strip()

    if resolution == "release":
        # The validator was upheld: pay the executor, net of the standard fee.
        quote = quote_settlement_fee(amount)
        fee = quote.fee_usdc
        net = (amount - fee).quantize(_USDC_QUANT)
        payout = _resolve_dispute_payout(provider, session, obj)
        transfer = provider.release_escrow(
            EscrowRef(
                provider_escrow_id=escrow.provider_escrow_id or "",
                address=escrow.address or "",
                amount=net,
            ),
            payout,
        )
        escrow.status = EscrowStatus.RELEASED
        escrow.settle_tx_ref = transfer.tx_ref
        session.add(escrow)
        session.add(
            Settlement(
                objective_id=obj.id,
                status=SettlementStatus.SETTLED,
                amount_usdc=str(net),
                fee_usdc=str(fee),
                fee_basis=f"dispute released by arbiter — {quote.basis}",
                payout_tx_ref=transfer.tx_ref,
            )
        )
        if s.platform_fee_wallet_address and fee > 0:
            try:
                provider.collect_fee(
                    EscrowRef(
                        provider_escrow_id=escrow.provider_escrow_id or "",
                        address=escrow.address or "",
                        amount=fee,
                    ),
                    s.platform_fee_wallet_address,
                    fee,
                )
            except Exception:  # noqa: BLE001 — fee sweep is non-blocking
                pass
        obj.status = ObjectiveStatus.SETTLED
        for role in session.exec(
            select(WorkflowRole).where(WorkflowRole.objective_id == obj.id)
        ).all():
            if role.settlement_status in ("disputed", "pending"):
                role.validation_status = "passed"
                role.settlement_status = "settled"
                role.outcome = role.outcome or "released"
                role.status = RoleStatus.COMPLETED
                role.updated_at = now
                session.add(role)
        # Rejection was overturned — bad faith on the requester's record.
        ws = requester.record_outcome(session, obj.workspace_id, requester.DISPUTE_LOST)
        explorer = transfer.explorer_url
        log_event(
            session,
            objective_id=obj.id,
            kind="dispute.resolved.released",
            message=(
                f"Arbiter released {net} USDC to the executor: the independent "
                "validator passed the work, so the rejection was overturned."
                + (f" Rationale: {rationale}" if rationale else "")
            ),
            actor="arbiter",
            data={"net_usdc": str(net), "fee_usdc": str(fee)},
        )
        result_amount = net
        outcome_status = ObjectiveStatus.SETTLED.value
    else:
        # The rejection stands: slash to the neutral pool, never the requester.
        pool_addr = (
            s.slash_pool_wallet_address or s.platform_fee_wallet_address or ""
        ).strip()
        slash_dest = (
            WalletRef(
                provider_wallet_id="",
                address=pool_addr,
                blockchain=s.circle_blockchain,
            )
            if pool_addr
            else _resolve_dispute_payout(provider, session, obj)
        )
        transfer = provider.slash_escrow(
            EscrowRef(
                provider_escrow_id=escrow.provider_escrow_id or "",
                address=escrow.address or "",
                amount=amount,
            ),
            slash_dest,
        )
        escrow.status = EscrowStatus.SLASHED
        escrow.settle_tx_ref = transfer.tx_ref
        session.add(escrow)
        session.add(
            Settlement(
                objective_id=obj.id,
                status=SettlementStatus.SLASHED,
                amount_usdc=str(amount),
                fee_usdc="0",
                fee_basis="dispute upheld by arbiter — slashed to neutral pool",
                payout_tx_ref=transfer.tx_ref,
            )
        )
        obj.status = ObjectiveStatus.SLASHED
        for role in session.exec(
            select(WorkflowRole).where(WorkflowRole.objective_id == obj.id)
        ).all():
            if role.settlement_status in ("disputed", "pending"):
                role.validation_status = "failed"
                role.settlement_status = "slashed"
                role.outcome = role.outcome or "slashed"
                role.updated_at = now
                session.add(role)
        # Rejection upheld — a legitimate dispute, no bad-faith penalty.
        ws = requester.record_outcome(session, obj.workspace_id, requester.DISPUTE_UPHELD)
        explorer = transfer.explorer_url
        log_event(
            session,
            objective_id=obj.id,
            kind="dispute.resolved.slashed",
            message=(
                f"Arbiter upheld the rejection: {amount} USDC slashed to the "
                "neutral pool (not refunded to the requester)."
                + (f" Rationale: {rationale}" if rationale else "")
            ),
            actor="arbiter",
            data={"slashed_usdc": str(amount), "to_pool": bool(pool_addr)},
        )
        result_amount = amount
        outcome_status = ObjectiveStatus.SLASHED.value

    obj.updated_at = now
    session.add(obj)
    session.commit()
    return AdminDisputeResolveOut(
        ok=True,
        objective_id=obj.id,
        resolution=resolution,
        outcome_status=outcome_status,
        amount_usdc=str(result_amount),
        explorer_url=explorer,
        requester_reputation_score=ws.requester_reputation_score if ws else None,
    )


def _resolve_dispute_payout(provider, session: Session, obj: Objective) -> WalletRef:
    """Where a dispute release lands — the executor's verified payout address if
    one exists, otherwise a freshly provisioned provider wallet."""
    if obj.agent_id:
        agent = session.get(AgentIdentity, obj.agent_id)
        address = registry.resolve_verified_payout_address(agent)
        if address:
            return WalletRef(
                provider_wallet_id="",
                address=address,
                blockchain=(agent.payout_blockchain if agent else "") or "",
            )
    return provider.provision_treasury_wallet(f"dispute-payout-{obj.id}")
