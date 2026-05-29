"""API request/response contracts.

Kept separate from the SQLModel tables so the wire format is explicit and the
client never depends on storage internals.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models import ObjectiveStatus, WorkspaceRole


# --- Auth / identity --------------------------------------------------------


class SessionExchangeRequest(BaseModel):
    """Web posts the verified identity after OAuth/email sign-in.

    The API is the identity source of truth: it upserts the user, ensures a
    default workspace + treasury, and returns a canonical Brewing session token.
    """

    email: str
    name: str | None = None
    image: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None = None
    image: str | None = None


class WorkspaceOut(BaseModel):
    id: str
    name: str
    org_name: str | None = None
    operational_type: str | None = None
    subscription_tier: str = "free"
    treasury_address: str | None = None
    treasury_blockchain: str | None = None


class SessionOut(BaseModel):
    token: str
    user: UserOut
    workspace: WorkspaceOut
    role: WorkspaceRole


class MeOut(BaseModel):
    user: UserOut
    workspace: WorkspaceOut
    role: WorkspaceRole


# --- Objectives -------------------------------------------------------------


class ObjectiveCreate(BaseModel):
    intent: str
    title: str | None = None


class GovernanceEventOut(BaseModel):
    id: str
    kind: str
    message: str
    actor: str | None = None
    data: dict
    created_at: datetime


class ObjectiveOut(BaseModel):
    id: str
    workspace_id: str
    title: str
    intent: str
    status: ObjectiveStatus
    summary: str | None = None
    escrow_amount_usdc: str
    created_at: datetime
    updated_at: datetime


class EscrowOut(BaseModel):
    id: str
    status: str
    amount_usdc: str
    custody_model: str = "custodial"  # "custodial" | "non_custodial"
    controller_wallet: str | None = None  # agentic wallet holding signing authority
    address: str | None = None
    provider_escrow_id: str | None = None
    lock_tx_ref: str | None = None
    lock_tx_hash: str | None = None  # on-chain signature once confirmed
    lock_tx_url: str | None = None  # explorer /tx/ proof link
    explorer_url: str | None = None  # escrow account on the explorer


class ExecutionStepOut(BaseModel):
    id: str
    index: int
    title: str
    status: str
    output: str | None = None


class ExecutionRunOut(BaseModel):
    id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    steps: list[ExecutionStepOut]


class GovernanceFinding(BaseModel):
    criterion: str
    met: bool
    assessment: str | None = None


class GovernanceEvaluationOut(BaseModel):
    id: str
    recommendation: str  # approved | approved_with_conditions | rejected
    reasoning: str
    findings: list[GovernanceFinding]
    conditions: list[str]
    source: str
    created_at: datetime


class AuditReviewOut(BaseModel):
    id: str
    status: str
    notes: str | None = None
    recommendation: str | None = None
    overridden: bool = False
    created_at: datetime


class SettlementOut(BaseModel):
    id: str
    status: str
    amount_usdc: str
    fee_usdc: str
    fee_basis: str | None = None  # tier applied, e.g. "0.5% volume tier"
    payout_address: str | None = None
    payout_tx_ref: str | None = None
    payout_tx_hash: str | None = None  # on-chain signature once confirmed
    payout_tx_url: str | None = None  # explorer /tx/ proof link
    explorer_url: str | None = None  # payout account on the explorer


class AuditDecision(BaseModel):
    """Governance validation decision applied to a completed execution."""

    decision: str = "approve"  # "approve" | "reject"
    notes: str | None = None


class ObjectiveDetailOut(ObjectiveOut):
    governance_config: dict
    sla_config: dict
    settlement_config: dict
    orchestration_plan: dict
    timeline: list[GovernanceEventOut]
    escrow: EscrowOut | None = None
    treasury_address: str | None = None
    execution: ExecutionRunOut | None = None
    evaluation: GovernanceEvaluationOut | None = None
    audit: AuditReviewOut | None = None
    settlement: SettlementOut | None = None


# --- Dashboard --------------------------------------------------------------


class OverviewMetric(BaseModel):
    label: str
    value: str
    hint: str | None = None


class OverviewOut(BaseModel):
    metrics: list[OverviewMetric]
    status_counts: dict[str, int]
    treasury_balance_usdc: str
    objectives: list[ObjectiveOut]
    recent_events: list[GovernanceEventOut]
