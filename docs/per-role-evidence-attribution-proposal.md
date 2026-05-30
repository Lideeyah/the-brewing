# Per-Role Evidence Attribution — Design Proposal

**Status:** Proposal — design and migration path only. No implementation is proposed for merge as part of this document.
**Scope:** How coordination sub-tasks (WorkflowRoles) are bound to the execution evidence that justifies their independent validation and settlement.
**Audience:** Architecture / governance review.

---

## 1. Why this proposal exists

Brewing decomposes an objective into a dependency-ordered graph of sub-tasks, and each sub-task is **independently verifiable and independently settleable**: it carries its own success criteria, its own validation verdict, its own settlement authorization, and releases or slashes its own allocation. That is the coordination primitive the product is built on.

There is one seam in that primitive that is currently a deliberate compromise: **every sub-task is validated against the same objective-wide evidence bundle.** What differs per sub-task is its *contract* (its own criteria), not the *evidence* it is judged against. This document names that compromise precisely, explains why it is acceptable today, and proposes a per-role evidence attribution model to replace it when the product needs genuinely independent evidence per sub-task. It does **not** change code.

## 2. Current state — the shared-evidence model

### 2.1 One evidence bundle, many contracts

Execution produces a single objective-level `ExecutionRun` with ordered `ExecutionStep`s. The SLA oracle (`oracle.build_evidence`) normalizes those steps into one evidence list, and `_objective_evidence_bundle()` returns that single `(evidence_dicts, evidence_summary)` pair for the whole objective.

When a sub-task is validated (`POST /objectives/{id}/roles/{role_id}/validate`), it reuses **that same bundle**:

```
evidence_dicts, evidence_summary = _objective_evidence_bundle(session, obj)
record = validation.run_validation(..., evidence=evidence_dicts, role_id=role.id)
authorization = validation.record_authorization(..., raw_criteria=role.success_criteria,
                                                evidence=evidence_dicts, role_id=role.id)
```

So `run_validation` and `record_authorization` are correctly **scoped by `role_id`** — each sub-task gets its own `ValidationRecord` and `SettlementAuthorization` — but they all reason over identical evidence. The per-criterion `basis` (which cites `step_index` / `step_title`) can already point at *which steps* grounded a criterion, but nothing asserts that a given step *belongs to* a given sub-task.

### 2.2 What is honest today

- Each sub-task's **criteria** are genuinely its own, and its verdict is computed against those criteria. A sub-task can pass while another fails on the same evidence.
- The `evidence_hash` each sub-task binds is the hash of the shared bundle, so two sub-tasks of the same objective will share an `evidence_hash`. This is internally consistent (the validator and the authorization re-derive the same hash) but it does **not** prove sub-task–specific work.
- `WorkflowRole.required_evidence_kinds` exists and is surfaced, but it is an *expectation*, not an *attribution*: nothing maps a specific evidence item to the role that produced it.

This is the right compromise for now because most objectives execute as one run and the differentiation that matters to users — "did *this* sub-task meet *its* bar?" — is already answered by per-role criteria. The shared-evidence model is a limitation, not a dishonesty.

## 3. The gap

| Concern | Shared evidence (today) | Per-role attribution (target) |
|---|---|---|
| Evidence source | One objective-level run | Evidence items attributed to the producing role |
| `evidence_hash` | Identical across sibling sub-tasks | Distinct per sub-task — hashes only the role's own evidence |
| "Why paid" provenance | Criteria met against shared bundle | Criteria met against *this role's* outputs |
| Independent execution | Not represented | A role executed by a distinct agent has distinct evidence |
| Slashing precision | Slash on criteria verdict | Slash on the role's own unmet, attributable evidence |
| Collusion / free-riding | A weak role can "borrow" a strong sibling's evidence | Each role stands on its own evidence |

The sharp failure mode: under the shared model, a sub-task assigned to a low-trust agent can satisfy an evidence-kind requirement using an output *another* sub-task's agent actually produced. The criteria engine matches terms across the whole bundle, so attribution leakage is possible. As soon as sub-tasks are executed by **different** agents — which the registry and per-role assignment already allow — "who produced this evidence" becomes a settlement-integrity question, not a cosmetic one.

## 4. Proposed model — evidence attributed to the producing role

The goal: make each sub-task's validation and settlement rest on **the evidence that sub-task's assigned agent actually produced**, while preserving the existing deterministic, hash-anchored validation pipeline.

### 4.1 Attribute execution output to a role

Add an optional `role_id` to the execution layer so a step can be tagged with the sub-task it fulfills:

