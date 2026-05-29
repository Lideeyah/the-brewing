"""Session validation. The API is the identity source of truth.

Web owns the authentication UX (OAuth/email screens). After a successful
sign-in, web exchanges the verified identity for a canonical Brewing session
token issued here. Every protected route validates that token via
`get_current_user`, and authorization/workspace permissions are enforced
API-side — never trusted from the client.
"""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session

settings = get_settings()

SESSION_TTL = timedelta(days=7)


def create_session_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + SESSION_TTL).timestamp()),
    }
    return jwt.encode(
        payload, settings.session_secret, algorithm=settings.session_algorithm
    )


def _decode(token: str) -> str:
    try:
        payload = jwt.decode(
            token, settings.session_secret, algorithms=[settings.session_algorithm]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    return user_id


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
):
    from app.models import User

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session"
        )
    token = authorization.split(" ", 1)[1]
    user_id = _decode(token)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown identity"
        )
    return user
