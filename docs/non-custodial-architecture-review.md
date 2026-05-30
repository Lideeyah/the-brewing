# Non-Custodial Architecture Review

**Status:** Review — assessment and recommendation only. No implementation is proposed for merge as part of this document.
**Scope:** Brewing settlement, escrow, and treasury custody on Solana devnet (via Circle Developer-Controlled Wallets) behind the provider abstraction.
**Audience:** Architecture / governance review.

---

## 1. Why this review exists

Brewing positions itself as *governed coordination infrastructure for autonomous economic activity* — explicitly **not** a payment processor or custodian. That positioning only holds if Brewing can credibly say it never holds, transmits, or unilaterally moves counterparty funds. This document audits how close the current architecture is to that claim, names the gap precisely, and recommends a migration path. It does **not** change code.

## 2. Current state

### 2.1 The custody seam already exists

The settlement domain depends on an abstract `SettlementProvider` (`api/app/domain/settlement/provider.py`) and never on a concrete chain or custodian. Two custody postures are first-class:

- `CUSTODIAL` — the provider holds the keys to escrowed funds. This is the **current default**, implemented by the Circle Developer-Controlled Wallets provider.
- `NON_CUSTODIAL` — declared via the `NonCustodialSettlementProvider` ABC, where escrow is a *tenant-scoped account* whose signing authority is the tenant's own agentic wallet. Its `deploy_tenant_escrow(controller_wallet, amount, objective_id)` returns a `TenantEscrowAccount` carrying a `controller_wallet` — "the agentic wallet that holds signing authority." Brewing references and observes the account but is **not** the signer.

Every escrow record is stamped with its `custody_model`, and that stamp flows all the way to the UI (`NonCustodialNote`, the provenance chain, the dashboard). The trust posture is therefore **explicit and auditable per objective**, not a marketing claim.

### 2.2 What is honest today

The custody-aware copy is deliberately truthful:

- Under the custodial rail it says Brewing is *"custody-minimizing by design"* and that agentic-wallet-controlled escrow is *"the target model."* It does **not** claim Brewing is already non-custodial.
- Under a genuine non-custodial escrow it states the full guarantee and surfaces the controller wallet.

This split is the right call and should be preserved: the product never overstates its custody guarantees.

## 3. The gap

The abstraction is non-custodial-ready; the **only wired implementation is custodial.** Concretely:

| Concern | Custodial (today) | Non-custodial (target) |
|---|---|---|
| Escrow signing authority | Circle (provider) holds keys | Tenant's agentic wallet holds keys |
| `release_escrow` / `slash_escrow` | Authorized by Brewing-controlled provider | Authorized by controller wallet signature |
| Brewing's role | Instructs the custodian | Observes + governs; cannot move funds unilaterally |
| Failure blast radius | Provider key compromise drains escrow | Compromise limited to a single tenant's wallet |
| Regulatory surface | Looks like money transmission | Coordination + governance only |

The missing pieces to close the gap are:

1. A concrete `NonCustodialSettlementProvider` implementation that provisions a per-objective escrow account on Solana whose signing authority is the tenant's own (agentic) wallet, not a Brewing-/Circle-held key. Today Circle DCW holds the keys; the non-custodial variant must hand custody to the tenant — either a tenant-owned account with a governance-gated release path or a lightweight on-chain escrow program the tenant controls.
2. A **governance-authorizes, controller-executes** flow: Brewing's governance decision produces a signed *authorization* (release vs. slash with amounts/allocations), and the controller wallet — driven by the tenant's agent — submits the on-chain transaction. Brewing's signature is necessary for governance but **not sufficient** to move funds.
3. Settlement allocation (the Phase 3 role-level release/slash split) must be expressed as on-chain instructions the controller can verify before signing, so partial settlement remains trust-minimized.

## 4. Trust & risk implications

- **Today's residual trust:** users must trust Circle (and Brewing's instruction integrity) not to misappropriate escrowed funds. This is a normal, bounded custodial-provider trust assumption, and it is disclosed honestly. It is acceptable for a hackathon/testnet posture but is the single largest gap between the product's stated identity and its implementation.
- **Co-signing nuance:** the strongest end state is *governance-gated, controller-executed* settlement (a 2-of-2 style split: governance authorization + controller signature). A naive "controller signs everything" model loses Brewing's ability to enforce slash-on-invalidation; a naive "Brewing signs everything" model is just custodial with extra steps. The split must preserve both invariants: **(a)** Brewing cannot pay out without the controller, **(b)** the controller cannot bypass a governance slash. A timelock + governance veto on the tenant escrow contract is the cleanest construction.
- **Dispute path:** the existing dispute/slash semantics (`slash_job` after `sla_timeout`, owner-trigger) map cleanly onto a tenant escrow contract with a governance role; this should be designed as contract logic, not Brewing-side enforcement.

## 5. Recommendation

A three-stage migration, each independently shippable, none requiring a rewrite of governance/orchestration (they already sit behind the provider seam):

1. **Stage A — Custody construction.** Define the on-chain escrow position whose signing authority is the tenant's wallet and whose release/slash is gated by a Brewing-held governance role — e.g. a tenant-owned account with a governance co-sign, or a small Solana escrow program with `controller` + `governance` roles and a timelock/veto. Land it behind tests before wiring.
2. **Stage B — Provider.** Implement a concrete `NonCustodialSettlementProvider` against that construction. Because the domain already depends only on the ABC, escrow/governance/settlement code should need **no changes** beyond provider selection.
3. **Stage C — Default flip.** Make non-custodial the default custody model for new objectives; keep custodial (Circle DCW) available as an explicit fallback for tenants without a self-custodied wallet. The UI already renders both postures correctly.

**No code change is recommended by this document itself.** The architecture is correctly factored to absorb this migration without disturbing governance, validation, or orchestration. The work is additive (a new provider + contract surface), and the honesty of the current custody messaging means no claims need to be walked back as the migration lands.

## 6. Verdict

The non-custodial *architecture* is sound and already in place as an abstraction; the *implementation* is the remaining work. The product's custody claims are currently honest because the UI is custody-aware. Closing the gap is a well-scoped, additive effort that the existing seams were explicitly designed to accommodate.
