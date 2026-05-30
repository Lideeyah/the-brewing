"""Multi-agent workflow architecture.

An objective is an *outcome*, not a job for one agent. The Coordination Copilot
decomposes it into a workflow of 1..N roles — planner, research, analysis,
executor, reviewer, validator — each assignable independently and each carrying
its own settlement allocation. This module owns:

- the role catalog and deterministic default-workflow generation (the Copilot's
  heuristic fallback, and the normalizer for model-proposed workflows), and
- the **feasibility engine**: before a workflow is approved it reconciles the
  objective budget against the sum of role allocations and every assigned
  agent's pricing constraints, returning a feasible / insufficient verdict with
  concrete recommendations.

Provider-agnostic and dependency-free. All amounts are USDC decimals as strings.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlmodel import Session, select

from app.models import (
    AgentIdentity,
    Objective,
    RoleAllocationChange,
    RoleStatus,
    WorkflowRole,
)

_USDC = Decimal("0.000001")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Ordered role catalog. role_key -> (default title, description, default weight).
ROLE_CATALOG: dict[str, tuple[str, str, float]] = {
    "planner": (
        "Planner",
        "Decomposes the objective into an executable plan and success criteria.",
        0.10,
    ),
    "research": (
        "Research",
        "Gathers the source material and evidence the objective depends on.",
        0.30,
    ),
    "analysis": (
        "Analysis",
        "Synthesizes findings into structured, decision-ready conclusions.",
        0.25,
    ),
    "executor": (
        "Executor",
        "Produces the primary deliverable the objective asked for.",
        0.35,
    ),
    "reviewer": (
        "Reviewer",
        "Checks the deliverable against the objective's quality bar.",
        0.15,
    ),
    "validator": (
        "Validator",
        "Independently verifies evidence before settlement (executor-independent).",
        0.10,
    ),
}


def _dec(value: str | None) -> Decimal:
    try:
        return Decimal(value or "0")
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _q(value: Decimal) -> str:
    return str(value.quantize(_USDC))


def _select_role_keys(intent: str) -> list[str]:
    """Heuristically choose a role set from the intent's shape."""

    text = (intent or "").lower()
    keys: list[str] = ["planner"]
    if any(w in text for w in ("research", "competitor", "intelligence", "market", "find", "gather", "scrape", "monitor")):
        keys.append("research")
    if any(w in text for w in ("analy", "compare", "evaluate", "assess", "insight", "summari")):
        keys.append("analysis")
    keys.append("executor")  # always a primary deliverable producer
    if any(w in text for w in ("report", "write", "draft", "document", "deck", "brief")):
        # writer is modeled as an executor specialization; keep executor.
        pass
    keys.append("reviewer")
    # De-dup while preserving order.
    seen: set[str] = set()
    ordered = [k for k in keys if not (k in seen or seen.add(k))]
    return ordered


def allocate(role_keys: list[str], budget: Decimal) -> list[Decimal]:
    """Split a budget across roles by catalog weight, summing exactly to budget."""

    weights = [ROLE_CATALOG.get(k, ("", "", 0.2))[2] for k in role_keys]
    total_w = sum(weights) or 1.0
    raw = [budget * Decimal(str(w / total_w)) for w in weights]
    out = [r.quantize(_USDC) for r in raw]
    # Push rounding remainder onto the last role so allocations sum to budget.
    drift = budget.quantize(_USDC) - sum(out)
    if out:
        out[-1] = (out[-1] + drift).quantize(_USDC)
    return out


def _subtask_contract(key: str, description: str) -> tuple[list, list, bool]:
    """Default per-sub-task contract: (success_criteria, evidence_kinds, required).

    The catalog description is a serviceable success criterion seed, and the
    criteria engine's modality inference names the evidence the sub-task should
    produce. Conservative: only emits a required evidence kind when the wording
    clearly implies one.
    """

    from app.domain.validation import criteria as _criteria

    criterion = description or f"The {key} sub-task is completed as specified."
    kind = _criteria._infer_required_kind(criterion)
    return [criterion], ([kind] if kind else []), True


