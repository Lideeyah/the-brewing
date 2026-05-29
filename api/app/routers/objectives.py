"""Objective lifecycle routes.

The objective is the unit of coordination. These routes cover the first edges
of the lifecycle — Intent (create) and Governance (Copilot structuring) — and
expose the append-only governance timeline that powers observability.
Authorization is enforced API-side: an objective is only ever reachable through
the caller's own workspace.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.domain import copilot
from app.domain.governance import log_event
from app.domain.settlement import get_settlement_provider
from app.domain.settlement.circle_provider import SettlementConfigError
from app.domain.settlement.provider import EscrowRef, WalletRef
from app.models import (
    AuditReview,
    AuditStatus,
    EscrowState,
    EscrowStatus,
    ExecutionRun,
    ExecutionStep,
    GovernanceEvent,
    Objective,
    ObjectiveStatus,
    RunStatus,
    Settlement,
    SettlementStatus,
    StepStatus,
    User,
    Workspace,
)
from app.schemas import (
    AuditDecision,
    AuditReviewOut,
    EscrowOut,
    ExecutionRunOut,
    ExecutionStepOut,
    GovernanceEventOut,
    ObjectiveCreate,
    ObjectiveDetailOut,
    ObjectiveOut,
    SettlementOut,
)

# Governed platform settlement fee (frozen product decision).
SETTLEMENT_FEE_RATE = Decimal("0.025")
# USDC has 6 decimal places on-chain.
_USDC_QUANT = Decimal("0.000001")
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


@router.post("/{objective_id}/escrow/lock", response_model=ObjectiveDetailOut)
def lock_objective_escrow(
    objective_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    obj = _get_owned_objective(session, workspace, objective_id)

    if obj.status != ObjectiveStatus.COPILOT_STRUCTURED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Objective must be structured by the Copilot before escrow can be locked.",
        )
    try:
        amount = Decimal(obj.escrow_amount_usdc or "0")
    except InvalidOperation:
        amount = Decimal("0")
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Objective has no escrow amount to lock.",
        )

    treasury = workspace_service.get_treasury(session, workspace.id)
    if not treasury or not treasury.provider_wallet_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace treasury is not provisioned.",
        )

    treasury_ref = WalletRef(
        provider_wallet_id=treasury.provider_wallet_id,
        address=treasury.address or "",
        blockchain=treasury.blockchain or "",
    )

    try:
        provider = get_settlement_provider()
        balance = provider.get_balance(treasury_ref)
        if balance < amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "insufficient_treasury_balance",
                    "required_usdc": str(amount),
                    "balance_usdc": str(balance),
                    "treasury_address": treasury.address,
                    "message": (
                        f"Treasury holds {balance} USDC but {amount} USDC is required. "
                        "Fund the treasury with test USDC on Solana devnet via "
                        "https://faucet.circle.com, then lock again."
                    ),
                },
            )
        escrow_ref = provider.lock_escrow(treasury_ref, amount, obj.id)
    except SettlementConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    escrow = EscrowState(
        objective_id=obj.id,
        status=EscrowStatus.LOCKED,
        amount_usdc=str(amount),
        provider="circle",
        provider_escrow_id=escrow_ref.provider_escrow_id,
        address=escrow_ref.address,
        lock_tx_ref=escrow_ref.lock_tx_ref,
    )
    session.add(escrow)

    obj.status = ObjectiveStatus.ESCROW_LOCKED
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)

    log_event(
        session,
        objective_id=obj.id,
        kind="escrow.locked",
        message=f"Locked {amount} USDC from treasury into objective escrow.",
        actor=user.id,
        data={
            "amount_usdc": str(amount),
            "escrow_address": escrow_ref.address,
            "lock_tx_ref": escrow_ref.lock_tx_ref,
        },
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.post("/{objective_id}/execute", response_model=ObjectiveDetailOut)
def execute_objective(
    objective_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Execution orchestration.

    Brewing coordinates execution against the Copilot's orchestration plan; it
    does not run agents itself. Each plan step is materialized as a coordinated
    unit of work whose result is recorded on the run, producing an auditable
    execution record. Advances the objective into validation (UNDER_AUDIT).
    """
    obj = _get_owned_objective(session, workspace, objective_id)

    if obj.status != ObjectiveStatus.ESCROW_LOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Escrow must be locked before execution can be orchestrated.",
        )

    plan_steps = obj.orchestration_plan.get("steps") or []
    if not plan_steps:
        plan_steps = [{"title": "Fulfill objective", "detail": obj.title}]

    now = datetime.now(timezone.utc)
    run = ExecutionRun(
        objective_id=obj.id,
        status=RunStatus.COMPLETED,
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()

    for i, step in enumerate(plan_steps):
        title = str(step.get("title") or f"Step {i + 1}") if isinstance(step, dict) else str(step)
        detail = step.get("detail") if isinstance(step, dict) else None
        session.add(
            ExecutionStep(
                run_id=run.id,
                index=i,
                title=title,
                status=StepStatus.COMPLETED,
                output=(
                    f"Coordinated and recorded: {detail}"
                    if detail
                    else "Coordinated and recorded by orchestration."
                ),
            )
        )

    obj.status = ObjectiveStatus.UNDER_AUDIT
    obj.updated_at = now
    session.add(obj)

    log_event(
        session,
        objective_id=obj.id,
        kind="execution.completed",
        message=f"Orchestrated {len(plan_steps)} execution step(s); objective ready for validation.",
        actor="orchestration-engine",
        data={"steps": len(plan_steps)},
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.post("/{objective_id}/audit", response_model=ObjectiveDetailOut)
def audit_objective(
    body: AuditDecision,
    objective_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Validation against the governance criteria.

    Records a governance decision (approve/reject) on the completed execution
    and advances the objective to GOVERNANCE_DECISION, where settlement (release
    or slash) is authorized.
    """
    obj = _get_owned_objective(session, workspace, objective_id)

    if obj.status != ObjectiveStatus.UNDER_AUDIT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Objective must complete execution before it can be validated.",
        )

    approved = body.decision.strip().lower() != "reject"
    criteria = obj.governance_config.get("validation_criteria") or []

    review = AuditReview(
        objective_id=obj.id,
        status=AuditStatus.APPROVED if approved else AuditStatus.FAILED,
        notes=body.notes
        or (
            "Execution satisfies the governance validation criteria."
            if approved
            else "Execution failed to satisfy the governance validation criteria."
        ),
        reviewer_id=user.id,
    )
    session.add(review)

    obj.status = ObjectiveStatus.GOVERNANCE_DECISION
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)

    log_event(
        session,
        objective_id=obj.id,
        kind="audit.approved" if approved else "audit.failed",
        message=(
            "Governance validated the execution against criteria; settlement authorized."
            if approved
            else "Governance rejected the execution; escrow will be slashed."
        ),
        actor=user.id,
        data={"approved": approved, "criteria_count": len(criteria)},
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.post("/{objective_id}/settle", response_model=ObjectiveDetailOut)
def settle_objective(
    objective_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Settlement.

    On governance approval, release the escrow (net of the 2.5% governed fee) to
    a payout wallet representing the execution counterparty. On rejection, slash
    the escrow back to the workspace treasury. Both are real on-chain USDC
    movements via the settlement provider.
    """
    obj = _get_owned_objective(session, workspace, objective_id)

    if obj.status != ObjectiveStatus.GOVERNANCE_DECISION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Objective must have a governance decision before settlement.",
        )

    escrow = session.exec(
        select(EscrowState)
        .where(EscrowState.objective_id == obj.id)
        .order_by(EscrowState.created_at.desc())
    ).first()
    if escrow is None or escrow.status != EscrowStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No locked escrow is available to settle.",
        )

    review = session.exec(
        select(AuditReview)
        .where(AuditReview.objective_id == obj.id)
        .order_by(AuditReview.created_at.desc())
    ).first()
    approved = review is not None and review.status == AuditStatus.APPROVED

    treasury = workspace_service.get_treasury(session, workspace.id)
    if not treasury or not treasury.provider_wallet_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace treasury is not provisioned.",
        )
    treasury_ref = WalletRef(
        provider_wallet_id=treasury.provider_wallet_id,
        address=treasury.address or "",
        blockchain=treasury.blockchain or "",
    )

    try:
        amount = Decimal(escrow.amount_usdc or "0")
    except InvalidOperation:
        amount = Decimal("0")

    try:
        provider = get_settlement_provider()
        if approved:
            fee = (amount * SETTLEMENT_FEE_RATE).quantize(_USDC_QUANT)
            net = (amount - fee).quantize(_USDC_QUANT)
            payout = provider.provision_treasury_wallet(f"payout-{obj.id}")
            release_ref = EscrowRef(
                provider_escrow_id=escrow.provider_escrow_id or "",
                address=escrow.address or "",
                amount=net,
            )
            transfer = provider.release_escrow(release_ref, payout)

            escrow.status = EscrowStatus.RELEASED
            escrow.settle_tx_ref = transfer.tx_ref
            session.add(escrow)
            session.add(
                Settlement(
                    objective_id=obj.id,
                    status=SettlementStatus.SETTLED,
                    amount_usdc=str(net),
                    fee_usdc=str(fee),
                    payout_tx_ref=transfer.tx_ref,
                )
            )
            obj.status = ObjectiveStatus.SETTLED
            log_event(
                session,
                objective_id=obj.id,
                kind="settlement.released",
                message=f"Released {net} USDC to counterparty (fee {fee} USDC retained).",
                actor=user.id,
                data={
                    "net_usdc": str(net),
                    "fee_usdc": str(fee),
                    "payout_address": payout.address,
                    "payout_tx_ref": transfer.tx_ref,
                },
            )
        else:
            transfer = provider.slash_escrow(
                EscrowRef(
                    provider_escrow_id=escrow.provider_escrow_id or "",
                    address=escrow.address or "",
                    amount=amount,
                ),
                treasury_ref,
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
                    payout_tx_ref=transfer.tx_ref,
                )
            )
            obj.status = ObjectiveStatus.SLASHED
            log_event(
                session,
                objective_id=obj.id,
                kind="escrow.slashed",
                message=f"Slashed {amount} USDC back to treasury after governance rejection.",
                actor=user.id,
                data={
                    "amount_usdc": str(amount),
                    "treasury_address": treasury.address,
                    "slash_tx_ref": transfer.tx_ref,
                },
            )
    except SettlementConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


