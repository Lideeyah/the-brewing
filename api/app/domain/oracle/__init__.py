"""SLA oracle — validation layer for unstructured task outputs.

The governance auditor must evaluate outputs that are *not* clean API
responses: browser-operating agents produce navigation transcripts, DOM
snippets, screenshot references, and free-form prose. This module classifies
each execution output, extracts salient signals (URLs visited, success/error
markers, extracted fields), and renders an auditor-readable normalization so
the evaluation step can reason over messy, real-world evidence rather than
assuming structured JSON.

Pure, deterministic, dependency-free: it runs before (and independently of)
the model-based evaluation and degrades gracefully on anything it can't parse.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Output kinds the oracle recognizes.
STRUCTURED_API = "structured_api"
WEB_NAVIGATION = "web_navigation"
FREE_TEXT = "free_text"
EMPTY = "empty"

_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
_SUCCESS_MARKERS = (
    "success",
    "completed",
    "complete",
    "done",
    "confirmed",
    "submitted",
    "approved",
    "200 ok",
    "checkout complete",
    "order placed",
)
_ERROR_MARKERS = (
    "error",
    "failed",
    "failure",
    "timeout",
    "timed out",
    "exception",
    "captcha",
    "blocked",
    "denied",
    "not found",
    "403",
    "404",
    "500",
    "could not",
    "unable to",
)
# Verbs/nouns typical of a browser-operating agent transcript.
_WEB_MARKERS = (
    "navigat",
    "clicked",
    "click ",
    "typed",
    "selector",
    "screenshot",
    "page ",
    "dom",
    "scroll",
    "element",
    "button",
    "input field",
    "url:",
    "loaded",
    "xpath",
)


@dataclass
class Evidence:
    """Normalized, auditor-readable view of one execution output."""

    step_index: int
    step_title: str
    status: str
    output_kind: str
    normalized_text: str
    signals: dict = field(default_factory=dict)
    quality: str = "unknown"  # "strong" | "weak" | "contradictory" | "missing"

    def to_dict(self) -> dict:
        return {
            "step_index": self.step_index,
            "step_title": self.step_title,
            "status": self.status,
            "output_kind": self.output_kind,
            "normalized_text": self.normalized_text,
            "signals": self.signals,
            "quality": self.quality,
        }


def _try_json(raw: str):
    raw = raw.strip()
    if not (raw.startswith("{") or raw.startswith("[")):
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def classify_output(raw: str | None) -> str:
    if not raw or not raw.strip():
        return EMPTY
    if _try_json(raw) is not None:
        return STRUCTURED_API
    lowered = raw.lower()
    web_hits = sum(1 for m in _WEB_MARKERS if m in lowered)
    if web_hits >= 2 or (_URL_RE.search(raw) and web_hits >= 1):
        return WEB_NAVIGATION
    return FREE_TEXT


def _markers_present(lowered: str, markers: tuple[str, ...]) -> list[str]:
    return sorted({m.strip() for m in markers if m in lowered})


def extract_signals(raw: str, kind: str) -> dict:
    lowered = raw.lower()
    urls = _URL_RE.findall(raw)
    success = _markers_present(lowered, _SUCCESS_MARKERS)
    errors = _markers_present(lowered, _ERROR_MARKERS)
    signals: dict = {
        "urls": urls[:20],
        "url_count": len(urls),
        "success_markers": success,
        "error_markers": errors,
        "char_length": len(raw),
    }

    if kind == STRUCTURED_API:
        parsed = _try_json(raw)
        if isinstance(parsed, dict):
            signals["json_keys"] = sorted(parsed.keys())[:30]
            # Common API status/error shapes.
            for k in ("status", "state", "result", "ok", "error", "code"):
                if k in parsed:
                    signals[f"json_{k}"] = parsed[k]
        elif isinstance(parsed, list):
            signals["json_array_len"] = len(parsed)

    if kind == WEB_NAVIGATION:
        # Count navigation-ish action lines for a rough effort signal.
        action_lines = [
            ln.strip()
            for ln in raw.splitlines()
            if any(m in ln.lower() for m in _WEB_MARKERS)
        ]
        signals["action_count"] = len(action_lines)
        if urls:
            signals["last_url"] = urls[-1]
        signals["mentions_screenshot"] = "screenshot" in lowered

    return signals


def _assess_quality(status: str, kind: str, signals: dict) -> str:
    if kind == EMPTY:
        return "missing"
    has_success = bool(signals.get("success_markers"))
    has_error = bool(signals.get("error_markers"))
    completed = status == "completed"
    if has_success and has_error:
        return "contradictory"
    if completed and (has_success or kind == STRUCTURED_API) and not has_error:
        return "strong"
    if has_error or not completed:
        return "weak"
    return "weak"


def _render_normalized(kind: str, raw: str, signals: dict) -> str:
    if kind == EMPTY:
        return "(no output recorded)"
    if kind == STRUCTURED_API:
        keys = signals.get("json_keys")
        head = f"Structured API response (keys: {', '.join(keys)})" if keys else "Structured response"
        return f"{head}. Raw: {raw.strip()[:600]}"
    if kind == WEB_NAVIGATION:
        parts = [
            f"Browser-agent transcript: {signals.get('action_count', 0)} navigation actions",
            f"across {signals.get('url_count', 0)} URL(s)",
        ]
        if signals.get("last_url"):
            parts.append(f"ending at {signals['last_url']}")
        if signals.get("error_markers"):
            parts.append(f"errors noted: {', '.join(signals['error_markers'])}")
        elif signals.get("success_markers"):
            parts.append(f"success markers: {', '.join(signals['success_markers'])}")
        return ". ".join(parts) + f". Transcript: {raw.strip()[:600]}"
    # FREE_TEXT
    return f"Free-text output: {raw.strip()[:600]}"


def normalize_step(step: dict) -> Evidence:
    """Normalize a single execution step (title/status/output) into Evidence."""

    raw = step.get("output")
    kind = classify_output(raw)
    signals = extract_signals(raw, kind) if raw else {}
    quality = _assess_quality(step.get("status", "unknown"), kind, signals)
    normalized = _render_normalized(kind, raw or "", signals)
    return Evidence(
        step_index=int(step.get("index", 0) or 0),
        step_title=str(step.get("title", "step")),
        status=str(step.get("status", "unknown")),
        output_kind=kind,
        normalized_text=normalized,
        signals=signals,
        quality=quality,
    )


def build_evidence(steps: list[dict]) -> list[Evidence]:
    """Normalize all execution steps into auditor-readable evidence."""

    out: list[Evidence] = []
    for i, s in enumerate(steps):
        s = {**s, "index": s.get("index", i)}
        out.append(normalize_step(s))
    return out


def render_evidence_block(evidence: list[Evidence]) -> str:
    """Render evidence as a compact, model-readable audit input."""

    if not evidence:
        return "(no execution steps recorded)"
    lines = []
    for e in evidence:
        lines.append(
            f"{e.step_index + 1}. [{e.status} · {e.output_kind} · evidence:{e.quality}] "
            f"{e.step_title}: {e.normalized_text}"
        )
    return "\n".join(lines)


def evidence_summary(evidence: list[Evidence]) -> dict:
    """Aggregate evidence quality for heuristics and observability."""

    kinds: dict[str, int] = {}
    qualities: dict[str, int] = {}
    for e in evidence:
        kinds[e.output_kind] = kinds.get(e.output_kind, 0) + 1
        qualities[e.quality] = qualities.get(e.quality, 0) + 1
    return {
        "kinds": kinds,
        "qualities": qualities,
        "unstructured_present": any(
            e.output_kind in (WEB_NAVIGATION, FREE_TEXT) for e in evidence
        ),
        "any_errors": any(e.signals.get("error_markers") for e in evidence),
        "all_strong": bool(evidence) and all(e.quality == "strong" for e in evidence),
    }


def grounding_summary(sources: list[dict] | None) -> dict:
    """Summarize the proof-of-work sources backing a deliverable.

    A *verified* source is one that was fetched successfully AND bound to a
    sha256 of its retrieved content — the difference between an asserted
    citation and one a third party can re-fetch and hash-check. This feeds the
    validator so a free-text deliverable grounded in checkable sources is
    credited, and one that grounds nothing is flagged as unverifiable.
    """

    sources = sources or []
    verified = [s for s in sources if s.get("ok") and s.get("sha256")]
    return {
        "sources_total": len(sources),
        "sources_verified": len(verified),
        "hash_bound": bool(verified),
        "grounded": len(verified) > 0,
        "verified_urls": [s.get("url") for s in verified][:20],
    }
