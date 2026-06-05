"""Objective lifecycle routes.

The objective is the unit of coordination. These routes cover the first edges
of the lifecycle — Intent (create) and Governance (Copilot structuring) — and
expose the append-only governance timeline that powers observability.
Authorization is enforced API-side: an objective is only ever reachable through
the caller's own workspace.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.domain import copilot, oracle, registry, validation
from app.domain import workflow as workflow_domain
from app.domain.governance import log_event
from app.domain.settlement import get_settlement_provider
from app.domain.settlement.provider import (
    EscrowRef,
    SettlementConfigError,
    WalletRef,
)
from app.models import (
    AgentIdentity,
    AuditReview,
    AuditStatus,
    EscrowState,
    EscrowStatus,
    ExecutionRun,
    ExecutionStep,
    GovernanceEvaluation,
    GovernanceEvent,
    Objective,
    ObjectiveStatus,
    RunStatus,
    Settlement,
    SettlementAuthorization,
    SettlementStatus,
    StepStatus,
    User,
    Workspace,
)
from app.schemas import (
    AssignAgentIn,
    AssignedAgentOut,
    AuditDecision,
    AuditReviewOut,
    CoordinationEdgeOut,
    CoordinationGraphOut,
    CoordinationNodeOut,
    CriterionBasisOut,
    CriterionResultOut,
    EscrowOut,
    EvidenceTrailItem,
    EvidenceTrailOut,
    EvidenceTrailStage,
    ExecutionRunOut,
    ExecutionStepOut,
    GovernanceEvaluationOut,
    GovernanceEventOut,
    GovernanceFinding,
    GovernanceRisk,
    AssignRoleIn,
    FeasibilityReport,
    FeasibilityRoleCheck,
    ObjectiveCreate,
    ObjectiveDetailOut,
    ObjectiveOut,
    OnChainLedger,
    SettlementAuthorizationOut,
    SettlementOut,
    WalletMovement,
    UpdateAllocationIn,
    ValidationFinding,
    ValidationRecordOut,
    ValidatorOut,
    WorkflowRoleOut,
)
from app.models import RoleStatus, Validator, ValidationRecord, WorkflowRole

# USDC has 6 decimal places on-chain.
_USDC_QUANT = Decimal("0.000001")
from app.domain.settlement.fees import quote_settlement_fee
from app.services import workspace as workspace_service

logger = logging.getLogger("brewing.objectives")

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
        agent_id=obj.agent_id,
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

    # Optional operator-set budget. Stored as the escrow amount so the Copilot
    # structures the workflow within it (see structure step); blank = let the
    # Copilot recommend one.
    escrow_amount = "0"
    if body.budget_usdc is not None and str(body.budget_usdc).strip():
        try:
            budget = Decimal(str(body.budget_usdc).strip()).quantize(Decimal("0.000001"))
        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Budget must be a valid USDC amount.",
            )
        if budget <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Budget must be greater than zero.",
            )
        escrow_amount = str(budget)

    obj = Objective(
        workspace_id=workspace.id,
        created_by=user.id,
        title=title,
        intent=intent,
        status=ObjectiveStatus.DRAFT,
        escrow_amount_usdc=escrow_amount,
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


@router.post("/{objective_id}/assign-agent", response_model=ObjectiveDetailOut)
def assign_agent(
    objective_id: str,
    body: AssignAgentIn,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Assign a registered agent identity as the objective's executor.

    The assignment is what lets the reputation feedback loop attribute a
    settlement outcome to an agent automatically at settle time.
    """
    obj = _get_owned_objective(session, workspace, objective_id)
    agent = session.get(AgentIdentity, body.agent_id)
    if agent is None or agent.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
    obj.agent_id = agent.id
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)
    log_event(
        session,
        objective_id=obj.id,
        kind="agent.assigned",
        message=f"Assigned agent {agent.name} ({agent.token_id}) as executor.",
        actor=user.id,
        data={"agent_id": agent.id, "token_id": agent.token_id},
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.post(
    "/{objective_id}/roles/{role_id}/assign", response_model=ObjectiveDetailOut
)
def assign_role(
    objective_id: str,
    role_id: str,
    body: AssignRoleIn,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Bind a registered agent to one workflow role.

    The feasibility engine's agent-pricing constraints are enforced here: an
    assignment that violates the agent's minimum role compensation, minimum
    objective value, or availability is refused so an infeasible workflow can
    never be locked.
    """
    obj = _get_owned_objective(session, workspace, objective_id)
    role = session.get(WorkflowRole, role_id)
    if role is None or role.objective_id != obj.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )
    agent = session.get(AgentIdentity, body.agent_id)
    if agent is None or agent.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )

    # Enforce the agent's pricing/availability constraints against this role.
    alloc = Decimal(role.allocation_usdc or "0")
    budget = Decimal(obj.escrow_amount_usdc or "0")
    issues: list[str] = []
    min_comp = Decimal(agent.min_role_compensation_usdc or "0")
    if min_comp > 0 and alloc < min_comp:
        issues.append(
            f"Role allocation {alloc} USDC is below {agent.name}'s minimum role "
            f"compensation of {min_comp} USDC."
        )
    min_obj = Decimal(agent.min_objective_value_usdc or "0")
    if min_obj > 0 and budget < min_obj:
        issues.append(
            f"Objective budget {budget} USDC is below {agent.name}'s minimum "
            f"objective value of {min_obj} USDC."
        )
    if agent.availability == "offline":
        issues.append(f"{agent.name} is offline and cannot be assigned.")
    if issues:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "constraint_violation", "issues": issues},
        )

    role.assigned_agent_id = agent.id
    role.status = RoleStatus.ASSIGNED
    role.updated_at = datetime.now(timezone.utc)
    session.add(role)
    log_event(
        session,
        objective_id=obj.id,
        kind="role.assigned",
        message=(
            f"Assigned {agent.name} to the {role.title} role "
            f"({role.allocation_usdc} USDC allocation)."
        ),
        actor=user.id,
        data={
            "role_id": role.id,
            "role_key": role.role_key,
            "agent_id": agent.id,
            "token_id": agent.token_id,
            "allocation_usdc": role.allocation_usdc,
        },
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.patch(
    "/{objective_id}/roles/{role_id}/allocation", response_model=ObjectiveDetailOut
)
def update_role_allocation(
    objective_id: str,
    role_id: str,
    body: UpdateAllocationIn,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Re-weight a role's settlement allocation.

    The Copilot proposes a budget-proportional split at structure time; this is
    the user-adjust path. The change is rejected if it pushes total allocations
    over budget, and recorded in the append-only allocation history. Locked once
    the objective has settled so a paid-out split can't be rewritten.
    """
    obj = _get_owned_objective(session, workspace, objective_id)
    if obj.status in (ObjectiveStatus.SETTLED, ObjectiveStatus.SLASHED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Allocations are locked once the objective has settled.",
        )
    role = session.get(WorkflowRole, role_id)
    if role is None or role.objective_id != obj.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )
    try:
        new_amount = Decimal(body.allocation_usdc)
    except InvalidOperation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Allocation must be a USDC decimal amount.",
        )
    try:
        previous = role.allocation_usdc
        workflow_domain.update_allocation(
            session, objective=obj, role=role, new_amount=new_amount, actor=user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    log_event(
        session,
        objective_id=obj.id,
        kind="role.reallocated",
        message=(
            f"Re-weighted the {role.title} role allocation "
            f"from {previous} to {role.allocation_usdc} USDC."
        ),
        actor=user.id,
        data={
            "role_id": role.id,
            "role_key": role.role_key,
            "from_usdc": previous,
            "to_usdc": role.allocation_usdc,
        },
    )
    session.commit()
    session.refresh(obj)
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
    # Honour an operator-set budget; only fall back to the Copilot's
    # recommendation when no explicit budget was provided at creation.
    try:
        operator_budget = Decimal(obj.escrow_amount_usdc or "0")
    except InvalidOperation:
        operator_budget = Decimal("0")
    if operator_budget <= 0:
        obj.escrow_amount_usdc = str(
            obj.settlement_config.get("recommended_escrow_usdc", obj.escrow_amount_usdc)
        )
    obj.status = ObjectiveStatus.COPILOT_STRUCTURED
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)
    session.flush()

    # Multi-agent workflow: decompose the objective into independently assignable
    # roles with budget-proportional settlement allocations. Re-generated on each
    # (re)structure since no role is assigned or settled yet at this stage.
    try:
        budget = Decimal(obj.escrow_amount_usdc or "0")
    except InvalidOperation:
        budget = Decimal("0")
    role_specs = workflow_domain.normalize_workflow(
        structured.get("workflow"), obj.intent, budget
    )
    roles = workflow_domain.replace_roles(session, obj.id, role_specs)

    log_event(
        session,
        objective_id=obj.id,
        kind="objective.structured",
        message=(
            "Coordination Copilot structured the objective into governance, SLA, "
            f"settlement terms, and a {len(roles)}-role workflow."
        ),
        actor="copilot",
        data={
            "source": structured.get("_source"),
            "roles": [r.role_key for r in roles],
        },
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


# Circle accepts a transfer immediately and returns an internal tx id; the
# on-chain signature (and the network's verdict) only appear once the transfer
# confirms. Classify a polled TransactionState into one of three outcomes so the
# escrow is only ever marked LOCKED after the chain confirms the funds moved.
_LOCK_CONFIRMED_STATES = {"CONFIRMED", "COMPLETE"}
_LOCK_FAILED_STATES = {"FAILED", "DENIED", "CANCELLED"}


def _await_lock_confirmation(
    lock_tx_ref: str | None,
    *,
    attempts: int = 8,
    delay_seconds: float = 2.5,
) -> tuple[str, str | None]:
    """Poll the settlement provider until the lock transfer resolves.

    Returns ``(outcome, tx_hash)`` where ``outcome`` is one of ``"confirmed"``,
    ``"failed"`` or ``"pending"``. Funds are only in custody on ``"confirmed"``;
    the caller must not mark the escrow LOCKED otherwise. Never raises — provider
    errors are treated as a still-pending result so the escrow stays PENDING and
    can be re-checked, rather than being falsely promoted to LOCKED.
    """
    if not lock_tx_ref:
        return "pending", None
    provider = get_settlement_provider()
    last_hash: str | None = None
    for attempt in range(attempts):
        try:
            proof = provider.get_transaction_proof(lock_tx_ref)
        except Exception:  # noqa: BLE001 — proof resolution is best-effort
            proof = None
        if proof is not None:
            state = (proof.state or "").upper()
            last_hash = proof.tx_hash or last_hash
            if state in _LOCK_CONFIRMED_STATES:
                return "confirmed", last_hash
            if state in _LOCK_FAILED_STATES:
                return "failed", last_hash
        if attempt < attempts - 1:
            time.sleep(delay_seconds)
    return "pending", last_hash


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

    # The transfer has been accepted by the provider but is not yet confirmed
    # on-chain. Record the escrow as PENDING — funds are not in custody, the
    # objective does NOT advance, and settlement is barred (it gates on LOCKED)
    # until the chain confirms the lock.
    escrow = EscrowState(
        objective_id=obj.id,
        status=EscrowStatus.PENDING,
        amount_usdc=str(amount),
        provider=provider.name,
        custody_model=provider.custody_model,
        provider_escrow_id=escrow_ref.provider_escrow_id,
        address=escrow_ref.address,
        lock_tx_ref=escrow_ref.lock_tx_ref,
    )
    session.add(escrow)
    log_event(
        session,
        objective_id=obj.id,
        kind="escrow.submitted",
        message=f"Submitted {amount} USDC lock transfer; awaiting on-chain confirmation.",
        actor=user.id,
        data={
            "amount_usdc": str(amount),
            "escrow_address": escrow_ref.address,
            "lock_tx_ref": escrow_ref.lock_tx_ref,
        },
    )
    session.commit()

    outcome, lock_tx_hash = _await_lock_confirmation(escrow_ref.lock_tx_ref)
    session.refresh(escrow)

    if outcome == "confirmed":
        escrow.status = EscrowStatus.LOCKED
        escrow.lock_tx_hash = lock_tx_hash
        escrow.updated_at = datetime.now(timezone.utc)
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
                "lock_tx_hash": lock_tx_hash,
            },
        )
        session.commit()
        session.refresh(obj)
        return _detail(session, obj)

    if outcome == "failed":
        # The chain rejected the transfer; no funds moved. Mark the escrow FAILED
        # and leave the objective at COPILOT_STRUCTURED so it can be re-locked.
        escrow.status = EscrowStatus.FAILED
        escrow.lock_tx_hash = lock_tx_hash
        escrow.updated_at = datetime.now(timezone.utc)
        session.add(escrow)
        log_event(
            session,
            objective_id=obj.id,
            kind="escrow.failed",
            message=f"Lock transfer of {amount} USDC failed on-chain; no funds escrowed.",
            actor=user.id,
            data={
                "amount_usdc": str(amount),
                "escrow_address": escrow_ref.address,
                "lock_tx_ref": escrow_ref.lock_tx_ref,
                "lock_tx_hash": lock_tx_hash,
            },
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "escrow_lock_failed",
                "amount_usdc": str(amount),
                "lock_tx_ref": escrow_ref.lock_tx_ref,
                "message": (
                    "The settlement provider rejected the lock transfer on-chain. "
                    "No funds were escrowed; the objective remains unfunded."
                ),
            },
        )

    # Still in-flight after the polling window. Leave the escrow PENDING and the
    # objective unadvanced. The lock can be re-confirmed on a later read; the
    # objective cannot proceed to execution or settlement until it does.
    log_event(
        session,
        objective_id=obj.id,
        kind="escrow.pending",
        message=(
            f"Lock transfer of {amount} USDC is still confirming on-chain; "
            "escrow remains pending."
        ),
        actor=user.id,
        data={
            "amount_usdc": str(amount),
            "escrow_address": escrow_ref.address,
            "lock_tx_ref": escrow_ref.lock_tx_ref,
        },
    )
    session.commit()
    raise HTTPException(
        status_code=status.HTTP_202_ACCEPTED,
        detail={
            "error": "escrow_lock_pending",
            "amount_usdc": str(amount),
            "lock_tx_ref": escrow_ref.lock_tx_ref,
            "message": (
                "The lock transfer was accepted but has not yet confirmed on-chain. "
                "The escrow is pending; retry shortly to advance the objective."
            ),
        },
    )


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


