"""Brewing domain entities.

Everything orbits the Objective — the primary unit of coordination, not the
agent. The Objective lifecycle is the system's core state machine; every
transition emits a GovernanceEvent that feeds all observability.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Enums -----------------------------------------------------------------


class ObjectiveStatus(str, Enum):
    """The canonical objective lifecycle.

    Intent -> Governance -> Escrow -> Execution -> Validation -> Settlement.
    """

    DRAFT = "draft"
    COPILOT_STRUCTURED = "copilot_structured"
    ESCROW_LOCKED = "escrow_locked"
    EXECUTING = "executing"
    UNDER_AUDIT = "under_audit"
    GOVERNANCE_DECISION = "governance_decision"
    SETTLED = "settled"
    SLASHED = "slashed"
    DISPUTED = "disputed"


class WorkspaceRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    VIEWER = "viewer"


class EscrowStatus(str, Enum):
    # Transfer submitted to the settlement provider but not yet confirmed
    # on-chain. Funds are NOT in custody in this state — settlement must never
    # act on a PENDING escrow.
    PENDING = "pending"
    LOCKED = "locked"
    RELEASED = "released"
    SLASHED = "slashed"
    DISPUTED = "disputed"
    # The lock transfer was rejected / failed on-chain; no funds moved into
    # escrow. Terminal — the objective stays unfunded.
    FAILED = "failed"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    FAILED = "failed"
    ESCALATED = "escalated"


class SettlementStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    SLASHED = "slashed"


# --- Identity & workspace ---------------------------------------------------


class User(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str | None = None
    image: str | None = None
    created_at: datetime = Field(default_factory=_now)


class Workspace(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    name: str
    org_name: str | None = None
    operational_type: str | None = None
    owner_id: str = Field(foreign_key="user.id", index=True)
    # SaaS plan gating governance-dashboard access. Volume fees apply on top.
    subscription_tier: str = "free"
    # First-run onboarding gate. New workspaces start False and are walked
    # through Workspace + Treasury initialization before Mission Control opens.
    # Existing rows are backfilled True (already operational) — see app.db.
    onboarding_completed: bool = Field(default=False)
    # Governance defaults captured during onboarding; applied when the Copilot
    # structures an objective.
    governance_require_auditor: bool = Field(default=True)
    governance_human_authoritative: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_now)


class Membership(SQLModel, table=True):
    """Workspace permissions — authorization is enforced API-side."""

    id: str = Field(default_factory=_id, primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    role: WorkspaceRole = WorkspaceRole.OWNER
    created_at: datetime = Field(default_factory=_now)


class Treasury(SQLModel, table=True):
    """Isolated programmable settlement wallet for a workspace.

    Provider-agnostic: stores opaque provider references, not chain types.
    Balance is read live from the SettlementProvider, not stored as truth.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True, unique=True)
    provider: str = "circle"
    provider_wallet_id: str | None = None
    address: str | None = None
    blockchain: str | None = None
    created_at: datetime = Field(default_factory=_now)


# --- Objective & lifecycle --------------------------------------------------