def _escrow_out(escrow: EscrowState | None) -> EscrowOut | None:
    if escrow is None:
        return None
    # lock_tx_ref is Circle's transaction id (the on-chain signature is only
    # known after confirmation), so we link to the escrow *account* on the
    # explorer rather than fabricate a transaction URL.
    explorer = (
        f"https://explorer.solana.com/address/{escrow.address}?cluster=devnet"
        if escrow.address
        else None
    )
    return EscrowOut(
        id=escrow.id,
        status=escrow.status.value,
        amount_usdc=escrow.amount_usdc,
        address=escrow.address,
        provider_escrow_id=escrow.provider_escrow_id,
        lock_tx_ref=escrow.lock_tx_ref,
        explorer_url=explorer,
    )


def _execution_out(
    run: ExecutionRun | None, steps: list[ExecutionStep]
) -> ExecutionRunOut | None:
    if run is None:
        return None
    return ExecutionRunOut(
        id=run.id,
        status=run.status.value,
        started_at=run.started_at,
        completed_at=run.completed_at,
        steps=[
            ExecutionStepOut(
                id=s.id,
                index=s.index,
                title=s.title,
                status=s.status.value,
                output=s.output,
            )
            for s in sorted(steps, key=lambda s: s.index)
        ],
    )


def _audit_out(review: AuditReview | None) -> AuditReviewOut | None:
    if review is None:
        return None
    return AuditReviewOut(
        id=review.id,
        status=review.status.value,
        notes=review.notes,
        created_at=review.created_at,
    )


