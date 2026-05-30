"""Criteria satisfaction engine — the deterministic bridge from a success
criterion to the *specific evidence that satisfies it*.

This is the core of Brewing's differentiator: payment is authorized **because
recorded evidence satisfies predefined success criteria**, not because a status
flipped. The validation engine (`assess`) judges evidence *quality* in the
aggregate; this module is complementary and sharper — it answers, per criterion,
"was this met, and which piece of evidence proves it?". That mapping is what
makes the system able to answer *"why did this agent get paid?"* with a
verifiable trail.

Pure, deterministic, dependency-free. It never calls a model and never raises
into the settlement path — thin or missing evidence yields an *indeterminate*
verdict, never a crash.
"""

from __future__ import annotations

import re

# Verdict vocabulary, shared with the validation engine and Copilot evaluation.
APPROVED = "approved"
APPROVED_WITH_CONDITIONS = "approved_with_conditions"
REJECTED = "rejected"

# Tokens too common to carry meaning when matching a criterion to evidence.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
        "is", "are", "be", "been", "that", "this", "it", "as", "at", "by",
        "from", "must", "should", "shall", "will", "has", "have", "had", "all",
        "any", "each", "into", "than", "then", "via", "per", "no", "not", "if",
        "was", "were", "which", "what", "when", "where", "who", "whom", "its",
        "their", "they", "them", "we", "you", "your", "our", "can", "may",
        "ensure", "verify", "confirm", "check", "include", "included", "provide",
        "provided", "complete", "completed", "successfully", "correct",
        "correctly", "valid", "value", "values", "output", "outputs", "result",
        "results", "task", "objective", "step", "steps", "agent",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# When a criterion names an evidence modality, bias toward that evidence kind.
_KIND_HINTS = {
    "structured_api": ("api", "json", "endpoint", "payload", "response", "field", "schema", "status", "code"),
    "web_navigation": ("browser", "navigate", "click", "page", "url", "form", "checkout", "screenshot", "submit", "login"),
    "free_text": ("summary", "report", "write", "draft", "explanation", "prose", "document", "analysis"),
}


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in _TOKEN_RE.findall((text or "").lower())
        if len(t) >= 3 and t not in _STOPWORDS
    }


def normalize_criteria(raw: object) -> list[dict]:
    """Normalize heterogeneous criteria input into a stable structured shape.

    Accepts the legacy ``list[str]`` form *and* a structured ``list[dict]`` form
    so the engine works on today's data without a migration, while leaving room
    for richer criteria (explicit required evidence types, policy ids) later.

    Each result: ``{key, description, required_evidence_kind | None}``.
    """

    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            description = item.strip()
            if not description:
                continue
            out.append(
                {
                    "key": f"c{i + 1}",
                    "description": description,
                    "required_evidence_kind": _infer_required_kind(description),
                }
            )
        elif isinstance(item, dict):
            description = str(item.get("description") or item.get("criterion") or "").strip()
            if not description:
                continue
            out.append(
                {
                    "key": str(item.get("key") or f"c{i + 1}"),
                    "description": description,
                    "required_evidence_kind": item.get("required_evidence_kind")
                    or _infer_required_kind(description),
                }
            )
    return out


def _infer_required_kind(description: str) -> str | None:
    """Best-effort guess at the evidence modality a criterion implies.

    Deliberately conservative: only returns a kind when the criterion's wording
    clearly names one, so a generic criterion stays modality-agnostic and can be
    satisfied by any strong evidence.
    """

    toks = _tokens(description)
    best: tuple[str, int] | None = None
    for kind, hints in _KIND_HINTS.items():
        score = sum(1 for h in hints if h in toks)
        if score and (best is None or score > best[1]):
            best = (kind, score)
    return best[0] if best is not None else None


def _evidence_terms(ev: dict) -> set[str]:
    """All meaningful tokens an evidence item exposes for matching."""

    terms = _tokens(str(ev.get("step_title", "")))
    terms |= _tokens(str(ev.get("normalized_text", "")))
    signals = ev.get("signals") or {}
    for marker in signals.get("success_markers", []) or []:
        terms |= _tokens(str(marker))
    for key in signals.get("json_keys", []) or []:
        terms |= _tokens(str(key))
    return terms


def _supports(ev: dict) -> bool:
    """Whether an evidence item is strong enough to *positively* support a claim."""

    quality = ev.get("quality")
    has_error = bool((ev.get("signals") or {}).get("error_markers"))
    return quality == "strong" and not has_error


