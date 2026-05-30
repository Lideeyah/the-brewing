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
    agent_id: str | None = None  # assigned agent identity (reputation feedback loop)
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


# --- Independent validation layer & registry --------------------------------


class ValidatorOut(BaseModel):
    """A registered independent validator and its accuracy record."""

    id: str
    validator_key: str
    name: str
    kind: str
    description: str | None = None
    independent: bool = True
    active: bool = True
    validations_count: int = 0
    upheld_count: int = 0
    overturned_count: int = 0
    # Share of reconciled validations the authoritative decision kept (0..1).
    accuracy: float | None = None
    mean_confidence: float = 0.0
    created_at: datetime


class ValidationFinding(BaseModel):
    step_index: int | None = None
    step_title: str | None = None
    output_kind: str | None = None
    quality: str | None = None
    errors: bool = False


class ValidationRecordOut(BaseModel):
    """An evidence-bound, independent validation outcome for an objective."""

    id: str
    objective_id: str
    recommendation: str  # approved | approved_with_conditions | rejected
    confidence: float
    reasoning: str
    findings: list[ValidationFinding] = []
    evidence_hash: str
    evidence_summary: dict = {}
    executor_agent_id: str | None = None
    independent_of_executor: bool = True
    outcome: str | None = None  # final governance outcome once reconciled
    upheld: bool | None = None
    created_at: datetime
    reconciled_at: datetime | None = None
    validator: ValidatorOut | None = None


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


# --- Multi-agent workflow ---------------------------------------------------


class WorkflowRoleOut(BaseModel):
    """One independently assignable role in an objective's workflow."""

    id: str
    order_index: int
    role_key: str  # planner | research | analysis | executor | reviewer | validator
    title: str
    description: str | None = None
    assigned_agent_id: str | None = None
    assigned_agent: "AssignedAgentOut | None" = None
    allocation_usdc: str = "0"
    status: str = "pending"
    outcome: str | None = None  # released | slashed, set at settlement


class FeasibilityRoleCheck(BaseModel):
    role_id: str
    role_key: str
    title: str
    allocation_usdc: str
    assigned_agent_id: str | None = None
    assigned_agent_name: str | None = None
    ok: bool
    issues: list[str] = []


class FeasibilityReport(BaseModel):
    """Budget vs. workflow cost vs. agent-minimum reconciliation."""

    feasible: bool
    budget_usdc: str
    required_usdc: str
    shortfall_usdc: str
    over_budget: bool
    blocking_roles: int
    role_checks: list[FeasibilityRoleCheck] = []
    recommendations: list[str] = []


class AssignRoleIn(BaseModel):
    agent_id: str  # AgentIdentity.id to bind to this role


class UpdateAllocationIn(BaseModel):
    allocation_usdc: str  # new role-level settlement allocation (USDC decimal)


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
    validation: "ValidationRecordOut | None" = None
    audit: AuditReviewOut | None = None
    settlement: SettlementOut | None = None
    assigned_agent: "AssignedAgentOut | None" = None
    workflow: list["WorkflowRoleOut"] = []
    feasibility: "FeasibilityReport | None" = None


# --- Agent identity registry ------------------------------------------------


class ServiceEndpoint(BaseModel):
    name: str
    url: str
    protocol: str | None = None


class AgentRegisterIn(BaseModel):
    name: str
    owner: str  # agentic-wallet address / controlling account
    description: str | None = None
    capabilities: list[str] = []
    service_endpoints: list[ServiceEndpoint] = []
    pricing: str | None = None  # free-text, e.g. "0.05 USDC / call"
    discoverable: bool = True
    metadata_uri: str | None = None
    # Pricing & availability constraints that govern workflow feasibility.
    pricing_model: str = "fixed"  # fixed | hourly | percentage | custom
    min_objective_value_usdc: str | None = None
    min_role_compensation_usdc: str | None = None
    availability: str = "available"  # available | busy | offline
    max_concurrent: int = 5


class ReputationEventOut(BaseModel):
    id: str
    objective_id: str | None = None
    kind: str
    delta: float
    score_after: float
    note: str | None = None
    created_at: datetime