def _latest_evaluation(
    session: Session, objective_id: str, role_id: str | None = None
) -> GovernanceEvaluation | None:
    """Latest Copilot evaluation for an objective, or a specific sub-task.

    With ``role_id`` omitted this returns the objective-level evaluation
    (``role_id IS NULL``); passing a role id returns the advisory evaluation
    scoped to that coordination sub-task.
    """

    stmt = select(GovernanceEvaluation).where(
        GovernanceEvaluation.objective_id == objective_id
    )
    if role_id is None:
        stmt = stmt.where(GovernanceEvaluation.role_id.is_(None))
    else:
        stmt = stmt.where(GovernanceEvaluation.role_id == role_id)
    return session.exec(
        stmt.order_by(GovernanceEvaluation.created_at.desc())
    ).first()


def _objective_step_dicts(session: Session, obj: Objective) -> list[dict]:
    """Normalized step dicts for an objective's latest execution run.

    The single source of step truth the evidence builders and the advisory
    Copilot evaluation all share, so every consumer reasons over the exact same
    deterministic inputs (and therefore the same ``evidence_hash``).
    """

    run = session.exec(
        select(ExecutionRun)
        .where(ExecutionRun.objective_id == obj.id)
        .order_by(ExecutionRun.created_at.desc())
    ).first()
    steps = (
        session.exec(
            select(ExecutionStep)
            .where(ExecutionStep.run_id == run.id)
            .order_by(ExecutionStep.index.asc())
        ).all()
        if run
        else []
    )
    return [
        {
            "index": s.index,
            "title": s.title,
            "status": s.status.value,
            "output": s.output,
        }
        for s in steps
    ]


def _objective_evidence(session: Session, obj: Objective) -> list[dict]:
    """Rebuild the normalized evidence dicts for an objective from its steps.

    Deterministic: the same step inputs yield the same evidence and therefore
    the same ``evidence_hash`` the independent validator bound at evaluation
    time. This lets the settlement authorization re-derive criterion
    satisfaction from the exact evidence that was validated.
    """

    step_dicts = _objective_step_dicts(session, obj)
    return [e.to_dict() for e in oracle.build_evidence(step_dicts)]


def _objective_evidence_bundle(
    session: Session, obj: Objective
) -> tuple[list[dict], dict]:
    """Build (evidence_dicts, evidence_summary) for an objective's latest run.

    Sub-task validation reuses the exact same evidence the objective-level
    validator reasons over — there is no separate sub-task evidence store. What
    differs per sub-task is the *contract* (its own success criteria) judged
    against this shared evidence, not the evidence itself.
    """

    step_dicts = _objective_step_dicts(session, obj)
    evidence_objs = oracle.build_evidence(step_dicts)
    return (
        [e.to_dict() for e in evidence_objs],
        oracle.evidence_summary(evidence_objs),
    )


def _get_owned_role(
    session: Session, obj: Objective, role_id: str
) -> WorkflowRole:
    role = session.get(WorkflowRole, role_id)
    if role is None or role.objective_id != obj.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )
    return role


