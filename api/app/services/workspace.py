"""Identity & workspace bootstrap.

The API owns identity, authorization, and workspace permissions. On first
sign-in a user is upserted and given a default workspace, an owner membership,
and a treasury (a real Circle settlement wallet, provisioned best-effort).
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.domain.settlement import get_settlement_provider
from app.domain.settlement.provider import WalletRef
from app.models import Membership, Treasury, User, Workspace, WorkspaceRole

logger = logging.getLogger("brewing.workspace")


def upsert_user(
    session: Session, *, email: str, name: str | None, image: str | None
) -> tuple[User, bool]:
    """Return ``(user, is_new)``. ``is_new`` distinguishes a first-ever sign-in
    (account creation) from a returning sign-in — the signal the web app uses to
    branch the Sign Up vs Log In journey."""
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        user = User(email=email, name=name, image=image)
        session.add(user)
        session.flush()
        return user, True
    # Keep profile fields fresh from the identity provider.
    changed = False
    if name and user.name != name:
        user.name, changed = name, True
    if image and user.image != image:
        user.image, changed = image, True
    if changed:
        session.add(user)
    return user, False


def _provision_treasury(session: Session, workspace: Workspace) -> Treasury:
    """Create the workspace treasury row and provision its settlement wallet.

    Wallet provisioning is best-effort: a Circle hiccup must never block
    sign-in. If provisioning fails the treasury exists without a wallet and can
    be provisioned later on demand.
    """
    # Stamp the treasury with the configured provider's own name rather than a
    # hardcoded "circle", so the row stays accurate if the settlement provider
    # is ever swapped.
    provider = get_settlement_provider()
    treasury = Treasury(workspace_id=workspace.id, provider=provider.name)
    try:
        wallet: WalletRef = provider.provision_treasury_wallet(workspace.id)
        treasury.provider_wallet_id = wallet.provider_wallet_id
        treasury.address = wallet.address
        treasury.blockchain = wallet.blockchain
    except Exception as exc:  # noqa: BLE001 — provisioning is best-effort
        logger.warning("Treasury wallet provisioning deferred: %s", exc)
    session.add(treasury)
    session.flush()
    return treasury


def get_default_workspace(session: Session, user: User) -> Workspace | None:
    membership = session.exec(
        select(Membership).where(Membership.user_id == user.id)
    ).first()
    if membership is None:
        return None
    return session.get(Workspace, membership.workspace_id)


def get_or_create_default_workspace(session: Session, user: User) -> Workspace:
    existing = get_default_workspace(session, user)
    if existing is not None:
        return existing

    name = (user.name or user.email.split("@")[0]).strip()
    workspace = Workspace(name=f"{name}'s Workspace", owner_id=user.id)
    session.add(workspace)
    session.flush()

    session.add(
        Membership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.OWNER,
        )
    )
    _provision_treasury(session, workspace)
    return workspace


def get_role(session: Session, *, workspace_id: str, user_id: str) -> WorkspaceRole:
    membership = session.exec(
        select(Membership)
        .where(Membership.workspace_id == workspace_id)
        .where(Membership.user_id == user_id)
    ).first()
    return membership.role if membership else WorkspaceRole.VIEWER


def get_treasury(session: Session, workspace_id: str) -> Treasury | None:
    return session.exec(
        select(Treasury).where(Treasury.workspace_id == workspace_id)
    ).first()
