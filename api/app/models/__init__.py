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
    LOCKED = "locked"
    RELEASED = "released"
    SLASHED = "slashed"
    DISPUTED = "disputed"


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

    # Coordination architecture produced by the Copilot (provider-agnostic blobs).
    governance_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    sla_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    settlement_config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    orchestration_plan: dict = Field(default_factory=dict, sa_column=Column(JSON))

    escrow_amount_usdc: str = "0"  # exact decimal stored as string

    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


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
    recommendation: str  # "approved" | "approved_with_conditions" | "rejected"
    reasoning: str = ""
    findings: list = Field(default_factory=list, sa_column=Column(JSON))
    conditions: list = Field(default_factory=list, sa_column=Column(JSON))
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
    capabilities: list = Field(default_factory=list, sa_column=Column(JSON))
    service_endpoints: list = Field(default_factory=list, sa_column=Column(JSON))

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


class Settlement(SQLModel, table=True):
    id: str = Field(default_factory=_id, primary_key=True)
    objective_id: str = Field(foreign_key="objective.id", index=True)
    status: SettlementStatus = SettlementStatus.PENDING
    amount_usdc: str = "0"
    fee_usdc: str = "0"  # hybrid volume fee (tiered, $0.001 micro-fee floor)
    fee_basis: str | None = None  # which tier applied, e.g. "0.5% volume tier"
    payout_tx_ref: str | None = None
    payout_tx_hash: str | None = None  # resolved on-chain signature
    created_at: datetime = Field(default_factory=_now)
