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
    onboarding_completed: bool = False
    governance_require_auditor: bool = True
    governance_human_authoritative: bool = True
    auto_settle_enabled: bool = False
    auto_settle_max_usdc: str | None = None
    auto_settle_min_confidence: float = 0.85
    treasury_address: str | None = None
    treasury_blockchain: str | None = None


class WorkspaceUpdateIn(BaseModel):
    """Onboarding Workspace Initialization — name the operational environment
    and set its governance defaults. All fields optional/idempotent."""

    name: str | None = None
    org_name: str | None = None
    operational_type: str | None = None
    governance_require_auditor: bool | None = None
    governance_human_authoritative: bool | None = None
    auto_settle_enabled: bool | None = None
    auto_settle_max_usdc: str | None = None
    auto_settle_min_confidence: float | None = None


class SessionOut(BaseModel):
    token: str
    user: UserOut
    workspace: WorkspaceOut
    role: WorkspaceRole
    # First-ever sign-in for this identity — drives the Sign Up vs Log In
    # journey on the web side. The onboarding gate (workspace.onboarding_completed)
    # remains the server-side source of truth for routing.
    is_new_account: bool = False


class MeOut(BaseModel):
    user: UserOut
    workspace: WorkspaceOut
    role: WorkspaceRole


# --- Objectives -------------------------------------------------------------


class ObjectiveCreate(BaseModel):
    intent: str
    title: str | None = None
    # Optional operator-set budget in USDC. When provided it becomes the escrow
    # amount and the Copilot structures the workflow within it; when omitted the
    # Copilot recommends a budget at structure time.
    budget_usdc: str | None = None
    # Optional operator-stated SLA: what "done" means and by when.
    definition_of_done: str | None = None
    deadline: str | None = None


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


class SourceProof(BaseModel):
    """A source an agent actually fetched during execution (proof-of-work)."""

    url: str
    ok: bool = False
    status: int | None = None
    title: str | None = None
    sha256: str | None = None
    bytes: int | None = None
    fetched_at: str | None = None


class ExecutionRunOut(BaseModel):
    id: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    deliverable: str | None = None
    sources: list[SourceProof] = []
    steps: list[ExecutionStepOut]


class GovernanceFinding(BaseModel):
    criterion: str
    met: bool
    assessment: str | None = None


class GovernanceRisk(BaseModel):
    """An advisory risk the Copilot flags during governance evaluation.

    Risks are surfaced even on an "approved" recommendation — they are
    governance intelligence, not a veto. ``category`` and ``severity`` are
    constrained vocabularies the client maps to tone.
    """

    category: str  # evidence | financial | governance | execution | compliance
    severity: str  # low | medium | high
    detail: str


class GovernanceEvaluationOut(BaseModel):
    id: str
    role_id: str | None = None  # set when the evaluation scopes a sub-task
    recommendation: str  # approved | approved_with_conditions | rejected
    reasoning: str
    findings: list[GovernanceFinding]
    risks: list[GovernanceRisk] = []
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


class CriterionBasisOut(BaseModel):
    """One evidence step that supports a satisfied criterion."""

    step_index: int | None = None
    step_title: str | None = None
    output_kind: str | None = None
    quality: str | None = None
    matched_terms: list[str] = []


class CriterionResultOut(BaseModel):
    """The verdict for one success criterion against the recorded evidence."""

    key: str
    description: str
    required_evidence_kind: str | None = None
    satisfied: bool | None = None  # True | False | None (indeterminate)
    confidence: float = 0.0
    rationale: str = ""
    basis: list[CriterionBasisOut] = []