class Objective(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True)
    created_by: str = Field(foreign_key="user.id")

    title: str
    intent: str  # raw operational intent the user expressed
    status: ObjectiveStatus = Field(default=ObjectiveStatus.DRAFT, index=True)
    summary: str | None = None

    # The agent identity executing this objective. When set, settlement
    # outcomes auto-update the agent's reputation in the registry.
    agent_id: str | None = Field(default=None, foreign_key="agentidentity.id", index=True)

    # Coordination architecture produced by the Copilot (provider-agnostic blobs).
    governance_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    sla_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    settlement_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    orchestration_plan: dict = Field(default_factory=dict, sa_column=Column(JSON))

    escrow_amount_usdc: str = "0"  # exact decimal stored as string

    # Operator-stated SLA. The Copilot still structures sla_config, but these are
    # what the *human* declared "done" means and by when — never overwritten by
    # structuring. `deadline` is free text (e.g. "48 hours" or a date) so an
    # operator can express either a duration or an absolute due date.
    definition_of_done: str | None = None
    deadline: str | None = None

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RoleStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowRole(SQLModel, table=True):
    """One sub-task (role) in an objective's multi-agent coordination graph.

    An objective decomposes into a coordination graph of 1..N sub-tasks
    (planner, research, analysis, executor, reviewer, validator, …). Each
    sub-task is assigned independently to an agent (or, in future, a human),
    carries its own success criteria, evidence requirements, settlement
    allocation, and dependency edges, and resolves through its **own**
    validation and settlement — enabling a dependency-ordered execution graph,
    independent per-sub-task settlement, and per-sub-task slashing.

    The parent objective settles only once every *required* sub-task has passed
    validation; non-required sub-tasks are advisory and never block the parent.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    order_index: int = 0
    role_key: str = "executor"  # planner|research|analysis|executor|reviewer|validator
    title: str
    description: str | None = None

    # Independently assignable. Null until an agent is bound to the sub-task.
    assigned_agent_id: str | None = Field(
        default=None, foreign_key="agentidentity.id", index=True
    )
    # Sub-task-level settlement allocation (exact USDC decimal as string).
    allocation_usdc: str = "0"

    # --- Coordination graph & sub-task contract -----------------------------
    # Ids of the sibling sub-tasks that must pass validation before this one is
    # *ready* to execute. The edge set defines the objective's dependency DAG;
    # an empty list means the sub-task has no prerequisites (a graph root).
    depends_on: list = Field(default_factory=list, sa_column=Column(JSON))
    # Per-sub-task success criteria (same shape the criteria engine accepts:
    # list[str] or list[dict]); the sub-task's evidence is judged against these.
    success_criteria: list = Field(default_factory=list, sa_column=Column(JSON))
    # Evidence modalities this sub-task must produce (structured_api |
    # web_navigation | free_text). Empty = modality-agnostic.
    required_evidence_kinds: list = Field(default_factory=list, sa_column=Column(JSON))
    # Whether the parent objective's settlement is gated on this sub-task.
    required: bool = True
    # Independent validation state for the sub-task: pending | passed | failed.
    validation_status: str = Field(default="pending", index=True)
    # Independent settlement state for the sub-task: pending | settled | slashed.
    settlement_status: str = Field(default="pending", index=True)

    status: RoleStatus = Field(default=RoleStatus.PENDING, index=True)
    # Sub-task-level settlement outcome, set when the sub-task settles:
    # "released" (paid to the assigned agent) or "slashed".
    outcome: str | None = None

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RoleAllocationChange(SQLModel, table=True):
    """Append-only history of a role's settlement-allocation edits.

    The Copilot proposes the initial budget-proportional split; users may
    re-weight roles before settlement. Every change is recorded so the
    allocation that ultimately settles is fully auditable.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    role_id: str = Field(foreign_key="workflowrole.id", index=True)
    from_usdc: str = "0"
    to_usdc: str = "0"
    actor: str | None = None
    created_at: datetime = Field(default_factory=_now)