def generate_workflow(intent: str, budget: Decimal) -> list[dict]:
    """Deterministic default workflow (Copilot heuristic fallback).

    Emits a linear dependency chain (each sub-task depends on the previous) so
    the default coordination graph is always a valid DAG with a clear execution
    order, plus a per-sub-task contract (success criteria + evidence kinds).
    """

    keys = _select_role_keys(intent)
    allocations = allocate(keys, budget)
    roles = []
    for i, (key, alloc) in enumerate(zip(keys, allocations)):
        title, desc, _ = ROLE_CATALOG.get(key, (key.title(), "", 0.2))
        criteria, kinds, required = _subtask_contract(key, desc)
        roles.append(
            {
                "order_index": i,
                "role_key": key,
                "title": title,
                "description": desc,
                "allocation_usdc": _q(alloc),
                "depends_on_index": [i - 1] if i > 0 else [],
                "success_criteria": criteria,
                "required_evidence_kinds": kinds,
                "required": required,
            }
        )
    return roles


def normalize_workflow(raw: object, intent: str, budget: Decimal) -> list[dict]:
    """Coerce a model-proposed workflow into role dicts that sum to budget.

    Falls back to the deterministic default when the model output is unusable.
    """

    if not isinstance(raw, list) or not raw:
        return generate_workflow(intent, budget)

    keys: list[str] = []
    titles: list[str] = []
    descs: list[str] = []
    weights: list[float] = []
    dep_specs: list[object] = []
    crit_specs: list[object] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("role_key") or item.get("role") or "executor").strip().lower()
        if key not in ROLE_CATALOG:
            key = "executor"
        keys.append(key)
        titles.append(str(item.get("title") or ROLE_CATALOG[key][0]))
        descs.append(str(item.get("description") or ROLE_CATALOG[key][1]))
        dep_specs.append(item.get("depends_on") or item.get("depends_on_index"))
        crit_specs.append(item.get("success_criteria"))
        # Accept an explicit allocation_pct (0..1 or 0..100) if present.
        pct = item.get("allocation_pct")
        try:
            w = float(pct)
            weights.append(w / 100.0 if w > 1 else w)
        except (TypeError, ValueError):
            weights.append(ROLE_CATALOG[key][2])

    if not keys:
        return generate_workflow(intent, budget)

    total_w = sum(weights) or 1.0
    norm_keys_alloc = allocate_by_weights(weights, total_w, budget)
    roles = []
    for i, (key, title, desc, alloc) in enumerate(
        zip(keys, titles, descs, norm_keys_alloc)
    ):
        default_crit, kinds, required = _subtask_contract(key, desc)
        # Per-sub-task criteria: honor a model-proposed list, else the default.
        proposed_crit = crit_specs[i]
        success_criteria = (
            [str(c) for c in proposed_crit if str(c).strip()]
            if isinstance(proposed_crit, list) and proposed_crit
            else default_crit
        )
        # Dependency edges: accept model-proposed index list; else linear chain.
        depends_on_index = _normalize_dep_indices(dep_specs[i], i, len(keys))
        roles.append(
            {
                "order_index": i,
                "role_key": key,
                "title": title,
                "description": desc,
                "allocation_usdc": _q(alloc),
                "depends_on_index": depends_on_index,
                "success_criteria": success_criteria,
                "required_evidence_kinds": kinds,
                "required": required,
            }
        )
    return roles


def _normalize_dep_indices(spec: object, i: int, n: int) -> list[int]:
    """Coerce a proposed dependency spec into valid prior-index references.

    Only backward edges (index < i) are kept, so the result is always acyclic.
    Falls back to a linear chain (depend on the previous sub-task) when the
    spec is absent or unusable.
    """

    if isinstance(spec, list):
        out: list[int] = []
        for d in spec:
            try:
                idx = int(d)
            except (TypeError, ValueError):
                continue
            if 0 <= idx < i and idx not in out:
                out.append(idx)
        return out
    return [i - 1] if i > 0 else []


