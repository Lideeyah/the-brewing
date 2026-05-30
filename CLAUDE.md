# Brewing

Governed coordination infrastructure for autonomous economic activity.

Brewing is **not** an agent marketplace, an AI-workforce platform, or a payment
processor. It is a **governed coordination layer**: humans (and agents) declare
objectives, a Copilot structures governance/SLA/settlement terms and a
multi-agent workflow, capital is locked in escrow, execution is validated by an
identity **independent of the executor** and bound to a hash of the evidence,
and settlement releases or slashes per role on a human-authoritative decision.

> This is a real, standalone product. It is **not** the earlier Arc/EVM
> hackathon variant. There is **no** Vyper, no `AgentEscrow.vy`, no titanoboa,
> no Anchor program, no Arc testnet here. Settlement runs through **Circle
> Developer-Controlled Wallets → USDC on Solana devnet**. Ignore any guidance
> that references Arc, Vyper, titanoboa, or Playwright — none are part of this
> stack.

---

## Layout

```
web/    Next.js 16 (App Router) dashboard — the operator UI
api/    FastAPI backend — identity source of truth, governance, settlement
docs/   Architecture reviews / planning docs (review-only unless stated)
```

## Stack

| Layer | Technology |
|---|---|
| Web | Next.js 16.2.6 (App Router, server components + server actions), React 19, TailwindCSS v4, lucide-react, next-auth v5 |
| API | FastAPI, SQLModel, Alembic, pydantic-settings, python-jose (JWT, HS256) |
| DB | SQLite for dev (`api/brewing.db`); Postgres (psycopg) in prod |
| Agents | Anthropic Claude via the Anthropic SDK (`copilot_model`, default `claude-opus-4-7`) |
| Settlement | Circle Developer-Controlled Wallets → USDC on **Solana devnet** (`SOL-DEVNET`) |

## API domain layering (`api/app/domain/`)

The domain is layered and chain-neutral; routers stay thin.

- `copilot/` — Coordination Copilot: structures objectives, generates workflows, governance evaluation. Serializes downstream Claude calls behind a **3.5s `asyncio.Lock` pacemaker** (`orchestration_pacemaker_seconds`) to avoid 429s.
- `governance/` — advisory governance evaluation (human issues the binding decision).
- `validation/` — independent, evidence-bound validation (validator identity is distinct from the executor; bound to an `evidence_hash`).
- `oracle/` — SLA oracle for assessing unstructured deliverables against criteria.
- `orchestration/` — execution run/step orchestration.
- `registry/` — ERC-8004-shaped agent identity registry, reputation feedback loop, multidimensional trust dimensions.
- `workflow/` — multi-agent workflow roles, feasibility, allocation, per-role settlement.
- `settlement/` — **provider-agnostic** settlement: `provider.py` defines the `SettlementProvider` ABC (and the `NonCustodialSettlementProvider` seam), `circle_provider.py` is the first (custodial) implementation, `fees.py` the hybrid fee model. No Circle/Solana types leak into the domain.

## Objective lifecycle

`draft → copilot_structured → escrow_locked → executing → under_audit →
governance_decision → settled | slashed | disputed`

---

## Running it

**API** (from `api/`, venv at `api/.venv`):
```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```
Defaults to SQLite (`brewing.db`); tables are created on startup and columns are
idempotently backfilled (see `app/db.py` `_COLUMN_BACKFILLS`).

**Web** (from `web/`):
```bash
npm run dev      # next dev, http://localhost:3000
npx tsc --noEmit # typecheck
npx eslint src   # lint
```

## Auth (for manual API testing)

The API is the identity source of truth and shares `session_secret` with the web app.
```
POST /auth/session
  header: x-brewing-auth: <SESSION_SECRET>     # dev default: dev-insecure-change-me
  body:   { "email": "...", "name": "..." }
→ returns a JWT; send it as  Authorization: Bearer <token>
```

## Env vars (see `api/.env.example`)

`DATABASE_URL`, `SESSION_SECRET`, `ANTHROPIC_API_KEY`, `COPILOT_MODEL`,
`SETTLEMENT_PROVIDER` (default `circle`), `CIRCLE_API_KEY`,
`CIRCLE_ENTITY_SECRET`, `CIRCLE_WALLET_SET_ID`, `CIRCLE_BLOCKCHAIN`
(default `SOL-DEVNET`), `WEB_ORIGIN`.

---

## Conventions

- **Commits**: small, incremental, one logical slice each. Never batch unrelated changes.
- **Never** add a `Co-Authored-By` trailer to commits.
- **Never** commit `.env` (only `.env.example`).
- **Never** touch any `README` unless explicitly asked.
- **Frontend API helpers**: `apiGet` / `apiPost` / `apiPatch` in `web/src/lib/api.ts`; server actions in `web/src/lib/actions.ts`; wire types in `web/src/lib/types.ts` mirror the FastAPI schemas.
- **`StatusPill` tones**: `success | pending | failure | neutral | active` (no `warning`).
- **New domain calls in audit/settle paths are non-blocking** — wrap in try/except and `logger.warning` so a reputation/trace side-effect never breaks settlement.
- **Money math**: `Decimal`, quantized to USDC precision (`0.000001`); proportional splits sum exactly to budget (drift pushed to the last role).
- Anthropic "credit balance too low" is expected in dev and handled gracefully via heuristic fallbacks — not an error to fix.

## What this is NOT

- Not the Arc/EVM hackathon build (no Vyper, no `AgentEscrow.vy`, no titanoboa, no Canteen/Agora submission).
- Not a Solana **Anchor** program — on-chain value movement is via Circle DCW, not a custom program.
- Not a custodian by intent: the custodial Circle rail is current; a non-custodial (tenant-key-controlled) escrow seam is defined and is the target. See `docs/non-custodial-architecture-review.md`.