class SettlementAuthorizationOut(BaseModel):
    """Evidence-grounded authorization answering "why was this agent paid?"."""

    id: str
    objective_id: str
    role_id: str | None = None  # set when scoped to a coordination sub-task
    evidence_hash: str
    criteria_results: list[CriterionResultOut] = []
    criteria_total: int = 0
    criteria_satisfied: int = 0
    criteria_failed: int = 0
    criteria_indeterminate: int = 0
    evidence_verdict: str  # approved | approved_with_conditions | rejected
    headline: str = ""
    governance_approved: bool | None = None
    aligned_with_evidence: bool | None = None
    authorized: bool | None = None
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


class EvidenceTrailItem(BaseModel):
    """One normalized execution output, annotated with what it grounds.

    Ties a single piece of evidence forward to the success criteria it supports
    (via the authorization's per-criterion basis) and flags whether the
    independent validator surfaced an error on it — so the chain from raw output
    to settlement is legible per step.
    """

    step_index: int
    step_title: str
    status: str
    output_kind: str
    quality: str
    has_errors: bool = False
    snippet: str = ""
    supports_criteria: list[str] = []  # criterion descriptions grounded here
    validation_flagged: bool = False  # validator surfaced a finding on this step


class EvidenceTrailStage(BaseModel):
    """One link in the output→evidence→validation→authorization→settlement chain."""

    key: str  # output | evidence | validation | authorization | settlement
    label: str
    complete: bool
    detail: str = ""


class EvidenceTrailOut(BaseModel):
    """Human-readable audit trail binding execution evidence to settlement.

    The ``evidence_hash`` is the cryptographic anchor the independent validator
    bound and the settlement authorization re-derived; ``hash_consistent``
    asserts those two hashes match — i.e. the agent was authorized against the
    exact evidence that was validated.
    """

    evidence_hash: str | None = None
    hash_consistent: bool = False
    items: list[EvidenceTrailItem] = []
    stages: list[EvidenceTrailStage] = []
    criteria_total: int = 0
    criteria_satisfied: int = 0


class WalletMovement(BaseModel):
    """One on-chain movement of capital within an objective's lifecycle.

    Each lock, release, or slash is a real USDC transfer between named wallets.
    ``tx_hash`` + ``tx_url`` expose the independently verifiable proof; until the
    provider confirms a signature the movement is shown as ``confirmed=False`` so
    a not-yet-final hop is visible rather than hidden.
    """

    kind: str  # lock | release | slash
    label: str
    amount_usdc: str
    direction: str  # inbound | outbound (relative to escrow custody)
    from_label: str | None = None
    from_address: str | None = None
    to_label: str | None = None
    to_address: str | None = None
    to_explorer_url: str | None = None
    tx_hash: str | None = None
    tx_url: str | None = None
    tx_ref: str | None = None
    confirmed: bool = False
    role_id: str | None = None  # set for per-sub-task movements
    role_title: str | None = None
    occurred_at: datetime


class OnChainLedger(BaseModel):
    """The full on-chain money trail for an objective.

    Aggregates the escrow lock and every settlement (objective-level and
    per-sub-task) into a single ordered movement ledger with explorer links and
    running totals, so capital movement is legible in one place.
    """

    blockchain: str | None = None
    treasury_address: str | None = None
    treasury_explorer_url: str | None = None
    escrow_address: str | None = None
    escrow_explorer_url: str | None = None
    movements: list[WalletMovement] = []
    total_locked_usdc: str = "0"
    total_released_usdc: str = "0"
    total_slashed_usdc: str = "0"
    total_fees_usdc: str = "0"
    confirmed_count: int = 0
    pending_count: int = 0


class AuditDecision(BaseModel):
    """Governance validation decision applied to a completed execution."""

    decision: str = "approve"  # "approve" | "reject"
    notes: str | None = None


# --- Multi-agent workflow ---------------------------------------------------