def allocate_by_weights(weights: list[float], total_w: float, budget: Decimal) -> list[Decimal]:
    raw = [budget * Decimal(str(w / total_w)) for w in weights]
    out = [r.quantize(_USDC) for r in raw]
    drift = budget.quantize(_USDC) - sum(out)
    if out:
        out[-1] = (out[-1] + drift).quantize(_USDC)
    return out


# --- Feasibility engine -----------------------------------------------------


def evaluate_feasibility(
    session: Session, objective: Objective, roles: list[WorkflowRole]
) -> dict:
    """Reconcile budget vs. role allocations vs. assigned-agent constraints."""

    budget = _dec(objective.escrow_amount_usdc)
    required = sum((_dec(r.allocation_usdc) for r in roles), Decimal("0"))

    role_checks: list[dict] = []
    blocking = 0
    for role in sorted(roles, key=lambda r: r.order_index):
        alloc = _dec(role.allocation_usdc)
        issues: list[str] = []
        agent_name = None
        if role.assigned_agent_id:
            agent = session.get(AgentIdentity, role.assigned_agent_id)
            if agent is not None:
                agent_name = agent.name
                min_comp = _dec(agent.min_role_compensation_usdc)
                if min_comp > 0 and alloc < min_comp:
                    issues.append(
                        f"Allocation {alloc} USDC is below {agent.name}'s "
                        f"minimum role compensation of {min_comp} USDC."
                    )
                min_obj = _dec(agent.min_objective_value_usdc)
                if min_obj > 0 and budget < min_obj:
                    issues.append(
                        f"Objective budget {budget} USDC is below {agent.name}'s "
                        f"minimum objective value of {min_obj} USDC."
                    )
                if agent.availability == "offline":
                    issues.append(f"{agent.name} is offline and cannot be assigned.")
        if issues:
            blocking += 1
        role_checks.append(
            {
                "role_id": role.id,
                "role_key": role.role_key,
                "title": role.title,
                "allocation_usdc": _q(alloc),
                "assigned_agent_id": role.assigned_agent_id,
                "assigned_agent_name": agent_name,
                "ok": not issues,
                "issues": issues,
            }
        )

    over_budget = required > budget
    shortfall = (required - budget) if over_budget else Decimal("0")
    feasible = not over_budget and blocking == 0

    recommendations: list[str] = []
    if over_budget:
        recommendations.append(
            f"Increase the objective budget by {_q(shortfall)} USDC "
            f"(required {_q(required)} vs. budget {_q(budget)})."
        )
        recommendations.append("Or remove a role / lower a role's allocation.")
    if blocking:
        recommendations.append(
            "Resolve agent-constraint conflicts: raise allocations, choose "
            "alternative agents, or increase the budget."
        )

    return {
        "feasible": feasible,
        "budget_usdc": _q(budget),
        "required_usdc": _q(required),
        "shortfall_usdc": _q(shortfall),
        "over_budget": over_budget,
        "blocking_roles": blocking,
        "role_checks": role_checks,
        "recommendations": recommendations,
    }


# --- Persistence helpers ----------------------------------------------------


def replace_roles(session: Session, objective_id: str, role_specs: list[dict]) -> list[WorkflowRole]:
    """Replace an objective's workflow roles with a freshly generated set.

    Only called while the objective is still being (re)structured, before any
    role has been assigned or settled, so wiping is safe.
    """

    existing = session.exec(
        select(WorkflowRole).where(WorkflowRole.objective_id == objective_id)
    ).all()
    for r in existing:
        session.delete(r)

    created: list[WorkflowRole] = []
    for spec in role_specs:
        role = WorkflowRole(
            objective_id=objective_id,
            order_index=int(spec.get("order_index", 0)),
            role_key=str(spec.get("role_key", "executor")),
            title=str(spec.get("title", "Role")),
            description=spec.get("description"),
            allocation_usdc=str(spec.get("allocation_usdc", "0")),
            success_criteria=list(spec.get("success_criteria") or []),
            required_evidence_kinds=list(spec.get("required_evidence_kinds") or []),
            required=bool(spec.get("required", True)),
        )
        session.add(role)
        created.append(role)
    session.flush()

    # Second pass: resolve depends_on_index (positions in role_specs) into the
    # concrete role ids now that every role has been flushed and has an id.
    for role, spec in zip(created, role_specs):
        dep_idx = spec.get("depends_on_index") or []
        deps = [
            created[idx].id
            for idx in dep_idx
            if isinstance(idx, int) and 0 <= idx < len(created)
        ]
        if deps:
            role.depends_on = deps
            session.add(role)
    session.flush()
    return created


