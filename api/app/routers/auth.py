"""Identity exchange + session validation.

Web owns the sign-in UX; after a verified OAuth/email sign-in it calls
`POST /auth/session` (server-side only, authenticated with the shared web
secret) to exchange the identity for a canonical Brewing session token. Every
other protected route validates that token via `get_current_user`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session

from app.auth import create_session_token, get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import Treasury, User, Workspace
from app.schemas import (
    MeOut,
    SessionExchangeRequest,
    SessionOut,
    UserOut,
    WorkspaceOut,
)
from app.services import workspace as workspace_service

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def require_web_secret(x_brewing_auth: str | None = Header(default=None)) -> None:
    """Trust boundary: only the web server (which shares SESSION_SECRET) may
    mint sessions. The secret never reaches the browser."""
    if not x_brewing_auth or x_brewing_auth != settings.session_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorized to exchange identity",
        )


def _workspace_out(workspace: Workspace, treasury: Treasury | None) -> WorkspaceOut:
    return WorkspaceOut(
        id=workspace.id,
        name=workspace.name,
        org_name=workspace.org_name,
        operational_type=workspace.operational_type,
        treasury_address=treasury.address if treasury else None,
        treasury_blockchain=treasury.blockchain if treasury else None,
    )


@router.post("/session", response_model=SessionOut)
def exchange_session(
    body: SessionExchangeRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_web_secret),
) -> SessionOut:
    user = workspace_service.upsert_user(
        session, email=body.email, name=body.name, image=body.image
    )
    workspace = workspace_service.get_or_create_default_workspace(session, user)
    role = workspace_service.get_role(
        session, workspace_id=workspace.id, user_id=user.id
    )
    treasury = workspace_service.get_treasury(session, workspace.id)
    session.commit()

    return SessionOut(
        token=create_session_token(user.id),
        user=UserOut(id=user.id, email=user.email, name=user.name, image=user.image),
        workspace=_workspace_out(workspace, treasury),
        role=role,
    )


@router.get("/me", response_model=MeOut)
def me(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MeOut:
    workspace = workspace_service.get_or_create_default_workspace(session, user)
    role = workspace_service.get_role(
        session, workspace_id=workspace.id, user_id=user.id
    )
    treasury = workspace_service.get_treasury(session, workspace.id)
    session.commit()
    return MeOut(
        user=UserOut(id=user.id, email=user.email, name=user.name, image=user.image),
        workspace=_workspace_out(workspace, treasury),
        role=role,
    )
