# Payout Destination Decoupling — Design Proposal

**Status:** Proposal — design and migration path only. No implementation is proposed for merge as part of this document.
**Scope:** How settlement resolves *where* released funds are sent, and removing the wallet-per-settlement assumption baked into that decision.
**Audience:** Architecture / settlement review.
**Relates to:** the `_resolve_payout_wallet` seam in `api/app/routers/objectives.py` (the single, deliberately-centralized place this decision is now made).

---

## 1. Why this proposal exists

When an objective (or sub-task) is approved, settlement **releases escrow to a payee**. Today the payee wallet is produced like this:

```python
payout = _resolve_payout_wallet(provider, ref=f"payout-{obj.id}-{role.id}")
transfer = provider.release_escrow(EscrowRef(...), payout)
```

`_resolve_payout_wallet` currently calls `provider.provision_treasury_wallet(...)` — i.e. it **mints a brand-new provider wallet at payout time** and releases into it. That is a wallet-per-objective artifact in the settlement path: the destination is a throwaway account created for one release, not a persistent, counterparty-owned wallet.

This document names that assumption, explains why it is acceptable today, and proposes binding settlement to a **registered payee wallet** so funds land in an account the counterparty actually owns. It does **not** change the settlement model, the escrow design, or introduce PDA escrow. It changes only *whose* wallet a release targets.

## 2. Current state — payout destination is minted, not resolved

- The release destination is a fresh wallet from `provision_treasury_wallet`. Under the current custodial Circle rail, that wallet is itself a Brewing-controlled Developer-Controlled Wallet — so "release to the agent" actually lands in **another wallet Brewing custodies**, recorded only by the `payout_address` on the settlement event.
- `AgentIdentity.owner` already exists and is documented as "owner / agentic-wallet address holding signing authority" — i.e. a real counterparty-owned address — but it is **not** used as the settlement destination.
- The assumption is now isolated to one function (`_resolve_payout_wallet`), so this proposal is about changing *that function's body*, not threading a change through every settle call site.

### What is honest today
- The settlement amount, fee, authorization, and evidence hash are all correct and real.
- The on-chain transfer is real once the rail is unblocked.
- What is **not** yet true: that the destination is the payee's own persistent wallet. It is a system-minted account standing in for one.

## 3. The gap

| Concern | Mint-per-settlement (today) | Registered-payee (target) |
|---|---|---|
| Destination identity | Throwaway wallet per release | The payee's persistent, registered wallet |
| Custody of paid funds | Lands in a Brewing-controlled wallet | Lands in a counterparty-owned wallet |
| Wallet count | +1 per settlement | 0 new wallets per settlement |
| Non-custodial readiness | Destination is provider-custodied | Destination is the agent's agentic wallet |
| Provider/escrow swap | Destination tied to `provision_treasury_wallet` semantics | Destination is a plain address; provider-neutral |
| Auditability | Payee inferred from event `payout_address` | Payee bound to a registered identity up front |

The sharp version: as soon as settlement should pay an **independent** counterparty (a distinct agent, a human, a tenant), "mint a wallet and call it the payee" stops being a stand-in and becomes incorrect — the money never reaches an account the payee controls.

## 4. Proposed model — resolve the payee's registered wallet

Keep `_resolve_payout_wallet` as the single decision point; change what it returns.

### 4.1 Bind a payout wallet to the payee identity
- Reuse `AgentIdentity.owner` as the payout destination where it is a settlement-capable address, **or** add an explicit, nullable `AgentIdentity.payout_address` (additive, backfillable via the existing `_COLUMN_BACKFILLS` pattern) when the signing-authority address and the payout address should differ.
- The assigned agent for a role (`role.assigned_agent_id`) already exists, so the payee is known at settlement time.

### 4.2 Resolution rule (inside the one seam)
```
_resolve_payout_wallet(provider, *, obj, role=None):
    agent = registered agent for role (or objective-level payee)
    if agent has a registered payout wallet:
        return WalletRef(address=that wallet, ...)   # provider-neutral
    else:
        return provider.provision_treasury_wallet(ref)   # current fallback
```
The fallback preserves today's behavior for objectives with no registered payee, so the change is **backwards-compatible** and non-breaking.

### 4.3 What stays exactly the same
- `release_escrow` / `slash_escrow`, the escrow model, the fee model, authorization, evidence hashing, and the lifecycle are untouched.
- The settlement event still records `payout_address`; it simply now points at a registered wallet.
- No PDA escrow, no change to custody of *escrow* funds — only the *destination* of a release.

## 5. Migration path

1. **Schema, dormant.** Add `AgentIdentity.payout_address` (nullable) + backfill entry, or formally designate `owner` as the payout address. No behavior change.
2. **Capture at registration/assignment.** Let agents register a payout wallet; surface it read-only in the registry. Still settling via the mint fallback.
3. **Resolve behind the seam.** Change `_resolve_payout_wallet` to prefer the registered wallet, falling back to minting when absent. Distinct, counterparty-owned destinations start appearing in settlement events.
4. **Default for assigned agents.** Once coverage is trusted, require a registered payout wallet to assign an agent to a paid role; keep the mint fallback only for unassigned/objective-level payouts.

Each phase is independently revertible; none requires a destructive migration.

## 6. Open questions
- **One address or two?** Reuse `owner` (signing authority == payout) vs. a separate `payout_address` (paid somewhere other than the signer). The latter is more flexible but adds a field to validate.
- **Verification.** Should a registered payout wallet be proven (signature challenge) before it can receive funds, to prevent misdirected settlement?
- **Objective-level payee.** When there is no per-role agent, who is the objective-level payee — the workspace treasury, or a designated counterparty?
- **Interaction with non-custodial escrow.** In the `NonCustodialSettlementProvider` model the destination is naturally the controller wallet; this proposal and that one should converge on the same "registered counterparty address" concept.

## 7. Recommendation

Adopt registered-payee resolution **when settlement must pay independent counterparties**, following the phased path in §5. Until then, the mint-per-settlement fallback is an acceptable, internally consistent stand-in — but it should be documented as a known limitation (as it is here and in the `_resolve_payout_wallet` docstring), not presented as paying the counterparty's own wallet. The highest-leverage first step is **§5.1 + §5.2**: give identities a payout wallet and capture it, which is additive, non-breaking, and immediately makes the eventual settlement change a one-function edit behind the existing seam.
