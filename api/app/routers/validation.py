"""Validation Registry API.

Exposes the read side of the independent validation layer: the registry of
validators a workspace relies on, their accuracy records, and the validation
outcomes they have produced. Kept deliberately separate from the agent identity
registry — trust in *who validates* is a distinct dimension from trust in *who
executes*, and the system's core invariant is that the two never collapse into
the same identity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.domain import validation
from app.models import Objective, User, Validator, ValidationRecord, Workspace
from app.schemas import ValidationFinding, ValidationRecordOut, ValidatorOut
from app.services import workspace as workspace_service

router = APIRouter(prefix="/validation", tags=["validation"])

_RECENT_LIMIT = 25


def current_workspace(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Workspace:
    return workspace_service.get_or_create_default_workspace(session, user)


def _validator_out(v: Validator) -> ValidatorOut:
    reconciled = v.upheld_count + v.overturned_count
    return ValidatorOut(
        id=v.id,
        validator_key=v.validator_key,
        name=v.name,
        kind=v.kind,
        description=v.description,
        independent=v.independent,
        active=v.active,
        validations_count=v.validations_count,
        upheld_count=v.upheld_count,
        overturned_count=v.overturned_count,
        accuracy=round(v.upheld_count / reconciled, 4) if reconciled else None,
        mean_confidence=v.mean_confidence,
        created_at=v.created_at,
    )


def _record_out(record: ValidationRecord, validator: Validator | None) -> ValidationRecordOut:
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
        validator=_validator_out(validator) if validator else None,
    )


@router.get("/validators", response_model=list[ValidatorOut])
def list_validators(
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> list[ValidatorOut]:
    validators = validation.list_validators(session, workspace.id)
    session.commit()
    return [_validator_out(v) for v in validators]


@router.get("/validators/{validator_id}", response_model=ValidatorOut)
def get_validator(
    validator_id: str,
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> ValidatorOut:
    validator = session.get(Validator, validator_id)
    if validator is None or validator.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Validator not found"
        )
    return _validator_out(validator)


@router.get("/records", response_model=list[ValidationRecordOut])
def list_records(
    workspace: Workspace = Depends(current_workspace),
    session: Session = Depends(get_session),
) -> list[ValidationRecordOut]:
    """Recent validation outcomes across this workspace's objectives."""

    records = session.exec(
        select(ValidationRecord)
        .join(Objective, Objective.id == ValidationRecord.objective_id)
        .where(Objective.workspace_id == workspace.id)
        .order_by(ValidationRecord.created_at.desc())
        .limit(_RECENT_LIMIT)
    ).all()
    validators = {v.id: v for v in session.exec(select(Validator)).all()}
    return [_record_out(r, validators.get(r.validator_id)) for r in records]