def get_roles(session: Session, objective_id: str) -> list[WorkflowRole]:
    return session.exec(
        select(WorkflowRole)
        .where(WorkflowRole.objective_id == objective_id)
        .order_by(WorkflowRole.order_index.asc())
    ).all()


def update_allocation(
    session: Session,
    *,
    objective: Objective,
    role: WorkflowRole,
    new_amount: Decimal,
    actor: str | None = None,
) -> WorkflowRole:
    """Re-weight a single role's settlement allocation.

    The Copilot proposes the initial budget-proportional split; this is the
    user-adjust path. Refuses a negative amount or one that would push the sum
    of all role allocations over the objective budget, and records the change
    in the append-only allocation history.

    Raises ValueError on an invalid edit.
    """

    if new_amount < 0:
        raise ValueError("Allocation cannot be negative.")

    budget = _dec(objective.escrow_amount_usdc)
    others = sum(
        (
            _dec(r.allocation_usdc)
            for r in get_roles(session, objective.id)
            if r.id != role.id
        ),
        Decimal("0"),
    )
    new_amount = new_amount.quantize(_USDC)
    if budget > 0 and (others + new_amount) > budget:
        remaining = (budget - others).quantize(_USDC)
        raise ValueError(
            f"Allocation {new_amount} USDC exceeds the remaining budget of "
            f"{remaining} USDC (objective budget {_q(budget)} USDC)."
        )

    previous = role.allocation_usdc
    role.allocation_usdc = _q(new_amount)
    role.updated_at = _now()
    session.add(role)
    session.add(
        RoleAllocationChange(
            objective_id=objective.id,
            role_id=role.id,
            from_usdc=previous,
            to_usdc=role.allocation_usdc,
            actor=actor,
        )
    )
    session.flush()
    return role


def settle_roles(
    session: Session, *, objective_id: str, approved: bool
) -> list[WorkflowRole]:
    """Resolve every workflow role's outcome when an objective settles.

    On approval, each role's allocation is treated as released to its assigned
    agent; on rejection, each role is slashed. Roles with no assigned agent are
    still marked so the workflow reflects a complete, auditable outcome. Returns
    the roles whose outcome was set.
    """

    roles = get_roles(session, objective_id)
    resolved: list[WorkflowRole] = []
    for role in roles:
        if approved:
            role.outcome = "released"
            role.status = RoleStatus.COMPLETED
        else:
            role.outcome = "slashed"
            role.status = RoleStatus.FAILED
        role.updated_at = _now()
        session.add(role)
        resolved.append(role)
    session.flush()
    return resolved


# --- Coordination graph -----------------------------------------------------