@router.post(
    "/{objective_id}/roles/{role_id}/validate", response_model=ObjectiveDetailOut
)
async def validate_subtask(
    objective_id: str,
    role_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Validate one coordination sub-task independently.

    Runs the *same* independent validation engine and evidence-grounded
    authorization used at the objective level, but scoped to this sub-task's own
    success criteria and bound to its role_id. A sub-task can only be validated
    once its dependency sub-tasks have themselves passed validation (the
    coordination graph's execution order), so the DAG is honored. Sets the
    sub-task's validation_status to passed | failed from the evidence verdict.
    """

    obj = _get_owned_objective(session, workspace, objective_id)
    role = _get_owned_role(session, obj, role_id)

    # Evidence must exist — the objective has to have executed at least once.
    run = session.exec(
        select(ExecutionRun)
        .where(ExecutionRun.objective_id == obj.id)
        .order_by(ExecutionRun.created_at.desc())
    ).first()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The objective must execute before a sub-task can be validated.",
        )
    if role.validation_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sub-task already validated ({role.validation_status}).",
        )

    # Honor the dependency DAG: every prerequisite sub-task must have passed.
    roles = workflow_domain.get_roles(session, obj.id)
    graph = workflow_domain.coordination_graph(roles)
    node = next((n for n in graph["nodes"] if n["role_id"] == role.id), None)
    if node and node["dependency_state"] == "cycle":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sub-task is part of a dependency cycle and cannot be validated.",
        )
    if node and node["dependency_state"] == "blocked_failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A prerequisite sub-task failed validation; this sub-task cannot pass.",
        )
    if node and node["dependency_state"] == "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Sub-task is blocked: its dependencies have not all passed "
                "validation yet."
            ),
        )

    evidence_dicts, evidence_summary = _objective_evidence_bundle(session, obj)

    record = None
    authorization = None
    try:
        record = validation.run_validation(
            session,
            objective_id=obj.id,
            workspace_id=obj.workspace_id,
            evidence=evidence_dicts,
            evidence_summary=evidence_summary,
            executor_agent_id=role.assigned_agent_id,
            role_id=role.id,
        )
        # Authorize against THIS sub-task's own success criteria.
        authorization = validation.record_authorization(
            session,
            objective_id=obj.id,
            raw_criteria=list(role.success_criteria or []),
            evidence=evidence_dicts,
            approved=record.recommendation != validation.REJECTED,
            role_id=role.id,
        )
    except Exception as exc:  # noqa: BLE001 — never 500 on a validation engine miss
        logger.warning("Sub-task validation engine error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sub-task validation failed to run.",
        )

    passed = authorization.evidence_verdict != validation.REJECTED
    role.validation_status = "passed" if passed else "failed"
    role.updated_at = datetime.now(timezone.utc)
    session.add(role)

    # Advisory Copilot reasoning scoped to THIS sub-task's own success criteria.
    # Mirrors the objective-level evaluation but bound to role_id, so the
    # coordination graph carries per-sub-task findings, risks, and conditions.
    # Strictly advisory and strictly non-blocking — the deterministic validation
    # above already set the authoritative sub-task verdict.
    try:
        sub_steps = _objective_step_dicts(session, obj)
        sub_evidence = oracle.build_evidence(sub_steps)
        sub_eval = await copilot.evaluate_governance(
            intent=obj.intent,
            summary=role.description or role.title,
            criteria=list(role.success_criteria or []),
            steps=sub_steps,
            evidence_block=oracle.render_evidence_block(sub_evidence),
            evidence_summary=evidence_summary,
        )
        session.add(
            GovernanceEvaluation(
                objective_id=obj.id,
                role_id=role.id,
                recommendation=sub_eval["recommendation"],
                reasoning=sub_eval.get("reasoning", ""),
                findings=sub_eval.get("findings", []),
                risks=sub_eval.get("risks", []),
                conditions=sub_eval.get("conditions", []),
                source=sub_eval.get("_source", "copilot"),
            )
        )
        log_event(
            session,
            objective_id=obj.id,
            kind="subtask.evaluated",
            message=(
                f"Coordination Copilot reviewed sub-task '{role.title}' against its "
                f"own success criteria and recommends '{sub_eval['recommendation']}'."
            ),
            actor="copilot",
            data={
                "role_id": role.id,
                "role_key": role.role_key,
                "recommendation": sub_eval["recommendation"],
                "source": sub_eval.get("_source", "copilot"),
                "risk_count": len(sub_eval.get("risks", []) or []),
            },
        )
    except Exception as exc:  # noqa: BLE001 — advisory eval must never block validation
        logger.warning("Sub-task Copilot evaluation skipped: %s", exc)

    validator = session.get(Validator, record.validator_id)
    log_event(
        session,
        objective_id=obj.id,
        kind="subtask.validated",
        message=(
            f"Sub-task '{role.title}' {'passed' if passed else 'failed'} independent "
            f"validation: {authorization.criteria_satisfied}/{authorization.criteria_total} "
            f"of its success criteria are satisfied by evidence "
            f"(verdict '{authorization.evidence_verdict}', validated by "
            f"{validator.name if validator else 'independent validator'})."
        ),
        actor=validator.validator_key if validator else "validator",
        data={
            "role_id": role.id,
            "role_key": role.role_key,
            "validation_status": role.validation_status,
            "evidence_verdict": authorization.evidence_verdict,
            "criteria_satisfied": authorization.criteria_satisfied,
            "criteria_total": authorization.criteria_total,
            "evidence_hash": authorization.evidence_hash,
            "validator_id": record.validator_id,
            "confidence": record.confidence,
        },
    )
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.post(
    "/{objective_id}/roles/{role_id}/settle", response_model=ObjectiveDetailOut
)
def settle_subtask(
    objective_id: str,
    role_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Settle one coordination sub-task independently.

    A sub-task that passed validation releases its own allocation (net of the
    hybrid volume fee) to a per-sub-task payout wallet; one that failed slashes
    its allocation back to the workspace treasury. The release/slash is a real
    partial movement against the objective's escrow, recorded as a Settlement
    bound to the role_id, and the assigned agent's reputation is attributed
    immediately. The parent objective is unaffected until its own settle gate.
    """

    obj = _get_owned_objective(session, workspace, objective_id)
    role = _get_owned_role(session, obj, role_id)

    if role.validation_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Validate the sub-task before settling it.",
        )
    if role.settlement_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sub-task already settled ({role.settlement_status}).",
        )

    escrow = session.exec(
        select(EscrowState)
        .where(EscrowState.objective_id == obj.id)
        .order_by(EscrowState.created_at.desc())
    ).first()
    if escrow is None or escrow.status != EscrowStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No locked escrow is available to settle this sub-task against.",
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
        alloc = Decimal(role.allocation_usdc or "0")
    except InvalidOperation:
        alloc = Decimal("0")

    released = role.validation_status == "passed"
    authorization = validation.latest_authorization(session, obj.id, role_id=role.id)

    try:
        provider = get_settlement_provider()
        if released:
            quote = quote_settlement_fee(alloc)
            fee = quote.fee_usdc
            net = (alloc - fee).quantize(_USDC_QUANT)
            payout = _resolve_payout_wallet(
                provider,
                session,
                ref=f"payout-{obj.id}-{role.id}",
                agent_id=role.assigned_agent_id,
            )
            transfer = provider.release_escrow(
                EscrowRef(
                    provider_escrow_id=escrow.provider_escrow_id or "",
                    address=escrow.address or "",
                    amount=net,
                ),
                payout,
            )
            settlement = Settlement(
                objective_id=obj.id,
                role_id=role.id,
                status=SettlementStatus.SETTLED,
                amount_usdc=str(net),
                fee_usdc=str(fee),
                fee_basis=quote.basis,
                payout_tx_ref=transfer.tx_ref,
            )
            session.add(settlement)
            role.settlement_status = "settled"
            role.outcome = "released"
            role.status = RoleStatus.COMPLETED
            log_event(
                session,
                objective_id=obj.id,
                kind="subtask.settled",
                message=(
                    f"Sub-task '{role.title}' settled independently: released {net} USDC "
                    f"to its agent (fee {fee} USDC, {quote.basis})"
                    + (
                        f" — authorized by {authorization.criteria_satisfied}"
                        f"/{authorization.criteria_total} satisfied success criteria."
                        if authorization
                        else "."
                    )
                ),
                actor=user.id,
                data={
                    "role_id": role.id,
                    "role_key": role.role_key,
                    "net_usdc": str(net),
                    "fee_usdc": str(fee),
                    "fee_basis": quote.basis,
                    "payout_address": payout.address,
                    "payout_tx_ref": transfer.tx_ref,
                    "agent_id": role.assigned_agent_id,
                    "authorization_id": authorization.id if authorization else None,
                    "evidence_hash": authorization.evidence_hash if authorization else None,
                },
            )
        else:
            transfer = provider.slash_escrow(
                EscrowRef(
                    provider_escrow_id=escrow.provider_escrow_id or "",
                    address=escrow.address or "",
                    amount=alloc,
                ),
                treasury_ref,
            )
            settlement = Settlement(
                objective_id=obj.id,
                role_id=role.id,
                status=SettlementStatus.SLASHED,
                amount_usdc=str(alloc),
                fee_usdc="0",
                fee_basis="slashed — no fee",
                payout_tx_ref=transfer.tx_ref,
            )
            session.add(settlement)
            role.settlement_status = "slashed"
            role.outcome = "slashed"
            role.status = RoleStatus.FAILED
            log_event(
                session,
                objective_id=obj.id,
                kind="subtask.slashed",
                message=(
                    f"Sub-task '{role.title}' failed validation; slashed {alloc} USDC "
                    "back to treasury."
                ),
                actor=user.id,
                data={
                    "role_id": role.id,
                    "role_key": role.role_key,
                    "amount_usdc": str(alloc),
                    "treasury_address": treasury.address,
                    "slash_tx_ref": transfer.tx_ref,
                    "agent_id": role.assigned_agent_id,
                },
            )
    except SettlementConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    role.updated_at = datetime.now(timezone.utc)
    session.add(role)

    # Attribute the sub-task outcome to its assigned agent immediately, reusing
    # the registry's single reputation mutation point. Never blocks settlement.
    if role.assigned_agent_id:
        try:
            agent = session.get(AgentIdentity, role.assigned_agent_id)
            if agent is not None:
                registry.record_outcome(
                    session,
                    agent=agent,
                    objective_id=obj.id,
                    success=released,
                    note=f"sub-task settlement ({role.role_key})",
                )
        except Exception as exc:  # noqa: BLE001 — registry must never block settlement
            logger.warning("Sub-task reputation attribution skipped: %s", exc)

    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.post("/{objective_id}/audit/evaluate", response_model=ObjectiveDetailOut)