def evaluate_criterion(criterion: dict, evidence: list[dict]) -> dict:
    """Map one criterion to the recorded evidence that satisfies or fails it.

    Returns a structured result whose ``basis`` names the exact evidence steps
    (and the overlapping terms) that justify the verdict — the auditable "this is
    why" for a single criterion.
    """

    cterms = _tokens(criterion["description"])
    required_kind = criterion.get("required_evidence_kind")

    if not evidence:
        return {
            **_result_shell(criterion),
            "satisfied": None,
            "confidence": 0.2,
            "rationale": "No execution evidence was recorded for this criterion.",
            "basis": [],
        }

    basis: list[dict] = []
    error_conflict = False
    kind_present = False

    for ev in evidence:
        kind = ev.get("output_kind")
        if required_kind and kind == required_kind:
            kind_present = True
        overlap = sorted(cterms & _evidence_terms(ev)) if cterms else []
        relevant = bool(overlap) or (required_kind and kind == required_kind)
        if not relevant:
            continue
        if _supports(ev):
            basis.append(
                {
                    "step_index": ev.get("step_index"),
                    "step_title": ev.get("step_title"),
                    "output_kind": kind,
                    "quality": ev.get("quality"),
                    "matched_terms": overlap,
                }
            )
        elif (ev.get("signals") or {}).get("error_markers"):
            error_conflict = True

    # Decide the verdict deterministically.
    required_ok = (not required_kind) or kind_present
    if basis and required_ok:
        satisfied: bool | None = True
        term_strength = min(1.0, sum(len(b["matched_terms"]) for b in basis) / 4.0)
        confidence = round(min(0.97, 0.6 + 0.1 * len(basis) + 0.2 * term_strength), 2)
        rationale = (
            f"Satisfied by {len(basis)} strongly-evidenced step(s)"
            + (f" including required {required_kind} evidence" if required_kind else "")
            + "."
        )
    elif required_kind and not kind_present:
        satisfied = False
        confidence = 0.65
        rationale = (
            f"Requires {required_kind} evidence, which was not recorded."
        )
    elif error_conflict:
        satisfied = False
        confidence = 0.7
        rationale = "Relevant evidence carries error markers; criterion not met."
    elif cterms:
        satisfied = None
        confidence = 0.35
        rationale = "No recorded evidence clearly addresses this criterion."
    else:
        # Criterion has no matchable terms (e.g. one stopword); fall back to the
        # aggregate signal rather than asserting a verdict we can't justify.
        any_strong = any(_supports(ev) for ev in evidence)
        satisfied = True if any_strong else None
        confidence = 0.4
        rationale = (
            "Generic criterion; treated as met given strong overall evidence."
            if any_strong
            else "Generic criterion with no strong supporting evidence."
        )

    return {
        **_result_shell(criterion),
        "satisfied": satisfied,
        "confidence": confidence,
        "rationale": rationale,
        "basis": basis,
    }


def _result_shell(criterion: dict) -> dict:
    return {
        "key": criterion["key"],
        "description": criterion["description"],
        "required_evidence_kind": criterion.get("required_evidence_kind"),
    }


def evaluate_criteria(raw_criteria: object, evidence: list[dict]) -> list[dict]:
    """Evaluate every success criterion against the recorded evidence."""

    return [evaluate_criterion(c, evidence) for c in normalize_criteria(raw_criteria)]


def summarize_satisfaction(results: list[dict]) -> dict:
    """Roll per-criterion results into an evidence-derived settlement verdict.

    The verdict is *advisory to the human reviewer* but fully deterministic: it
    is the system's evidence-grounded recommendation for whether payment is
    warranted, and the basis for the "why was this paid" rationale.
    """

    total = len(results)
    satisfied = sum(1 for r in results if r["satisfied"] is True)
    failed = sum(1 for r in results if r["satisfied"] is False)
    indeterminate = sum(1 for r in results if r["satisfied"] is None)

    if total == 0:
        verdict = APPROVED_WITH_CONDITIONS
        headline = "No success criteria were defined; settlement cannot be evidence-gated."
    elif failed == 0 and indeterminate == 0:
        verdict = APPROVED
        headline = f"All {total} success criteria are satisfied by recorded evidence."
    elif satisfied == 0:
        verdict = REJECTED
        headline = "No success criteria are satisfied by the recorded evidence."
    elif failed > satisfied:
        verdict = REJECTED
        headline = (
            f"{failed} of {total} criteria fail against the evidence; "
            "more criteria fail than are satisfied."
        )
    else:
        verdict = APPROVED_WITH_CONDITIONS
        headline = (
            f"{satisfied} of {total} criteria are satisfied; "
            f"{failed} fail and {indeterminate} are indeterminate."
        )

    return {
        "total": total,
        "satisfied": satisfied,
        "failed": failed,
        "indeterminate": indeterminate,
        "all_satisfied": total > 0 and satisfied == total,
        "verdict": verdict,
        "headline": headline,
    }