def coordination_graph(roles: list[WorkflowRole]) -> dict:
    """Compute the execution DAG over a set of sub-tasks (workflow roles).

    Pure and provider-agnostic. Each role carries `depends_on` (role ids) and a
    `validation_status` (pending|passed|failed). From those we derive:

    - **waves**: a topological layering (Kahn's algorithm) — wave 0 is everything
      with no dependency, wave k everything whose dependencies all land in waves
      < k. This is the execution order the UI renders left-to-right.
    - **node classification**: a sub-task is `ready` when all its dependencies
      have passed validation, `blocked` when a dependency is still pending,
      `failed` when a dependency failed (it can never become ready), or simply
      reflects its own terminal validation/settlement state.
    - **cycle detection**: any role left unlayered means a dependency cycle;
      reported rather than silently dropped.
    - **parent_settleable**: true only when every *required* sub-task has passed
      validation — the gate the parent objective settles behind.
    """

    by_id = {r.id: r for r in roles}
    order = sorted(roles, key=lambda r: (r.order_index, r.id))

    # Only count dependency edges that point at real sibling roles.
    deps: dict[str, list[str]] = {
        r.id: [d for d in (r.depends_on or []) if d in by_id and d != r.id]
        for r in order
    }

    # Kahn's algorithm: layer roles into execution waves.
    indegree = {rid: len(ds) for rid, ds in deps.items()}
    dependents: dict[str, list[str]] = {rid: [] for rid in by_id}
    for rid, ds in deps.items():
        for d in ds:
            dependents[d].append(rid)

    wave_of: dict[str, int] = {}
    frontier = [r.id for r in order if indegree[r.id] == 0]
    wave = 0
    remaining = dict(indegree)
    while frontier:
        for rid in frontier:
            wave_of[rid] = wave
        nxt: list[str] = []
        for rid in frontier:
            for dep in dependents[rid]:
                remaining[dep] -= 1
                if remaining[dep] == 0:
                    nxt.append(dep)
        # Preserve deterministic order within a wave.
        frontier = sorted(nxt, key=lambda x: (by_id[x].order_index, x))
        wave += 1

    cycle_ids = [rid for rid in by_id if rid not in wave_of]

    def _dep_state(rid: str) -> str:
        """Classify a node by its dependencies' validation outcomes."""
        ds = deps[rid]
        if any(by_id[d].validation_status == "failed" for d in ds):
            return "blocked_failed"
        if all(by_id[d].validation_status == "passed" for d in ds):
            return "ready"
        return "blocked"

    nodes: list[dict] = []
    for r in order:
        in_cycle = r.id in cycle_ids
        dep_state = "cycle" if in_cycle else _dep_state(r.id)
        nodes.append(
            {
                "role_id": r.id,
                "role_key": r.role_key,
                "title": r.title,
                "order_index": r.order_index,
                "wave": wave_of.get(r.id),
                "depends_on": deps[r.id],
                "required": bool(r.required),
                "allocation_usdc": r.allocation_usdc,
                "assigned_agent_id": r.assigned_agent_id,
                "validation_status": r.validation_status,
                "settlement_status": r.settlement_status,
                "dependency_state": dep_state,
                # A sub-task is actionable when its deps are satisfied and it has
                # not already passed/failed validation itself.
                "ready": dep_state == "ready"
                and r.validation_status == "pending",
            }
        )

    edges = [
        {"from": d, "to": r.id} for r in order for d in deps[r.id]
    ]

    waves: list[list[str]] = []
    if wave_of:
        for w in range(max(wave_of.values()) + 1):
            members = sorted(
                (rid for rid, wv in wave_of.items() if wv == w),
                key=lambda x: (by_id[x].order_index, x),
            )
            if members:
                waves.append(members)

    required_roles = [r for r in order if r.required]
    required_total = len(required_roles)
    required_passed = sum(
        1 for r in required_roles if r.validation_status == "passed"
    )
    required_failed = sum(
        1 for r in required_roles if r.validation_status == "failed"
    )
    parent_settleable = required_total > 0 and required_passed == required_total

    return {
        "nodes": nodes,
        "edges": edges,
        "waves": waves,
        "has_cycle": bool(cycle_ids),
        "cycle_role_ids": cycle_ids,
        "required_total": required_total,
        "required_passed": required_passed,
        "required_failed": required_failed,
        "parent_settleable": parent_settleable,
    }


def ready_subtasks(roles: list[WorkflowRole]) -> list[WorkflowRole]:
    """Return the sub-tasks whose dependencies have all passed validation and
    which have not themselves been validated yet — i.e. the actionable frontier.
    """

    graph = coordination_graph(roles)
    ready_ids = {n["role_id"] for n in graph["nodes"] if n["ready"]}
    return [r for r in roles if r.id in ready_ids]