async def evaluate_governance_route(
    objective_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """AI-powered governance evaluation (advisory).

    The Coordination Copilot reviews the recorded execution outputs against the
    objective's validation criteria and produces a structured recommendation
    (approved / approved_with_conditions / rejected) with reasoning and
    per-criterion findings. This does NOT settle or transition the objective —
    a human reviewer still issues the authoritative decision via /audit/decide.
    """
    obj = _get_owned_objective(session, workspace, objective_id)

    if obj.status != ObjectiveStatus.UNDER_AUDIT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Objective must complete execution before it can be evaluated.",
        )

    criteria = obj.governance_config.get("validation_criteria") or []
    run = session.exec(
        select(ExecutionRun)
        .where(ExecutionRun.objective_id == obj.id)
        .order_by(ExecutionRun.created_at.desc())
    ).first()
    steps = (
        session.exec(
            select(ExecutionStep)
            .where(ExecutionStep.run_id == run.id)
            .order_by(ExecutionStep.index.asc())
        ).all()
        if run
        else []
    )
    step_dicts = [
        {
            "index": s.index,
            "title": s.title,
            "status": s.status.value,
            "output": s.output,
        }
        for s in steps
    ]

    # SLA oracle: normalize unstructured / browser-agent outputs into
    # auditor-readable evidence before evaluation, so the audit handles more
    # than clean API responses.
    evidence = oracle.build_evidence(step_dicts)
    evidence_block = oracle.render_evidence_block(evidence)
    evidence_summary = oracle.evidence_summary(evidence)

    result = await copilot.evaluate_governance(
        intent=obj.intent,
        summary=obj.summary,
        criteria=list(criteria),
        steps=step_dicts,
        evidence_block=evidence_block,
        evidence_summary=evidence_summary,
    )

    evaluation = GovernanceEvaluation(
        objective_id=obj.id,
        recommendation=result["recommendation"],
        reasoning=result.get("reasoning", ""),
        findings=result.get("findings", []),
        risks=result.get("risks", []),
        conditions=result.get("conditions", []),
        source=result.get("_source", "copilot"),
    )
    session.add(evaluation)
    session.flush()

    log_event(
        session,
        objective_id=obj.id,
        kind="audit.evaluated",
        message=(
            f"Coordination Copilot recommends '{evaluation.recommendation}' "
            "after reviewing execution against governance criteria."
        ),
        actor="copilot",
        data={
            "recommendation": evaluation.recommendation,
            "source": evaluation.source,
            "criteria_count": len(criteria),
            "risk_count": len(evaluation.risks or []),
            "evidence_kinds": evidence_summary.get("kinds", {}),
            "evidence_qualities": evidence_summary.get("qualities", {}),
            "unstructured_present": evidence_summary.get("unstructured_present", False),
        },
    )

    # Independent validation layer: a validator distinct from the executor binds
    # the collected evidence to a recommendation it is accountable for. This is
    # the formal validation; the Copilot evaluation above is advisory reasoning.
    # Never blocks the audit on a validation miss.
    try:
        evidence_dicts = [e.to_dict() for e in evidence]
        record = validation.run_validation(
            session,
            objective_id=obj.id,
            workspace_id=obj.workspace_id,
            evidence=evidence_dicts,
            evidence_summary=evidence_summary,
            executor_agent_id=obj.agent_id,
            evaluation_id=evaluation.id,
        )
        validator = session.get(Validator, record.validator_id)
        log_event(
            session,
            objective_id=obj.id,
            kind="validation.recorded",
            message=(
                f"{validator.name if validator else 'Independent validator'} "
                f"validated the evidence and recommends '{record.recommendation}' "
                f"({int(record.confidence * 100)}% confidence), independent of the executor."
            ),
            actor=validator.validator_key if validator else "validator",
            data={
                "validator_id": record.validator_id,
                "validator_name": validator.name if validator else None,
                "recommendation": record.recommendation,
                "confidence": record.confidence,
                "evidence_hash": record.evidence_hash,
                "independent_of_executor": record.independent_of_executor,
            },
        )
    except Exception as exc:  # noqa: BLE001 — validation must never block the audit
        logger.warning("Independent validation skipped during evaluation: %s", exc)

    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