- `ExecutionStep.role_id: str | None` (FK to `workflowrole`, nullable, indexed).
- Backfill is additive (the existing `_COLUMN_BACKFILLS` pattern in `api/app/db.py`): existing steps stay `role_id = NULL` and continue to behave as objective-level evidence.
- The orchestration layer that emits steps from the coordination plan stamps each step with the role it advances. Where a step genuinely serves the whole objective (e.g. a shared setup step), `role_id` stays null and that step is treated as **common evidence** available to every role (see 4.3).

No new evidence store is introduced — attribution is a tag on the step that already exists, so the oracle, criteria engine, and hashing all keep working unchanged.

### 4.2 A role-scoped evidence bundle

Introduce `_role_evidence_bundle(session, obj, role)` alongside the existing objective bundle. It builds evidence from:

1. Steps where `role_id == role.id` (the role's own work), **plus**
2. Steps where `role_id IS NULL` that are dependencies' published outputs the role legitimately consumes (common evidence), gated by the coordination graph's `depends_on` edges.

`run_validation` and `record_authorization` then receive this **narrower** evidence list. Because `evidence_hash` is `"sha256:" + sha256(canonical_json(evidence))`, a role-scoped bundle naturally yields a **distinct, role-specific hash** — the cryptographic anchor now proves "this agent was authorized against *its own* evidence."

### 4.3 Dependency-aware evidence visibility

The coordination graph already encodes `depends_on`. Reuse it as the evidence-visibility rule:

- A role sees its own attributed evidence and the **published outputs of the sub-tasks it depends on** (so a downstream analysis role can cite the upstream research role's result).
- A role does **not** see sibling evidence it has no dependency on. This is what closes the attribution-leakage hole in §3.

This makes evidence visibility a function of the DAG, not of the objective — consistent with how validation ordering already honors the DAG.

### 4.4 What stays exactly the same

- The deterministic validation engine, the criteria-satisfaction engine, and the `evidence_hash` construction are **untouched** — they simply receive a different (narrower) evidence list.
- `SettlementAuthorization`, the "why was this agent paid?" artifact, and the evidence audit trail keep their shape; they become *more* precise because their basis now cites only the role's own steps.
- The objective-level evaluation continues to use the full bundle. Per-role attribution is additive, not a replacement for the objective view.
- Non-blocking conventions hold: if a step has no `role_id` (legacy or shared), the role bundle gracefully falls back to treating it as common evidence, so nothing breaks for objectives that predate attribution.

## 5. Migration path

The change is incremental and backward-compatible at every step:

1. **Schema, dormant.** Add `ExecutionStep.role_id` (nullable) + backfill entry. No behavior change; all steps remain null and the shared bundle is still used. Ships safely on its own.
2. **Attribution, observational.** Begin stamping `role_id` on steps during orchestration and surface "produced by {role}" in the evidence audit trail — but **keep validating against the shared bundle.** This lets the attribution be inspected and corrected before it gates money.
3. **Role-scoped validation behind a flag.** Add `_role_evidence_bundle` and switch `validate_subtask` to it under an objective- or workspace-level setting (e.g. `governance_config["per_role_evidence"]`). Objectives without the flag keep the shared model. Distinct per-role `evidence_hash`es start appearing.
4. **Default on for multi-agent objectives.** Once attribution coverage is trusted, default role-scoped evidence for objectives whose sub-tasks are assigned to **distinct** agents (where the integrity risk is real), while single-agent objectives may retain the shared bundle as an explicit, cheaper mode.

Each phase is independently revertible and none requires a destructive migration.

## 6. Open questions

- **Common-evidence policy.** Should null-`role_id` steps be visible to all roles, or only to roles whose `required_evidence_kinds` match the step's classified kind? The latter is stricter but risks starving legitimate roles of shared context.
- **Re-execution & partial runs.** If one sub-task is re-executed, do we append a new attributed step set and re-hash only that role's bundle, leaving sibling hashes stable? (Proposed: yes — that is the point of attribution.)
- **Attribution authority.** Who asserts a step's `role_id` — the orchestrator deterministically from the plan, or the executing agent's self-report? Self-report needs validator corroboration to avoid re-introducing the leakage it removes. Proposed default: orchestrator-assigned, validator-checkable.
- **UI.** The evidence audit trail and coordination panel should show evidence grouped by producing role once attribution is on; the shared view remains available as an objective rollup.

## 7. Recommendation

Adopt per-role evidence attribution **when sub-tasks are routinely executed by distinct agents**, following the phased path in §5. Until then, the shared-evidence model is an acceptable, internally consistent compromise — but it should be documented as a known limitation (as it is here), not presented as per-sub-task evidence isolation. The single highest-leverage first step is **§5.1 + §5.2**: tag steps with their role and surface that attribution in the audit trail, which is observational, non-breaking, and immediately improves traceability without touching the settlement path.
