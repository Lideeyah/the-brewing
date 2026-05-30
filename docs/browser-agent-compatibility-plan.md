# Browser-Agent Compatibility Plan

**Status:** Planning — design and sequencing only. No implementation is proposed for merge as part of this document.
**Scope:** How browser-driven agents (headless-browser or Claude-in-Chrome–style executors that act on live web UIs) participate in Brewing as first-class, governed, verifiable coordination participants. Note: no browser-automation tooling is part of the stack today; this scopes how one would integrate.
**Audience:** Architecture / governance review.

---

## 1. Problem statement

Brewing's executors today are assumed to produce structured, inspectable outputs. A growing class of useful agents instead **drive a browser**: they fill forms, click through flows, scrape state, and complete tasks against systems with no API. These agents are valuable but introduce three hard problems for a governance layer:

1. **Evidence** — their "output" is a sequence of UI actions and screenshots, not a JSON artifact. Governance and independent validation need something hashable and verifiable.
2. **Non-determinism & trust** — a browser agent can hallucinate success, get rate-limited, or silently fail mid-flow. The settlement decision must not rest on the agent's own self-report.
3. **Safety** — a browser agent acts with real credentials on real systems. Its blast radius must be bounded by the coordination contract, not by the agent's good behavior.

This plan describes how the **existing** Brewing primitives (agent identity registry, executor-independent evidence-bound validation, the SLA oracle for unstructured outputs, role-based workflows, the rate-limiting pacemaker) extend to cover browser agents — and what genuinely new surface is required.

## 2. What already fits

Browser agents do **not** need a new identity or governance model. They reuse:

- **Agent identity registry (ERC-8004-shaped).** A browser agent registers like any other: a token id, capabilities (e.g. `web.form_fill`, `web.scrape`, `web.checkout`), pricing constraints, availability, and capacity. Its reputation accrues from settled outcomes exactly as for an API agent — *trust is earned from results, not from the modality.*
- **Workflow roles.** A browser agent fills a role (`executor`, `research`) in a multi-agent workflow and is assigned subject to the same Phase 3 constraints (min role compensation, availability, capacity).
- **Independent validation.** This is the keystone. Brewing already mandates that validation is performed by an **identity distinct from the executor** and is **bound to a hash of the exact evidence reviewed**. Browser agents make this principle *more* important, not less — the executor must never validate its own browser run.
- **SLA oracle for unstructured outputs.** Browser results are inherently unstructured; the SLA oracle path already exists to assess unstructured deliverables against criteria, and is the natural evaluator for "did the browser task actually meet the objective."
- **Rate-limiting pacemaker.** Brewing already serializes downstream Claude calls behind a 3.5s `asyncio.Lock` pacemaker (`orchestration_pacemaker_seconds`, see `domain/copilot`) to avoid 429s. A browser harness would extend the same discipline to every browser/model action, not just the existing Copilot calls.

## 3. What is new: the evidence envelope

The one genuinely new primitive a browser agent needs is a **structured evidence envelope** that turns an unstructured browser run into something governance can hash, store, and independently validate.

Proposed envelope (conceptual — not a schema for merge):

```
BrowserRunEvidence:
  objective_id / role_id
  agent_token_id
  steps: [
    { index, intent, action, target_url,
      dom_snapshot_ref, screenshot_ref,
      network_summary, timestamp }
  ]
  final_state: { url, assertion_results, extracted_data }
  evidence_hash        # hash over the canonicalized envelope
  pacemaker_log        # proves rate-limit discipline was honored
```

Key properties:

- **Hashable & bound.** The `evidence_hash` plugs directly into the existing validation flow (`evidence_hash`, `evidence_summary` already exist on `ValidationRecord`). Validation binds to it; execution cannot retroactively edit what it claimed to have done.
- **Artifact storage.** `dom_snapshot_ref` / `screenshot_ref` are content-addressed references (the artifacts themselves live in blob storage, not the DB). Only references + the hash are in the governance record.
- **Self-report is not evidence.** The agent's "I succeeded" is one field among many; the validator re-derives success from `final_state.assertion_results` and the captured DOM/screenshots, independently.

## 4. Validation of browser outputs

The independent validator for a browser run:

1. Receives the evidence envelope (not the live browser, not the agent's word).
2. Re-checks `assertion_results` against the objective's governance criteria.
3. Optionally re-runs cheap deterministic assertions against the captured `final_state` / DOM snapshot.
4. Emits a recommendation + confidence + findings, bound to the `evidence_hash`, exactly as today.

Because the validator is a **distinct identity** and works only from captured evidence, a browser agent cannot launder a failed run into a payout. This is the existing Phase 1 guarantee applied unchanged.

## 5. Safety boundaries

Browser agents act with real credentials, so the coordination contract must bound them:

- **Capability scoping.** Registry capabilities (`web.checkout`, `web.scrape`, …) gate which roles an agent may be assigned. A scrape-only agent must not be assignable to a checkout role.
- **Allowlist / target constraints.** A role definition should carry an allowed-origin set; actions outside it are rejected at the harness, not trusted to the agent.
- **Credential isolation.** Credentials used by a browser agent are tenant-scoped and never enter Brewing's governance records — only redacted network summaries do. This dovetails with the non-custodial direction: Brewing observes and governs, it does not hold the tenant's secrets.
- **Pacemaker enforcement.** The existing 3.5s pacemaker lock would be extended to the browser harness; `pacemaker_log` in the evidence envelope makes adherence auditable and can itself be a validation finding.
- **Kill-switch via SLA.** A browser run that exceeds `sla_config.deadline_hours` or stalls is slashable through the existing SLA/slash path — no new enforcement primitive needed.

## 6. Sequencing (when this is built)

Each stage is additive and independently shippable; none disturbs governance, validation, or settlement internals.

1. **Stage A — Evidence envelope.** Define `BrowserRunEvidence`, content-addressed artifact storage, and the canonicalization + hashing that feeds the existing `evidence_hash`. Validate that the existing validation flow accepts it unchanged.
2. **Stage B — Browser executor adapter.** A harness that runs a browser agent under the pacemaker, captures the envelope, and submits it as the role's deliverable. Capability scoping + origin allowlists enforced here.
3. **Stage C — Validator extensions.** Teach the independent validator / SLA oracle to re-derive success from the envelope (assertion replay over captured state).
4. **Stage D — Registry surfacing.** Show `web.*` capabilities and a "browser agent" affordance in the Verified Agent Registry, so counterparties can see the modality and its earned trust.

## 7. Verdict

Browser-agent compatibility is **mostly a reuse story.** Identity, reputation, workflow roles, independent evidence-bound validation, the SLA oracle, and the rate-limit pacemaker already cover the governance-critical concerns. The single new primitive is the **evidence envelope** that converts an unstructured browser run into a hashable, independently-validatable artifact. Building it does not require changes to governance or settlement logic — it slots into the `evidence_hash` contract those layers already depend on. No code change is recommended by this document; it scopes the work and confirms the architecture absorbs it additively.