@router.post("/{objective_id}/audit/decide", response_model=ObjectiveDetailOut)
def decide_audit(
    body: AuditDecision,
    objective_id: str,
    user: User = Depends(get_current_user),
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ObjectiveDetailOut:
    """Human governance decision (authoritative).

    A reviewer issues the binding approve/reject on the execution, optionally
    overriding the Copilot's recommendation. Requires an AI evaluation first so
    the decision is governance-aware. Advances UNDER_AUDIT -> GOVERNANCE_DECISION.
    """
    obj = _get_owned_objective(session, workspace, objective_id)

    if obj.status != ObjectiveStatus.UNDER_AUDIT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Objective must complete execution before it can be validated.",
        )

    evaluation = _latest_evaluation(session, obj.id)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run the governance evaluation before issuing a decision.",
        )

    approved = body.decision.strip().lower() != "reject"
    # The Copilot recommends settlement unless it explicitly rejected.
    recommended_approve = evaluation.recommendation != "rejected"
    overridden = approved != recommended_approve
    criteria = obj.governance_config.get("validation_criteria") or []

    default_note = (
        "Reviewer approved the execution against the governance criteria."
        if approved
        else "Reviewer rejected the execution against the governance criteria."
    )
    if overridden:
        default_note += (
            f" (Overrides Copilot recommendation: '{evaluation.recommendation}'.)"
        )

    review = AuditReview(
        objective_id=obj.id,
        status=AuditStatus.APPROVED if approved else AuditStatus.FAILED,
        notes=body.notes or default_note,
        reviewer_id=user.id,
        evaluation_id=evaluation.id,
        recommendation=evaluation.recommendation,
        overridden=overridden,
    )
    session.add(review)

    obj.status = ObjectiveStatus.GOVERNANCE_DECISION
    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)

    # Reconcile the independent validation against this authoritative decision so
    # validator accuracy reflects how often the network kept its call.
    try:
        reconciled = validation.reconcile_outcome(
            session, objective_id=obj.id, approved=approved
        )
    except Exception as exc:  # noqa: BLE001 — never block the decision
        logger.warning("Validation reconciliation skipped: %s", exc)
        reconciled = []
    if reconciled:
        upheld = sum(1 for r in reconciled if r.upheld)
        log_event(
            session,
            objective_id=obj.id,
            kind="validation.reconciled",
            message=(
                f"Reconciled {len(reconciled)} validation(s) against the decision: "
                f"{upheld} upheld, {len(reconciled) - upheld} overturned."
            ),
            actor="governance-engine",
            data={
                "approved": approved,
                "upheld": upheld,
                "overturned": len(reconciled) - upheld,
            },
        )

    # Settlement authorization: bind the human decision to the deterministic
    # per-criterion evidence verdict so the objective carries an auditable
    # "why was this authorized?" artifact, hashed to the validated evidence.
    # Never blocks the decision on an authorization miss.
    try:
        evidence_dicts = _objective_evidence(session, obj)
        authorization = validation.record_authorization(
            session,
            objective_id=obj.id,
            raw_criteria=list(criteria),
            evidence=evidence_dicts,
            approved=approved,
        )
        log_event(
            session,
            objective_id=obj.id,
            kind="settlement.authorized" if approved else "settlement.denied",
            message=(
                f"Settlement authorization recorded: {authorization.criteria_satisfied}"
                f"/{authorization.criteria_total} criteria satisfied by evidence "
                f"(evidence verdict '{authorization.evidence_verdict}', "
                f"{'aligned with' if authorization.aligned_with_evidence else 'overrides'} "
                "the human decision)."
            ),
            actor="settlement-authorizer",
            data={
                "authorization_id": authorization.id,
                "evidence_verdict": authorization.evidence_verdict,
                "criteria_satisfied": authorization.criteria_satisfied,
                "criteria_total": authorization.criteria_total,
                "criteria_failed": authorization.criteria_failed,
                "criteria_indeterminate": authorization.criteria_indeterminate,
                "evidence_hash": authorization.evidence_hash,
                "aligned_with_evidence": authorization.aligned_with_evidence,
                "authorized": authorization.authorized,
            },
        )
    except Exception as exc:  # noqa: BLE001 — authorization must never block the decision
        logger.warning("Settlement authorization skipped: %s", exc)

    log_event(
        session,
        objective_id=obj.id,
        kind="audit.approved" if approved else "audit.failed",
        message=(
            "Reviewer approved the execution; settlement authorized."
            if approved
            else "Reviewer rejected the execution; escrow will be slashed."
        )
        + (" Copilot recommendation overridden." if overridden else ""),
        actor=user.id,
        data={
            "approved": approved,
            "recommendation": evaluation.recommendation,
            "overridden": overridden,
            "criteria_count": len(criteria),
        },
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

    On governance approval, release the escrow (net of the hybrid volume fee) to
    a payout wallet representing the execution counterparty. On rejection, slash
    the escrow back to the workspace treasury. Both are real on-chain USDC
    movements via the settlement provider. The fee is resolved from the tiered
    volume schedule (0.5% scaling down, $0.001 micro-fee floor), never a flat
    rate.
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

    # The evidence-grounded authorization recorded at decision time — the
    # deterministic "why this agent is paid" artifact that justifies the release.
    authorization = validation.latest_authorization(session, obj.id)

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

    # Coordination gate: when sub-tasks have begun settling/validating
    # independently, the parent objective can only finalize once every
    # *required* sub-task has passed validation, and it settles only the escrow
    # not already resolved at the sub-task level (so nothing is paid twice).
    roles = workflow_domain.get_roles(session, obj.id)
    graph = workflow_domain.coordination_graph(roles) if roles else None
    subtask_mode = bool(roles) and any(
        r.validation_status != "pending" or r.settlement_status != "pending"
        for r in roles
    )
    if approved and subtask_mode and graph and not graph["parent_settleable"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Parent objective can only settle once every required sub-task "
                f"has passed validation ({graph['required_passed']}/"
                f"{graph['required_total']} required sub-tasks passed)."
            ),
        )
    # Subtract escrow already resolved by independent sub-task settlement.
    accounted = sum(
        (
            Decimal(r.allocation_usdc or "0")
            for r in roles
            if r.settlement_status in ("settled", "slashed")
        ),
        Decimal("0"),
    )
    remaining = (amount - accounted).quantize(_USDC_QUANT)
    if remaining < 0:
        remaining = Decimal("0")

    try:
        provider = get_settlement_provider()
        if approved and remaining <= 0:
            # Every allocation was already released/slashed per sub-task; the
            # parent only needs to finalize state, with no further transfer.
            escrow.status = EscrowStatus.RELEASED
            session.add(escrow)
            session.add(
                Settlement(
                    objective_id=obj.id,
                    status=SettlementStatus.SETTLED,
                    amount_usdc="0",
                    fee_usdc="0",
                    fee_basis="fully settled via sub-tasks",
                    payout_tx_ref=None,
                )
            )
            obj.status = ObjectiveStatus.SETTLED
            log_event(
                session,
                objective_id=obj.id,
                kind="settlement.released",
                message=(
                    "Parent objective finalized: all escrow was already released "
                    "or slashed through independent sub-task settlement."
                ),
                actor=user.id,
                data={
                    "net_usdc": "0",
                    "accounted_usdc": str(accounted),
                    "parent_settleable": graph["parent_settleable"] if graph else None,
                },
            )
        elif approved:
            amount = remaining
            quote = quote_settlement_fee(amount)
            fee = quote.fee_usdc
            net = (amount - fee).quantize(_USDC_QUANT)
            payout = _resolve_payout_wallet(
                provider,
                session,
                ref=f"payout-{obj.id}",
                agent_id=obj.agent_id,
            )
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
                    fee_basis=quote.basis,
                    payout_tx_ref=transfer.tx_ref,
                )
            )
            obj.status = ObjectiveStatus.SETTLED
            log_event(
                session,
                objective_id=obj.id,
                kind="settlement.released",
                message=(
                    f"Released {net} USDC to counterparty (fee {fee} USDC, {quote.basis})"
                    + (
                        f" — authorized because {authorization.criteria_satisfied}"
                        f"/{authorization.criteria_total} success criteria are satisfied "
                        f"by evidence {authorization.evidence_hash[:16]}…."
                        if authorization
                        else "."
                    )
                ),
                actor=user.id,
                data={
                    "net_usdc": str(net),
                    "fee_usdc": str(fee),
                    "fee_basis": quote.basis,
                    "payout_address": payout.address,
                    "payout_tx_ref": transfer.tx_ref,
                    "authorization_id": authorization.id if authorization else None,
                    "evidence_verdict": (
                        authorization.evidence_verdict if authorization else None
                    ),
                    "criteria_satisfied": (
                        authorization.criteria_satisfied if authorization else None
                    ),
                    "criteria_total": (
                        authorization.criteria_total if authorization else None
                    ),
                    "evidence_hash": (
                        authorization.evidence_hash if authorization else None
                    ),
                },
            )
        else:
            # Slash only the escrow not already resolved at the sub-task level.
            amount = remaining
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
                    fee_basis="slashed — no fee",
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

    # Partial settlement: resolve each workflow role's outcome (released vs.
    # slashed) so a multi-agent objective records a per-role result, not just a
    # single objective-level verdict. Runs before the reputation wiring so each
    # role's outcome can attribute to its assigned agent. Never blocks settlement.
    try:
        resolved_roles = workflow_domain.settle_roles(
            session, objective_id=obj.id, approved=approved
        )
    except Exception as exc:  # noqa: BLE001 — role settlement must never block
        logger.warning("Role settlement skipped: %s", exc)
        resolved_roles = []
    if resolved_roles:
        released = sum(1 for r in resolved_roles if r.outcome == "released")
        slashed = len(resolved_roles) - released
        log_event(
            session,
            objective_id=obj.id,
            kind="settlement.roles",
            message=(
                f"Resolved {len(resolved_roles)} workflow role(s): "
                f"{released} released, {slashed} slashed."
            ),
            actor="settlement-engine",
            data={
                "released": released,
                "slashed": slashed,
                "roles": [
                    {
                        "role_key": r.role_key,
                        "allocation_usdc": r.allocation_usdc,
                        "outcome": r.outcome,
                        "agent_id": r.assigned_agent_id,
                    }
                    for r in resolved_roles
                ],
            },
        )

    # Reputation feedback loop: fold the settlement outcome back into the agent
    # identity registry automatically. Auto-reveals any pre-committed blind
    # feedback for this objective and records the outcome for the assigned
    # agent. Never blocks settlement on a registry miss.
    try:
        affected_agents = registry.record_settlement_outcome(
            session, objective=obj, success=approved
        )
    except Exception as exc:  # noqa: BLE001 — registry must never block settlement
        logger.warning("Reputation wiring skipped after settlement: %s", exc)
        affected_agents = []

    if affected_agents:
        log_event(
            session,
            objective_id=obj.id,
            kind="reputation.updated",
            message=(
                f"Reputation updated for {len(affected_agents)} agent(s) after "
                f"{'successful settlement' if approved else 'slash'}."
            ),
            actor=user.id,
            data={
                "success": approved,
                "agents": [
                    {
                        "token_id": a.token_id,
                        "reputation_score": a.reputation_score,
                        "jobs_completed": a.jobs_completed,
                        "jobs_failed": a.jobs_failed,
                    }
                    for a in affected_agents
                ],
            },
        )

    obj.updated_at = datetime.now(timezone.utc)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return _detail(session, obj)