class WorkflowRoleOut(BaseModel):
    """One independently assignable sub-task in an objective's coordination graph.

    Beyond assignment + allocation, a sub-task carries its own coordination
    contract — dependency edges, success criteria, required evidence kinds — and
    its own validation + settlement state, plus the evidence-grounded
    authorization and settlement record produced when it resolves independently.
    """

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
    deliverable: str | None = None  # this role/agent's produced contribution

    # --- Coordination contract & sub-task state -----------------------------
    depends_on: list[str] = []  # sibling role ids that must pass first
    success_criteria: list = []  # per-sub-task criteria (str or dict)
    required_evidence_kinds: list[str] = []
    required: bool = True  # whether the parent settle is gated on this sub-task
    validation_status: str = "pending"  # pending | passed | failed
    settlement_status: str = "pending"  # pending | settled | slashed
    # The per-sub-task "why was this paid?" artifact + settlement, when resolved.
    authorization: "SettlementAuthorizationOut | None" = None
    settlement: "SettlementOut | None" = None
    # Advisory Copilot evaluation scoped to this sub-task's own criteria.
    evaluation: "GovernanceEvaluationOut | None" = None


class CoordinationNodeOut(BaseModel):
    """A sub-task as a node in the execution DAG (graph-derived view)."""

    role_id: str
    role_key: str
    title: str
    order_index: int
    wave: int | None = None  # topological execution layer (0 = no prerequisites)
    depends_on: list[str] = []
    required: bool = True
    allocation_usdc: str = "0"
    assigned_agent_id: str | None = None
    validation_status: str = "pending"
    settlement_status: str = "pending"
    # ready | blocked | blocked_failed | cycle — derived from dependency outcomes.
    dependency_state: str = "ready"
    ready: bool = False  # dependencies satisfied and not yet validated


class CoordinationEdgeOut(BaseModel):
    from_role: str
    to_role: str


class CoordinationGraphOut(BaseModel):
    """The objective's sub-task dependency DAG, execution order, and settle gate."""

    nodes: list[CoordinationNodeOut] = []
    edges: list[CoordinationEdgeOut] = []
    waves: list[list[str]] = []  # role ids grouped by execution wave
    has_cycle: bool = False
    cycle_role_ids: list[str] = []
    required_total: int = 0
    required_passed: int = 0
    required_failed: int = 0
    parent_settleable: bool = False  # gate: all required sub-tasks passed


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
    definition_of_done: str | None = None
    deadline: str | None = None
    settlement_config: dict
    orchestration_plan: dict
    timeline: list[GovernanceEventOut]
    escrow: EscrowOut | None = None
    treasury_address: str | None = None
    execution: ExecutionRunOut | None = None
    evaluation: GovernanceEvaluationOut | None = None
    validation: "ValidationRecordOut | None" = None
    audit: AuditReviewOut | None = None
    authorization: "SettlementAuthorizationOut | None" = None
    settlement: SettlementOut | None = None
    assigned_agent: "AssignedAgentOut | None" = None
    workflow: list["WorkflowRoleOut"] = []
    coordination: "CoordinationGraphOut | None" = None
    feasibility: "FeasibilityReport | None" = None
    evidence_trail: "EvidenceTrailOut | None" = None
    onchain_ledger: "OnChainLedger | None" = None


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
    # Payout destination (Escrow V1.5). Only a *verified* address is ever used as
    # a settlement destination; `payout_address_verified` reflects proof-of-control.
    payout_address: str | None = None
    payout_blockchain: str | None = None
    payout_address_verified: bool = False
    payout_address_verified_at: datetime | None = None
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


class PayoutAddressEventOut(BaseModel):
    id: str
    action: str  # challenge_issued | registered | changed | verification_failed | cleared
    old_address: str | None = None
    new_address: str | None = None
    verified: bool = False
    actor: str | None = None
    note: str | None = None
    created_at: datetime


class AgentDetailOut(AgentIdentityOut):
    reputation_history: list[ReputationEventOut] = []
    trust_dimensions: list[ReputationDimension] = []
    payout_history: list[PayoutAddressEventOut] = []