def _settlement_out(
    settlement: Settlement | None, payout_address: str | None
) -> SettlementOut | None:
    if settlement is None:
        return None
    explorer = (
        f"https://explorer.solana.com/address/{payout_address}?cluster=devnet"
        if payout_address
        else None
    )
    return SettlementOut(
        id=settlement.id,
        status=settlement.status.value,
        amount_usdc=settlement.amount_usdc,
        fee_usdc=settlement.fee_usdc,
        payout_address=payout_address,
        payout_tx_ref=settlement.payout_tx_ref,
        explorer_url=explorer,
    )


def _detail(session: Session, obj: Objective) -> ObjectiveDetailOut:
    events = session.exec(
        select(GovernanceEvent)
        .where(GovernanceEvent.objective_id == obj.id)
        .order_by(GovernanceEvent.created_at.asc())
    ).all()
    escrow = session.exec(
        select(EscrowState)
        .where(EscrowState.objective_id == obj.id)
        .order_by(EscrowState.created_at.desc())
    ).first()
    run = session.exec(
        select(ExecutionRun)
        .where(ExecutionRun.objective_id == obj.id)
        .order_by(ExecutionRun.created_at.desc())
    ).first()
    steps = (
        session.exec(
            select(ExecutionStep).where(ExecutionStep.run_id == run.id)
        ).all()
        if run
        else []
    )
    review = session.exec(
        select(AuditReview)
        .where(AuditReview.objective_id == obj.id)
        .order_by(AuditReview.created_at.desc())
    ).first()
    settlement = session.exec(
        select(Settlement)
        .where(Settlement.objective_id == obj.id)
        .order_by(Settlement.created_at.desc())
    ).first()
    # payout address is captured on the release event (not stored on Settlement).
    payout_address = next(
        (
            e.data.get("payout_address")
            for e in reversed(events)
            if e.kind == "settlement.released" and e.data.get("payout_address")
        ),
        None,
    )
    treasury = workspace_service.get_treasury(session, obj.workspace_id)
    base = _objective_out(obj)
    return ObjectiveDetailOut(
        **base.model_dump(),
        governance_config=obj.governance_config,
        sla_config=obj.sla_config,
        settlement_config=obj.settlement_config,
        orchestration_plan=obj.orchestration_plan,
        timeline=[_event_out(e) for e in events],
        escrow=_escrow_out(escrow),
        treasury_address=treasury.address if treasury else None,
        execution=_execution_out(run, list(steps)),
        audit=_audit_out(review),
        settlement=_settlement_out(settlement, payout_address),
    )
