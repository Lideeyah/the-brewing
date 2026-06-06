"""User-submitted product feedback / support requests."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.auth import get_current_user
from app.db import get_session
from app.models import Feedback, User
from app.schemas import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/feedback", tags=["feedback"])

_CATEGORIES = {"general", "bug", "feature", "support"}


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    body: FeedbackCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> FeedbackOut:
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feedback message is required.",
        )
    category = body.category if body.category in _CATEGORIES else "general"
    fb = Feedback(
        user_id=user.id,
        email=user.email,
        name=user.name,
        category=category,
        message=message[:4000],
    )
    session.add(fb)
    session.commit()
    session.refresh(fb)
    return FeedbackOut(
        id=fb.id,
        email=fb.email,
        name=fb.name,
        category=fb.category,
        message=fb.message,
        status=fb.status,
        created_at=fb.created_at,
    )