class AgentIdentityOut(BaseModel):
    id: str
    token_id: str  # on-chain-ready identity token (ERC-8004 agentId)
    owner: str
    name: str
    description: str | None = None
    capabilities: list[str]
    service_endpoints: list[dict]
    pricing: str | None = None
    discoverable: bool = True
    reputation_score: float
    jobs_completed: int
    jobs_failed: int
    rated: bool  # false until the agent has at least one outcome
    success_rate: float | None = None  # null until the agent has any outcome
    pricing_model: str = "fixed"
    min_objective_value_usdc: str | None = None
    min_role_compensation_usdc: str | None = None
    availability: str = "available"
    max_concurrent: int = 5
    metadata_uri: str | None = None
    registry_chain: str | None = None
    registry_address: str | None = None
    signing_pubkey: str | None = None  # public verifier; the secret is never exposed
    created_at: datetime


class ReputationDimension(BaseModel):
    """One independent axis of an agent's reputation, with its sample size.

    ``value`` is a 0..1 ratio, or null when the agent has no sample for that
    axis yet — so a thin or absent signal is never shown as a misleading zero.
    """

    key: str
    label: str
    value: float | None = None
    sample_size: int = 0
    hint: str | None = None


class AgentDetailOut(AgentIdentityOut):
    reputation_history: list[ReputationEventOut] = []
    trust_dimensions: list[ReputationDimension] = []


class FeedbackCommitIn(BaseModel):
    objective_id: str


class FeedbackCommitmentOut(BaseModel):
    id: str
    agent_id: str
    objective_id: str
    commitment_hash: str
    signature: str
    revealed: bool
    outcome: str | None = None
    created_at: datetime
    revealed_at: datetime | None = None


class FeedbackRevealIn(BaseModel):
    commitment_id: str
    success: bool
    note: str | None = None


class AssignAgentIn(BaseModel):
    agent_id: str  # AgentIdentity.id to assign as the objective's executor


# --- Trust API --------------------------------------------------------------


class TrustScoreOut(BaseModel):
    """Queryable reputation snapshot for any registered agent.

    Keyed by the on-chain-ready identity token so a counterparty can look up
    trust before transacting, without needing workspace credentials.
    """

    token_id: str
    name: str
    owner: str
    description: str | None = None
    pricing: str | None = None
    reputation_score: float
    jobs_completed: int
    jobs_failed: int
    total_jobs: int
    success_rate: float | None = None  # null until the agent has any outcome
    rated: bool
    capabilities: list[str] = []
    service_endpoints: list[dict] = []
    registry_chain: str | None = None
    registry_address: str | None = None
    last_outcome_at: datetime | None = None
    recent_events: list[ReputationEventOut] = []
    trust_dimensions: list["ReputationDimension"] = []


class AssignedAgentOut(BaseModel):
    """Compact agent reference embedded on an objective once assigned.

    Carries the live reputation read so the objective page reflects the trust
    score moving the moment a settlement folds the outcome back in.
    """

    id: str
    token_id: str
    name: str
    reputation_score: float
    jobs_completed: int
    jobs_failed: int
    rated: bool
    success_rate: float | None = None


# --- KPI analytics ----------------------------------------------------------


class KpiMetric(BaseModel):
    """Display-ready rendering of a single KPI for the analytics surface."""

    key: str
    label: str
    value: str  # formatted for display (already carries unit, e.g. "1,250 USDC")
    hint: str | None = None
    raw: float | None = None  # machine-readable value for charting/thresholds


class KpiOut(BaseModel):
    """Workspace KPI snapshot.

    Provider-agnostic, computed live from the lifecycle tables. ``metrics`` is
    the display-ready list; the explicit fields below are the raw, queryable
    values for programmatic consumers (dashboards, alerts, board reporting).
    """

    generated_at: datetime
    window: str = "all-time"

    # Governed Transaction Volume: gross USDC that passed through governed
    # settlement (net released + fees retained + value slashed).
    governed_transaction_volume_usdc: str

    # Mean Time to Settlement: average wall-clock from escrow lock to settlement.
    mean_time_to_settlement_seconds: float | None = None
    mean_time_to_settlement_human: str | None = None

    # Attestation Discrepancy Rate: share of audits where the human overrode the
    # AI attestation (0..1).
    attestation_discrepancy_rate: float

    # Active Escrow Accounts: escrow states currently locked.
    active_escrow_accounts: int

    # Take-Rate Drag: governed fees as a share of governed volume (0..1).
    take_rate_drag: float

    # Supporting counts / totals.
    settled_count: int
    slashed_count: int
    total_settlements: int
    fees_collected_usdc: str

    metrics: list[KpiMetric] = []


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
