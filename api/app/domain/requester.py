"""Requester-side reputation — the second half of two-sided trust.

Executor reputation (registry/ReputationEvent) answers "can this agent be
trusted to deliver?". This answers the mirror question the network also needs:
"can this requester be trusted to pay for work that was actually done?".

The defining bad-faith move is rejecting work the *independent* validator passed
in order to reclaim escrow and use the deliverable for free. Settlement already
makes that unprofitable (escrow is held, then either released to the executor or
slashed to the neutral pool — never refunded). This module makes it *reputational*
as well: a rejection an arbiter overturns ("dispute_lost") is the strong negative
signal; settling in good faith repairs the score.

Pure and side-effect-light: mutates the Workspace counters + cached score and
flushes. Never raises into the settlement path.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models import Workspace

SETTLED = "settled"
DISPUTE_RAISED = "dispute_raised"
DISPUTE_LOST = "dispute_lost"
DISPUTE_UPHELD = "dispute_upheld"


def compute_score(*, settled: int, disputes_lost: int, disputes_upheld: int) -> float:
    """Good-faith score in 0..100.

    A *concluded* interaction with an executor is one that ended in payment, an
    overturned rejection, or an upheld rejection. Only ``disputes_lost`` —
    rejections an arbiter overturned — count as bad faith. With nothing concluded
    the requester is unrated and sits at 100 (clean by default, like an unrated
    executor).
    """

    concluded = settled + disputes_lost + disputes_upheld
    if concluded <= 0:
        return 100.0
    bad_faith_rate = disputes_lost / concluded
    return round(100.0 * (1.0 - bad_faith_rate), 1)


def record_outcome(session: Session, workspace_id: str, kind: str) -> Workspace | None:
    """Increment the relevant counter and recompute the cached good-faith score.

    Best-effort: an unknown kind or missing workspace is a no-op (this is wired
    into the settlement path and must never break it).
    """

    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        return None

    if kind == SETTLED:
        workspace.objectives_settled += 1
    elif kind == DISPUTE_RAISED:
        workspace.disputes_raised += 1
    elif kind == DISPUTE_LOST:
        workspace.disputes_lost += 1
    elif kind == DISPUTE_UPHELD:
        workspace.disputes_upheld += 1
    else:
        return workspace

    workspace.requester_reputation_score = compute_score(
        settled=workspace.objectives_settled,
        disputes_lost=workspace.disputes_lost,
        disputes_upheld=workspace.disputes_upheld,
    )
    session.add(workspace)
    session.flush()
    return workspace