class EscrowState(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    status: EscrowStatus = EscrowStatus.LOCKED
    amount_usdc: str = "0"

    provider: str = "circle"
    # Trust model for this escrow account: "custodial" (provider holds keys) or
    # "non_custodial" (tenant agentic wallet holds keys; Brewing never custodies).
    custody_model: str = "custodial"
    # The tenant agentic wallet with signing authority in the non-custodial
    # model. Null while the rail is custodial.
    controller_wallet: str | None = None
    provider_escrow_id: str | None = None
    address: str | None = None
    lock_tx_ref: str | None = None
    settle_tx_ref: str | None = None
    # On-chain signatures, resolved from the provider once confirmed. These make
    # the lock/release independently verifiable on a block explorer.
    lock_tx_hash: str | None = None
    settle_tx_hash: str | None = None

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ExecutionRun(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)


class ExecutionStep(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    run_id: str = Field(foreign_key="executionrun.id", index=True)
    index: int = 0
    title: str
    status: StepStatus = StepStatus.PENDING
    output: str | None = None  # produced artifact / result text
    created_at: datetime = Field(default_factory=_now)


class GovernanceEvaluation(SQLModel, table=True):
    """An advisory, AI-produced governance evaluation of an execution.

    The Coordination Copilot reviews recorded execution outputs against the
    governance validation criteria and recommends approve / approve-with-
    conditions / reject, with reasoning and per-criterion findings. It is
    advisory: the human AuditReview is authoritative and may override it.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    # When set, the evaluation is scoped to a single coordination sub-task rather
    # than the whole objective, so the Copilot reasons over a sub-task's own
    # success criteria. Null means it is the objective-level evaluation.
    role_id: str | None = Field(default=None, foreign_key="workflowrole.id", index=True)
    recommendation: str  # "approved" | "approved_with_conditions" | "rejected"
    reasoning: str = ""
    findings: list = Field(default_factory=list, sa_column=Column(JSON))
    conditions: list = Field(default_factory=list, sa_column=Column(JSON))
    # Advisory risk analysis: governance/financial/evidence risks the Copilot
    # surfaces even when it recommends approval. Each: {category, severity, detail}.
    risks: list = Field(default_factory=list, sa_column=Column(JSON))
    source: str = "copilot"  # model id or "heuristic"
    created_at: datetime = Field(default_factory=_now)


class AuditReview(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    status: AuditStatus = AuditStatus.PENDING
    notes: str | None = None
    reviewer_id: str | None = Field(default=None, foreign_key="user.id")
    # Link back to the AI evaluation the human acted on, and whether the human
    # overrode its recommendation. Authoritative decision stays human.
    evaluation_id: str | None = Field(default=None, foreign_key="governanceevaluation.id")
    recommendation: str | None = None  # recommendation present at decision time
    overridden: bool = False
    created_at: datetime = Field(default_factory=_now)


class GovernanceEvent(SQLModel, table=True):
    """The observable governance timeline. Append-only."""

    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    kind: str  # e.g. "objective.created", "escrow.locked", "audit.approved"
    message: str
    actor: str | None = None  # user id, "copilot", "governance-engine", etc.
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


# --- Independent validation layer & registry --------------------------------


class Validator(SQLModel, table=True):
    """An independent validation participant.

    Core invariant of the coordination network: execution must never equal
    validation. A Validator is a distinct identity from any executor agent — it
    inspects collected evidence and renders a governance recommendation it is
    accountable for. Accuracy (upheld vs. overturned against the authoritative
    human decision) accrues to the validator's own reputation, separate from
    agent execution reputation.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    # Null workspace == a network-level system validator shared across tenants.
    workspace_id: str | None = Field(default=None, foreign_key="workspace.id", index=True)
    # Stable, human-readable key (e.g. "evidence-integrity"); unique per scope.
    validator_key: str = Field(index=True)
    name: str
    kind: str = "evidence_engine"  # evidence_engine | policy_engine | human
    description: str | None = None
    # Independence flag: a validator is never permitted to be the executor.
    independent: bool = True
    active: bool = True

    # Validation accuracy cache (authoritative history is ValidationRecord).
    validations_count: int = 0
    upheld_count: int = 0  # decisions the authoritative governance decision kept
    overturned_count: int = 0  # decisions the human overrode
    mean_confidence: float = 0.0

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ValidationRecord(SQLModel, table=True):
    """An evidence-bound validation outcome for one objective.

    Captures the independent validator's recommendation, its confidence, and a
    cryptographic hash of the exact evidence it reasoned over so the validation
    is tamper-evident and auditable after the fact. Settlement and reputation
    both read from this; it is the formal bridge from execution evidence to
    governance recommendation.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    # When set, this validation is scoped to a single coordination sub-task
    # rather than the whole objective — so a sub-task validates independently.
    role_id: str | None = Field(default=None, foreign_key="workflowrole.id", index=True)
    validator_id: str = Field(foreign_key="validator.id", index=True)
    # Optional link to the advisory Copilot evaluation produced alongside it.
    evaluation_id: str | None = Field(default=None, foreign_key="governanceevaluation.id")

    recommendation: str  # approved | approved_with_conditions | rejected
    confidence: float = 0.0  # 0..1
    reasoning: str = ""
    findings: list = Field(default_factory=list, sa_column=Column(JSON))

    # Tamper-evident binding to the evidence reasoned over.
    evidence_hash: str = ""
    evidence_summary: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Independence proof: the executor whose work was validated, and the assertion
    # that the validator was not that executor.
    executor_agent_id: str | None = Field(default=None, foreign_key="agentidentity.id")
    independent_of_executor: bool = True

    # Final governance reconciliation, set when the human decision lands.
    outcome: str | None = None  # "approved" | "rejected"
    upheld: bool | None = None  # whether the authoritative decision matched

    created_at: datetime = Field(default_factory=_now)
    reconciled_at: datetime | None = None


# --- Agent identity registry (ERC-8004-shaped) -----------------------------


class AgentIdentity(SQLModel, table=True):
    """A registered agent's on-chain-ready identity token.

    Shaped to mirror an ERC-8004 Identity Registry entry: ``token_id`` is the
    deterministic on-chain agent id, ``owner`` is the controlling account, and
    ``metadata_uri`` points at a resolvable AgentCard (capabilities + service
    endpoints). The fields are DB-backed today and can be mirrored to an EVM
    registry without reshaping. Reputation history lives in ReputationEvent;
    the denormalized counters here are a fast read cache.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True)
    # Deterministic, unique on-chain-ready identity token id (ERC-8004 agentId).
    token_id: str = Field(index=True, unique=True)
    owner: str  # owner / agentic-wallet address holding signing authority
    name: str

    # --- Payout destination (Escrow V1.5) ----------------------------------
    # The wallet a release settles funds into. Distinct from `owner` so an agent
    # can be paid somewhere other than its signing-authority address. A payout
    # address is only usable as a settlement destination once the agent has
    # *proven control* of it by signing a challenge (see app.domain.payout);
    # `payout_address_verified` gates that. Settlement must never release to an
    # unverified address. All changes are recorded in PayoutAddressEvent.
    payout_address: str | None = None
    payout_blockchain: str | None = None  # chain context, e.g. "SOL-DEVNET"
    payout_address_verified: bool = Field(default=False)
    payout_address_verified_at: datetime | None = None
    # Outstanding proof-of-control challenge (single, one-time, time-boxed).
    payout_challenge: str | None = None
    payout_challenge_address: str | None = None
    payout_challenge_expires_at: datetime | None = None
    description: str | None = None  # what the agent does (marketplace listing)
    capabilities: list = Field(default_factory=list, sa_column=Column(JSON))
    service_endpoints: list = Field(default_factory=list, sa_column=Column(JSON))
    # Free-text pricing the developer advertises, e.g. "0.05 USDC / call".
    pricing: str | None = None
    # Whether the agent is listed as discoverable + hireable in the marketplace.
    discoverable: bool = Field(default=True, index=True)

    # Pricing & availability constraints that govern workflow feasibility. The
    # feasibility engine refuses to assign an agent to a role that violates these.
    pricing_model: str = "fixed"  # fixed | hourly | percentage | custom
    # Floor on the total objective value the agent will engage with.
    min_objective_value_usdc: str | None = None
    # Floor on the compensation the agent must receive from a single role.
    min_role_compensation_usdc: str | None = None
    availability: str = "available"  # available | busy | offline
    # Maximum concurrent objectives the agent will hold at once.
    max_concurrent: int = 5

    # Reputation read cache (authoritative history is ReputationEvent).
    reputation_score: float = 0.0  # 0..100; jobs_total == 0 means "unrated"
    jobs_completed: int = 0
    jobs_failed: int = 0

    # ERC-8004 mirroring pointers (null until mirrored on-chain).
    metadata_uri: str | None = None  # AgentCard URI
    registry_chain: str | None = None
    registry_address: str | None = None

    # Public verifier for blind-signature feedback. In production the private
    # key lives in the agent's agentic wallet and signs client-side; the MVP
    # stores a server-side signing secret (never exposed) to demonstrate the
    # sign-before-reveal flow. `signing_pubkey` is the derived public id.
    signing_secret: str | None = None
    signing_pubkey: str | None = None

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class PayoutAddressEvent(SQLModel, table=True):
    """Append-only audit trail of an agent's payout-address lifecycle.

    Every issue/verify/change/clear of a payout destination is recorded here, so
    the address that receives real funds is always traceable to who set it, when,
    and whether control was proven. A silent swap of the payout address right
    before settlement is therefore impossible without leaving an audited record.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    agent_id: str = Field(foreign_key="agentidentity.id", index=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True)
    # "challenge_issued" | "registered" | "changed" | "verification_failed" | "cleared"
    action: str
    old_address: str | None = None
    new_address: str | None = None
    verified: bool = False  # whether control was proven by this event
    actor: str | None = None  # user id that initiated the change
    note: str | None = None
    created_at: datetime = Field(default_factory=_now)


class ReputationEvent(SQLModel, table=True):
    """Append-only reputation history for an agent identity."""

    id: str = Field(default_factory=_id, primary_key=True)
    agent_id: str = Field(foreign_key="agentidentity.id", index=True)
    objective_id: str | None = Field(default=None, foreign_key="objective.id")
    kind: str  # "job.completed" | "job.failed" | "feedback.revealed"
    delta: float = 0.0  # contribution toward the score
    score_after: float = 0.0
    note: str | None = None
    created_at: datetime = Field(default_factory=_now)


class FeedbackCommitment(SQLModel, table=True):
    """Blind-signature feedback commitment.

    The agent signs a commitment *before* the evaluation outcome is revealed,
    binding it to the feedback regardless of result. This prevents selective
    participation in only positive reviews: the signature is captured at commit
    time, so an agent cannot decline once it sees a negative outcome.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    agent_id: str = Field(foreign_key="agentidentity.id", index=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    nonce: str
    commitment_hash: str  # blinded hash bound at commit time (no outcome inside)
    signature: str  # agent signature over commitment_hash, captured pre-reveal
    revealed: bool = False
    outcome: str | None = None  # "success" | "failure", set only at reveal
    created_at: datetime = Field(default_factory=_now)
    revealed_at: datetime | None = None


class SettlementAuthorization(SQLModel, table=True):
    """The evidence-grounded authorization to settle an objective.

    Answers *"why was this agent paid?"* deterministically. Where the
    ValidationRecord judges evidence *quality* in aggregate, this artifact maps
    each predefined success criterion to the specific recorded evidence that
    satisfies or fails it, binds that mapping to the exact ``evidence_hash`` the
    independent validator reasoned over, and records the evidence-derived
    verdict alongside the authoritative human decision.

    Payment is authorized **because recorded evidence satisfies predefined
    success criteria** — not because a status flipped. The per-criterion
    ``criteria_results`` is the auditable "this is why" trail; ``evidence_hash``
    makes it tamper-evident.
    """

    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    # When set, the authorization justifies settling a single coordination
    # sub-task; null means it authorizes the parent objective as a whole.
    role_id: str | None = Field(default=None, foreign_key="workflowrole.id", index=True)

    # Tamper-evident binding to the exact evidence reasoned over. Matches the
    # ValidationRecord's hash when the underlying evidence is unchanged, proving
    # the authorization and the validation judged the same artifact.
    evidence_hash: str = ""

    # Per-criterion satisfaction results (key/description/satisfied/confidence/
    # rationale/basis) and their roll-up counts.
    criteria_results: list = Field(default_factory=list, sa_column=Column(JSON))
    criteria_total: int = 0
    criteria_satisfied: int = 0
    criteria_failed: int = 0
    criteria_indeterminate: int = 0

    # The evidence-derived verdict, independent of the human decision:
    # "approved" | "approved_with_conditions" | "rejected".
    evidence_verdict: str = "approved_with_conditions"
    headline: str = ""

    # The authoritative human governance decision this was reconciled against.
    governance_approved: bool | None = None
    # Whether the human decision agreed with the evidence-derived verdict.
    aligned_with_evidence: bool | None = None
    # Final authorization: True when settlement is authorized to release funds.
    authorized: bool | None = None

    created_at: datetime = Field(default_factory=_now)


class Settlement(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    # When set, this is an independent settlement of a single coordination
    # sub-task (its allocation), not the parent objective's settlement.
    role_id: str | None = Field(default=None, foreign_key="workflowrole.id", index=True)
    status: SettlementStatus = SettlementStatus.PENDING
    amount_usdc: str = "0"
    fee_usdc: str = "0"  # hybrid volume fee (tiered, $0.001 micro-fee floor)
    fee_basis: str | None = None  # which tier applied, e.g. "0.5% volume tier"
    payout_tx_ref: str | None = None
    payout_tx_hash: str | None = None  # resolved on-chain signature
    created_at: datetime = Field(default_factory=_now)