# Block-explorer link construction is the one chain-specific concern that has to
# surface in API responses. Keep it confined to these two helpers (and the
# constants below) so a settlement-provider/chain swap touches one place instead
# of every call site that builds a proof link.
_EXPLORER_BASE = "https://explorer.solana.com"
_EXPLORER_CLUSTER = "devnet"


def _tx_explorer_url(tx_hash: str | None) -> str | None:
    if not tx_hash:
        return None
    return f"{_EXPLORER_BASE}/tx/{tx_hash}?cluster={_EXPLORER_CLUSTER}"


def _address_explorer_url(address: str | None) -> str | None:
    if not address:
        return None
    return f"{_EXPLORER_BASE}/address/{address}?cluster={_EXPLORER_CLUSTER}"


def _resolve_tx_hash(tx_ref: str | None, existing: str | None) -> str | None:
    """Best-effort resolve a provider tx id to its on-chain signature.

    Cached once confirmed (the caller persists the result). Never raises — if
    the provider is unreachable or the tx is still unconfirmed, returns None and
    the UI falls back to account-level links.
    """
    if existing:
        return existing
    if not tx_ref:
        return None
    try:
        proof = get_settlement_provider().get_transaction_proof(tx_ref)
        return proof.tx_hash
    except Exception:  # noqa: BLE001 — proof resolution is best-effort
        return None


def _resolve_payout_wallet(
    provider,
    session: Session,
    *,
    ref: str,
    agent_id: str | None = None,
) -> WalletRef:
    """Resolve the destination wallet a release settles funds into.

    Single decision point for *where* a release lands (Escrow V1.5). When the
    payee agent has a payout address it has *proven control of* (signed a
    challenge — see app.domain.payout), funds settle to that counterparty-owned
    wallet directly; no new wallet is minted. Only a verified address is ever
    used, so an unproven or absent one transparently falls back to provisioning
    a fresh provider wallet — preserving prior behavior for unassigned or
    unregistered payees. This keeps escrow custody, the settlement model, and the
    fee model untouched: only the *destination* of a release changed.
    See docs/payout-destination-decoupling-proposal.md.
    """
    if agent_id:
        agent = session.get(AgentIdentity, agent_id)
        address = registry.resolve_verified_payout_address(agent)
        if address:
            return WalletRef(
                provider_wallet_id="",
                address=address,
                blockchain=(agent.payout_blockchain if agent else "") or "",
            )
    return provider.provision_treasury_wallet(ref)


