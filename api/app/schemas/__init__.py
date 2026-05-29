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


class ObjectiveDetailOut(ObjectiveOut):
    governance_config: dict
    sla_config: dict
    settlement_config: dict
    orchestration_plan: dict
    timeline: list[GovernanceEventOut]


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
