"""Governance timeline — the system's observable record of truth.

Every meaningful objective state transition appends a GovernanceEvent. The
timeline is append-only and drives all observability surfaces (dashboard,
auditor, objective detail).
"""

from __future__ import annotations

from sqlmodel import Session

from app.models import GovernanceEvent


def log_event(
    session: Session,
    *,
    objective_id: str,
    kind: str,
    message: str,
    actor: str | None = None,
    data: dict | None = None,
) -> GovernanceEvent:
    event = GovernanceEvent(
        objective_id=objective_id,
        kind=kind,
        message=message,
        actor=actor,
        data=data or {},
    )
    session.add(event)
    return event