def _escrow_out(escrow: EscrowState | None) -> EscrowOut | None:
    if escrow is None:
        return None
    explorer = _address_explorer_url(escrow.address)
    return EscrowOut(
        id=escrow.id,
        status=escrow.status.value,
        amount_usdc=escrow.amount_usdc,
        custody_model=escrow.custody_model,
        controller_wallet=escrow.controller_wallet,
        address=escrow.address,
        provider_escrow_id=escrow.provider_escrow_id,
        lock_tx_ref=escrow.lock_tx_ref,
        lock_tx_hash=escrow.lock_tx_hash,
        lock_tx_url=_tx_explorer_url(escrow.lock_tx_hash),
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


def _evaluation_out(
    evaluation: GovernanceEvaluation | None,
) -> GovernanceEvaluationOut | None:
    if evaluation is None:
        return None
    findings = []
    for f in evaluation.findings or []:
        if isinstance(f, dict):
            findings.append(
                GovernanceFinding(
                    criterion=str(f.get("criterion", "")),
                    met=bool(f.get("met")),
                    assessment=f.get("assessment"),
                )
            )
    risks = []
    for r in evaluation.risks or []:
        if isinstance(r, dict):
            risks.append(
                GovernanceRisk(
                    category=str(r.get("category", "governance")),
                    severity=str(r.get("severity", "low")),
                    detail=str(r.get("detail", "")),
                )
            )
    return GovernanceEvaluationOut(
        id=evaluation.id,
        role_id=evaluation.role_id,
        recommendation=evaluation.recommendation,
        reasoning=evaluation.reasoning,
        findings=findings,
        risks=risks,
        conditions=[str(c) for c in (evaluation.conditions or [])],
        source=evaluation.source,
        created_at=evaluation.created_at,
    )


def _validator_out(validator: Validator | None) -> ValidatorOut | None:
    if validator is None:
        return None
    reconciled = validator.upheld_count + validator.overturned_count
    return ValidatorOut(
        id=validator.id,
        validator_key=validator.validator_key,
        name=validator.name,
        kind=validator.kind,
        description=validator.description,
        independent=validator.independent,
        active=validator.active,
        validations_count=validator.validations_count,
        upheld_count=validator.upheld_count,
        overturned_count=validator.overturned_count,
        accuracy=round(validator.upheld_count / reconciled, 4) if reconciled else None,
        mean_confidence=validator.mean_confidence,
        created_at=validator.created_at,
    )


def _validation_out(
    record: ValidationRecord | None, validator: Validator | None
) -> ValidationRecordOut | None:
    if record is None:
        return None
    findings = [
        ValidationFinding(
            step_index=f.get("step_index"),
            step_title=f.get("step_title"),
            output_kind=f.get("output_kind"),
            quality=f.get("quality"),
            errors=bool(f.get("errors")),
        )
        for f in (record.findings or [])
        if isinstance(f, dict)
    ]
    return ValidationRecordOut(
        id=record.id,
        objective_id=record.objective_id,
        recommendation=record.recommendation,
        confidence=record.confidence,
        reasoning=record.reasoning,
        findings=findings,
        evidence_hash=record.evidence_hash,
        evidence_summary=record.evidence_summary or {},
        executor_agent_id=record.executor_agent_id,
        independent_of_executor=record.independent_of_executor,
        outcome=record.outcome,
        upheld=record.upheld,
        created_at=record.created_at,
        reconciled_at=record.reconciled_at,
        validator=_validator_out(validator),
    )


def _authorization_out(
    authorization: SettlementAuthorization | None,
) -> SettlementAuthorizationOut | None:
    if authorization is None:
        return None
    results: list[CriterionResultOut] = []
    for r in authorization.criteria_results or []:
        if not isinstance(r, dict):
            continue
        basis = [
            CriterionBasisOut(
                step_index=b.get("step_index"),
                step_title=b.get("step_title"),
                output_kind=b.get("output_kind"),
                quality=b.get("quality"),
                matched_terms=list(b.get("matched_terms") or []),
            )
            for b in (r.get("basis") or [])
            if isinstance(b, dict)
        ]
        results.append(
            CriterionResultOut(
                key=str(r.get("key", "")),
                description=str(r.get("description", "")),
                required_evidence_kind=r.get("required_evidence_kind"),
                satisfied=r.get("satisfied"),
                confidence=float(r.get("confidence") or 0.0),
                rationale=str(r.get("rationale", "")),
                basis=basis,
            )
        )
    return SettlementAuthorizationOut(
        id=authorization.id,
        objective_id=authorization.objective_id,
        role_id=authorization.role_id,
        evidence_hash=authorization.evidence_hash,
        criteria_results=results,
        criteria_total=authorization.criteria_total,
        criteria_satisfied=authorization.criteria_satisfied,
        criteria_failed=authorization.criteria_failed,
        criteria_indeterminate=authorization.criteria_indeterminate,
        evidence_verdict=authorization.evidence_verdict,
        headline=authorization.headline,
        governance_approved=authorization.governance_approved,
        aligned_with_evidence=authorization.aligned_with_evidence,
        authorized=authorization.authorized,
        created_at=authorization.created_at,
    )


def _audit_out(review: AuditReview | None) -> AuditReviewOut | None:
    if review is None:
        return None
    return AuditReviewOut(
        id=review.id,
        status=review.status.value,
        notes=review.notes,
        recommendation=review.recommendation,
        overridden=review.overridden,
        created_at=review.created_at,
    )


def _settlement_out(
    settlement: Settlement | None, payout_address: str | None
) -> SettlementOut | None:
    if settlement is None:
        return None
    explorer = _address_explorer_url(payout_address)
    return SettlementOut(
        id=settlement.id,
        status=settlement.status.value,
        amount_usdc=settlement.amount_usdc,
        fee_usdc=settlement.fee_usdc,
        fee_basis=settlement.fee_basis,
        payout_address=payout_address,
        payout_tx_ref=settlement.payout_tx_ref,
        payout_tx_hash=settlement.payout_tx_hash,
        payout_tx_url=_tx_explorer_url(settlement.payout_tx_hash),
        explorer_url=explorer,
    )


def _evidence_trail(
    session: Session,
    obj: Objective,
    run: ExecutionRun | None,
    validation_record: ValidationRecord | None,
    authorization: SettlementAuthorization | None,
    settlement: Settlement | None,
) -> EvidenceTrailOut | None:
    """Assemble the human-readable output→evidence→validation→authorization→
    settlement audit trail for an objective.

    Re-derives the normalized evidence deterministically (the same inputs the
    validator and authorization reasoned over), then threads each evidence step
    forward to the success criteria it grounds and back to any validator finding
    that flagged it. The ``evidence_hash`` is the anchor proving the agent was
    authorized against the exact evidence that was validated.
    """

    if run is None:
        return None

    evidence = _objective_evidence(session, obj)
    if not evidence:
        return None

    # Map step_index -> set of validation findings flagging an error there.
    flagged: set[int] = set()
    for f in (validation_record.findings if validation_record else []) or []:
        if isinstance(f, dict) and f.get("errors") and f.get("step_index") is not None:
            flagged.add(int(f["step_index"]))

    # Map step_index -> criterion descriptions this evidence grounds, from the
    # authorization's per-criterion basis.
    supports: dict[int, list[str]] = {}
    if authorization:
        for r in authorization.criteria_results or []:
            if not isinstance(r, dict):
                continue
            desc = str(r.get("description") or r.get("key") or "")
            for b in r.get("basis") or []:
                if isinstance(b, dict) and b.get("step_index") is not None:
                    supports.setdefault(int(b["step_index"]), [])
                    if desc and desc not in supports[int(b["step_index"])]:
                        supports[int(b["step_index"])].append(desc)

    items: list[EvidenceTrailItem] = []
    for e in evidence:
        idx = int(e.get("step_index", 0) or 0)
        text = str(e.get("normalized_text") or "")
        snippet = text if len(text) <= 200 else text[:197].rstrip() + "…"
        items.append(
            EvidenceTrailItem(
                step_index=idx,
                step_title=str(e.get("step_title") or "step"),
                status=str(e.get("status") or "unknown"),
                output_kind=str(e.get("output_kind") or "free_text"),
                quality=str(e.get("quality") or "unknown"),
                has_errors=bool((e.get("signals") or {}).get("error_markers")),
                snippet=snippet,
                supports_criteria=supports.get(idx, []),
                validation_flagged=idx in flagged,
            )
        )

    # The cryptographic anchor: validation bound a hash; authorization re-derived
    # one. They must match for the settlement to be evidence-honest.
    v_hash = validation_record.evidence_hash if validation_record else None
    a_hash = authorization.evidence_hash if authorization else None
    anchor = a_hash or v_hash
    hash_consistent = bool(v_hash and a_hash and v_hash == a_hash)

    settled = settlement is not None and settlement.status in (
        SettlementStatus.SETTLED,
        SettlementStatus.SLASHED,
    )
    stages = [
        EvidenceTrailStage(
            key="output",
            label="Execution output",
            complete=True,
            detail=f"{len(items)} step output{'s' if len(items) != 1 else ''} recorded",
        ),
        EvidenceTrailStage(
            key="evidence",
            label="Normalized evidence",
            complete=True,
            detail=(
                f"{len(items)} output{'s' if len(items) != 1 else ''} classified "
                "and quality-graded by the SLA oracle"
            ),
        ),
        EvidenceTrailStage(
            key="validation",
            label="Independent validation",
            complete=validation_record is not None,
            detail=(
                f"validator bound evidence and recommended "
                f"'{validation_record.recommendation}'"
                if validation_record
                else "not yet validated"
            ),
        ),
        EvidenceTrailStage(
            key="authorization",
            label="Settlement authorization",
            complete=authorization is not None,
            detail=(
                f"{authorization.criteria_satisfied}/{authorization.criteria_total} "
                "success criteria satisfied by evidence"
                if authorization
                else "not yet authorized"
            ),
        ),
        EvidenceTrailStage(
            key="settlement",
            label="Settlement",
            complete=settled,
            detail=(
                f"{settlement.status.value} · {settlement.amount_usdc} USDC"
                if settled and settlement
                else "not yet settled"
            ),
        ),
    ]

    return EvidenceTrailOut(
        evidence_hash=anchor,
        hash_consistent=hash_consistent,
        items=items,
        stages=stages,
        criteria_total=authorization.criteria_total if authorization else 0,
        criteria_satisfied=authorization.criteria_satisfied if authorization else 0,
    )


def _onchain_ledger(
    escrow: EscrowState | None,
    all_settlements: list[Settlement],
    treasury,
    roles: list[WorkflowRole],
    events: list[GovernanceEvent],
) -> OnChainLedger | None:
    """Assemble the full on-chain money trail for an objective.

    Threads the escrow lock and every settlement (objective-level and
    per-sub-task release/slash) into a single chronological ledger with named
    counterparties, explorer links, and running totals. Movements whose
    signature has not yet confirmed are still listed (``confirmed=False``) so the
    gap is visible rather than hidden.
    """

    if escrow is None and not all_settlements:
        return None

    blockchain = (treasury.blockchain if treasury else None) or (
        escrow.blockchain if escrow and hasattr(escrow, "blockchain") else None
    )
    treasury_address = treasury.address if treasury else None
    treasury_explorer = _address_explorer_url(treasury_address)
    escrow_explorer = _address_explorer_url(escrow.address if escrow else None)

    role_title = {r.id: r.title for r in roles}

    # Payout addresses live on the release/settle events, not on Settlement.
    obj_payout = next(
        (
            e.data.get("payout_address")
            for e in reversed(events)
            if e.kind == "settlement.released" and e.data.get("payout_address")
        ),
        None,
    )
    role_payout: dict[str, str] = {}
    for e in events:
        if e.kind == "subtask.settled" and e.data.get("payout_address"):
            rid = e.data.get("role_id")
            if rid:
                role_payout[str(rid)] = str(e.data["payout_address"])

    movements: list[WalletMovement] = []
    total_locked = Decimal("0")
    total_released = Decimal("0")
    total_slashed = Decimal("0")
    total_fees = Decimal("0")

    # 1. Escrow lock — treasury funds capital into custody.
    if escrow:
        try:
            total_locked = Decimal(escrow.amount_usdc or "0")
        except InvalidOperation:
            total_locked = Decimal("0")
        movements.append(
            WalletMovement(
                kind="lock",
                label="Escrow lock",
                amount_usdc=escrow.amount_usdc or "0",
                direction="inbound",
                from_label="Workspace treasury",
                from_address=treasury_address,
                to_label="Escrow",
                to_address=escrow.address,
                to_explorer_url=escrow_explorer,
                tx_hash=escrow.lock_tx_hash,
                tx_url=_tx_explorer_url(escrow.lock_tx_hash),
                tx_ref=escrow.lock_tx_ref,
                confirmed=bool(escrow.lock_tx_hash),
                occurred_at=escrow.created_at,
            )
        )

    # 2. Each settlement — a release to a payout wallet or a slash to treasury.
    for s in all_settlements:
        is_release = s.status == SettlementStatus.SETTLED
        rid = s.role_id
        try:
            amt = Decimal(s.amount_usdc or "0")
        except InvalidOperation:
            amt = Decimal("0")
        try:
            fee = Decimal(s.fee_usdc or "0")
        except InvalidOperation:
            fee = Decimal("0")

        if is_release:
            total_released += amt
            total_fees += fee
            to_addr = role_payout.get(rid) if rid else obj_payout
            label = (
                f"Release · {role_title.get(rid, 'sub-task')}"
                if rid
                else "Release · objective"
            )
            movements.append(
                WalletMovement(
                    kind="release",
                    label=label,
                    amount_usdc=s.amount_usdc or "0",
                    direction="outbound",
                    from_label="Escrow",
                    from_address=escrow.address if escrow else None,
                    to_label="Agent payout wallet",
                    to_address=to_addr,
                    to_explorer_url=_address_explorer_url(to_addr),
                    tx_hash=s.payout_tx_hash,
                    tx_url=_tx_explorer_url(s.payout_tx_hash),
                    tx_ref=s.payout_tx_ref,
                    confirmed=bool(s.payout_tx_hash),
                    role_id=rid,
                    role_title=role_title.get(rid) if rid else None,
                    occurred_at=s.created_at,
                )
            )
        else:
            total_slashed += amt
            label = (
                f"Slash · {role_title.get(rid, 'sub-task')}"
                if rid
                else "Slash · objective"
            )
            movements.append(
                WalletMovement(
                    kind="slash",
                    label=label,
                    amount_usdc=s.amount_usdc or "0",
                    direction="outbound",
                    from_label="Escrow",
                    from_address=escrow.address if escrow else None,
                    to_label="Workspace treasury",
                    to_address=treasury_address,
                    to_explorer_url=treasury_explorer,
                    tx_hash=s.payout_tx_hash,
                    tx_url=_tx_explorer_url(s.payout_tx_hash),
                    tx_ref=s.payout_tx_ref,
                    confirmed=bool(s.payout_tx_hash),
                    role_id=rid,
                    role_title=role_title.get(rid) if rid else None,
                    occurred_at=s.created_at,
                )
            )

    confirmed = sum(1 for m in movements if m.confirmed)
    return OnChainLedger(
        blockchain=blockchain,
        treasury_address=treasury_address,
        treasury_explorer_url=treasury_explorer,
        escrow_address=escrow.address if escrow else None,
        escrow_explorer_url=escrow_explorer,
        movements=movements,
        total_locked_usdc=str(total_locked),
        total_released_usdc=str(total_released),
        total_slashed_usdc=str(total_slashed),
        total_fees_usdc=str(total_fees),
        confirmed_count=confirmed,
        pending_count=len(movements) - confirmed,
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
    evaluation = _latest_evaluation(session, obj.id)
    validation_record = validation.latest_record(session, obj.id)
    validation_validator = (
        session.get(Validator, validation_record.validator_id)
        if validation_record
        else None
    )
    # Every settlement for the objective — the objective-level payout plus any
    # per-sub-task settlements produced by the coordination graph. Ordered oldest
    # first so the on-chain ledger reads chronologically.
    all_settlements = list(
        session.exec(
            select(Settlement)
            .where(Settlement.objective_id == obj.id)
            .order_by(Settlement.created_at.asc())
        ).all()
    )
    # The authoritative objective-level settlement (role_id is None) is the one
    # surfaced in the headline settlement panel; fall back to the latest of any.
    settlement = next(
        (s for s in reversed(all_settlements) if s.role_id is None),
        all_settlements[-1] if all_settlements else None,
    )
    # payout address is captured on the release event (not stored on Settlement).
    payout_address = next(
        (
            e.data.get("payout_address")
            for e in reversed(events)
            if e.kind == "settlement.released" and e.data.get("payout_address")
        ),
        None,
    )

    # Best-effort resolve provider tx ids to confirmed on-chain signatures so the
    # lock/payout become independently verifiable. Persist once resolved so we
    # only hit the provider until the transaction confirms. Resolves the escrow
    # hops and EVERY settlement (objective + per-sub-task), not just the latest.
    _proof_dirty = False
    if escrow and escrow.lock_tx_ref and not escrow.lock_tx_hash:
        h = _resolve_tx_hash(escrow.lock_tx_ref, None)
        if h:
            escrow.lock_tx_hash = h
            _proof_dirty = True
    if escrow and escrow.settle_tx_ref and not escrow.settle_tx_hash:
        h = _resolve_tx_hash(escrow.settle_tx_ref, None)
        if h:
            escrow.settle_tx_hash = h
            _proof_dirty = True
    for s in all_settlements:
        if s.payout_tx_ref and not s.payout_tx_hash:
            h = _resolve_tx_hash(s.payout_tx_ref, None)
            if h:
                s.payout_tx_hash = h
                session.add(s)
                _proof_dirty = True
    if _proof_dirty:
        if escrow:
            session.add(escrow)
        session.commit()
        session.refresh(obj)

    treasury = workspace_service.get_treasury(session, obj.workspace_id)
    assigned_agent = None
    if obj.agent_id:
        agent = session.get(AgentIdentity, obj.agent_id)
        if agent is not None:
            assigned_agent = _assigned_agent_out(agent)

    roles = workflow_domain.get_roles(session, obj.id)
    feasibility = (
        _feasibility_out(workflow_domain.evaluate_feasibility(session, obj, roles))
        if roles
        else None
    )
    authorization = validation.latest_authorization(session, obj.id)
    evidence_trail = _evidence_trail(
        session, obj, run, validation_record, authorization, settlement
    )
    onchain_ledger = _onchain_ledger(
        escrow, all_settlements, treasury, roles, list(events)
    )
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
        evaluation=_evaluation_out(evaluation),
        validation=_validation_out(validation_record, validation_validator),
        audit=_audit_out(review),
        authorization=_authorization_out(authorization),
        settlement=_settlement_out(settlement, payout_address),
        assigned_agent=assigned_agent,
        workflow=[_role_out(session, r) for r in roles],
        coordination=_coordination_out(roles),
        feasibility=feasibility,
        evidence_trail=evidence_trail,
        onchain_ledger=onchain_ledger,
    )


def _assigned_agent_out(agent: AgentIdentity) -> AssignedAgentOut:
    total = agent.jobs_completed + agent.jobs_failed
    return AssignedAgentOut(
        id=agent.id,
        token_id=agent.token_id,
        name=agent.name,
        reputation_score=agent.reputation_score,
        jobs_completed=agent.jobs_completed,
        jobs_failed=agent.jobs_failed,
        rated=total > 0,
        success_rate=round(agent.jobs_completed / total, 4) if total > 0 else None,
    )


def _role_out(session: Session, role: WorkflowRole) -> WorkflowRoleOut:
    assigned_agent = None
    if role.assigned_agent_id:
        agent = session.get(AgentIdentity, role.assigned_agent_id)
        if agent is not None:
            assigned_agent = _assigned_agent_out(agent)

    # Per-sub-task "why was this paid?" artifact, when the sub-task validated.
    authorization = _authorization_out(
        validation.latest_authorization(session, role.objective_id, role_id=role.id)
    )
    # Per-sub-task settlement record, when it settled independently.
    role_settlement = session.exec(
        select(Settlement)
        .where(Settlement.role_id == role.id)
        .order_by(Settlement.created_at.desc())
    ).first()
    settlement_out = _settlement_out(role_settlement, None) if role_settlement else None

    # Advisory Copilot evaluation scoped to this sub-task, when one was produced.
    evaluation_out = _evaluation_out(
        _latest_evaluation(session, role.objective_id, role_id=role.id)
    )

    return WorkflowRoleOut(
        id=role.id,
        order_index=role.order_index,
        role_key=role.role_key,
        title=role.title,
        description=role.description,
        assigned_agent_id=role.assigned_agent_id,
        assigned_agent=assigned_agent,
        allocation_usdc=role.allocation_usdc,
        status=role.status.value if hasattr(role.status, "value") else str(role.status),
        outcome=role.outcome,
        depends_on=list(role.depends_on or []),
        success_criteria=list(role.success_criteria or []),
        required_evidence_kinds=list(role.required_evidence_kinds or []),
        required=bool(role.required),
        validation_status=role.validation_status,
        settlement_status=role.settlement_status,
        authorization=authorization,
        settlement=settlement_out,
        evaluation=evaluation_out,
    )


def _coordination_out(
    roles: list[WorkflowRole],
) -> CoordinationGraphOut | None:
    """Build the coordination graph view from an objective's sub-tasks."""

    if not roles:
        return None
    graph = workflow_domain.coordination_graph(roles)
    return CoordinationGraphOut(
        nodes=[
            CoordinationNodeOut(
                role_id=n["role_id"],
                role_key=n["role_key"],
                title=n["title"],
                order_index=n["order_index"],
                wave=n["wave"],
                depends_on=list(n["depends_on"]),
                required=n["required"],
                allocation_usdc=n["allocation_usdc"],
                assigned_agent_id=n["assigned_agent_id"],
                validation_status=n["validation_status"],
                settlement_status=n["settlement_status"],
                dependency_state=n["dependency_state"],
                ready=n["ready"],
            )
            for n in graph["nodes"]
        ],
        edges=[
            CoordinationEdgeOut(from_role=e["from"], to_role=e["to"])
            for e in graph["edges"]
        ],
        waves=[list(w) for w in graph["waves"]],
        has_cycle=graph["has_cycle"],
        cycle_role_ids=list(graph["cycle_role_ids"]),
        required_total=graph["required_total"],
        required_passed=graph["required_passed"],
        required_failed=graph["required_failed"],
        parent_settleable=graph["parent_settleable"],
    )


def _feasibility_out(report: dict) -> FeasibilityReport:
    return FeasibilityReport(
        feasible=report["feasible"],
        budget_usdc=report["budget_usdc"],
        required_usdc=report["required_usdc"],
        shortfall_usdc=report["shortfall_usdc"],
        over_budget=report["over_budget"],
        blocking_roles=report["blocking_roles"],
        role_checks=[FeasibilityRoleCheck(**c) for c in report["role_checks"]],
        recommendations=report["recommendations"],
    )