class PayoutChallengeIn(BaseModel):
    address: str  # candidate payout wallet (Solana base58 address)
    blockchain: str | None = None  # optional chain context, e.g. "SOL-DEVNET"


class PayoutChallengeOut(BaseModel):
    """The string the agent's wallet must sign to prove control of `address`."""

    agent_id: str
    address: str
    challenge: str
    expires_at: datetime


class PayoutVerifyIn(BaseModel):
    # ed25519 signature over the issued challenge, base58 or hex encoded.
    signature: str


class FeedbackCommitIn(BaseModel):
    objective_id: str


class FeedbackCommitmentOut(BaseModel):
    id: str
    agent_id: str
    objective_id: str
    objective_title: str | None = None  # resolved for readable display
    commitment_hash: str
    signature: str
    revealed: bool
    outcome: str | None = None
    created_at: datetime
    revealed_at: datetime | None = None


class FeedbackObjectiveOption(BaseModel):
    """An objective the agent contributed to — a candidate for feedback.

    Surfaced so the commit step can present a pick-list instead of asking for a
    raw objective id. ``committed`` marks ones that already carry a commitment.
    """

    id: str
    title: str
    status: str
    committed: bool


class AgentFeedbackOut(BaseModel):
    """Read model for the blind-signature feedback flow on one agent.

    ``commitments`` is the audit trail (committed and revealed); ``objectives``
    is the pick-list of associated objectives still available to commit on.
    """

    commitments: list[FeedbackCommitmentOut]
    objectives: list[FeedbackObjectiveOption]


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


# --- Feedback & admin -------------------------------------------------------


class FeedbackCreate(BaseModel):
    message: str
    category: str = "general"  # general | bug | feature | support


class FeedbackOut(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None
    category: str
    message: str
    status: str
    created_at: datetime


class AdminRecentObjective(BaseModel):
    id: str
    title: str
    status: str
    workspace: str | None = None
    created_at: datetime


class AdminRecentSettlement(BaseModel):
    objective_id: str
    status: str
    amount_usdc: str
    fee_usdc: str
    created_at: datetime


class AdminOverviewOut(BaseModel):
    users_total: int
    users_new_30d: int
    workspaces_total: int
    objectives_total: int
    objectives_by_status: dict[str, int]
    agents_total: int
    settled_usdc_total: str
    fees_usdc_total: str  # platform revenue (lifetime, recorded)
    settlements_count: int
    recent_objectives: list[AdminRecentObjective]
    recent_settlements: list[AdminRecentSettlement]
    # Platform revenue wallet — where swept fees actually land.
    platform_fee_wallet_address: str | None = None
    platform_fee_balance_usdc: str | None = None  # live on-chain balance


class AdminDisputeOut(BaseModel):
    """A held dispute awaiting arbiter resolution."""

    objective_id: str
    title: str
    workspace: str | None = None
    workspace_id: str
    held_usdc: str
    validator_recommendation: str | None = None
    validator_confidence: float | None = None
    reviewer_rationale: str | None = None
    requester_reputation_score: float | None = None
    disputes_raised: int = 0
    disputes_lost: int = 0
    created_at: datetime


class AdminDisputeResolveIn(BaseModel):
    # "release" → pay the executor (validator upheld); "uphold_rejection" →
    # slash held escrow to the neutral pool (rejection stands).
    resolution: str
    rationale: str | None = None


class AdminDisputeResolveOut(BaseModel):
    ok: bool
    objective_id: str
    resolution: str
    outcome_status: str  # resulting objective status
    amount_usdc: str
    explorer_url: str | None = None
    requester_reputation_score: float | None = None
    message: str | None = None


class FeeWithdrawIn(BaseModel):
    destination_address: str
    amount_usdc: str | None = None  # omit to withdraw the full balance


class FeeWithdrawOut(BaseModel):
    ok: bool
    amount_usdc: str
    destination_address: str
    explorer_url: str | None = None
    message: str | None = None
