"use client";

import { useActionState } from "react";

import { resolveDispute } from "@/lib/admin-actions";
import type { AdminDispute } from "@/lib/types";

type State =
  | { ok: true; message: string; explorer?: string }
  | { ok: false; message: string }
  | null;

function DisputeCard({ d }: { d: AdminDispute }) {
  const [state, action, pending] = useActionState<State, FormData>(
    async (_prev, formData) => resolveDispute(formData),
    null,
  );

  const score = d.requester_reputation_score;
  const scoreTone =
    score == null ? "text-muted" : score >= 80 ? "text-success" : score >= 50 ? "text-foreground" : "text-failure";

  return (
    <div className="px-5 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium text-foreground">{d.title}</p>
          <p className="mt-0.5 font-operational text-[11px] text-muted">
            {d.workspace ?? d.workspace_id}
          </p>
        </div>
        <div className="text-right">
          <p className="font-operational text-[16px] leading-none text-foreground">
            {d.held_usdc} <span className="text-[11px] text-muted">USDC held</span>
          </p>
          <p className={`mt-1 font-operational text-[11px] ${scoreTone}`}>
            requester good-faith {score == null ? "—" : score}
          </p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 rounded-lg border border-border bg-background p-3 sm:grid-cols-2">
        <div>
          <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
            Independent validator
          </p>
          <p className="mt-0.5 text-[12px] text-foreground">
            {d.validator_recommendation ?? "—"}
            {d.validator_confidence != null && (
              <span className="text-muted"> · conf {d.validator_confidence}</span>
            )}
          </p>
        </div>
        <div>
          <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
            Requester record
          </p>
          <p className="mt-0.5 text-[12px] text-foreground">
            {d.disputes_lost}/{d.disputes_raised} disputes overturned
          </p>
        </div>
      </div>

      {d.reviewer_rationale && (
        <p className="mt-2 text-[12px] italic text-secondary">
          Reviewer: “{d.reviewer_rationale}”
        </p>
      )}

      <form action={action} className="mt-3 space-y-2">
        <input type="hidden" name="objective_id" value={d.objective_id} />
        <input
          name="rationale"
          placeholder="Arbiter rationale (optional)"
          className="w-full rounded-lg border border-border bg-background px-3.5 py-2 text-[12px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            name="resolution"
            value="release"
            disabled={pending}
            className="rounded-lg bg-success px-3.5 py-2 text-[12px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {pending ? "Working…" : "Release to executor"}
          </button>
          <button
            type="submit"
            name="resolution"
            value="uphold_rejection"
            disabled={pending}
            className="rounded-lg border border-failure px-3.5 py-2 text-[12px] font-medium text-failure transition-colors hover:bg-failure hover:text-background disabled:opacity-60"
          >
            {pending ? "Working…" : "Uphold rejection (slash to pool)"}
          </button>
        </div>
        {state?.ok && (
          <p className="text-[12px] text-success">
            {state.message}{" "}
            {state.explorer && (
              <a href={state.explorer} target="_blank" rel="noreferrer" className="underline">
                view tx ↗
              </a>
            )}
          </p>
        )}
        {state && !state.ok && (
          <p className="text-[12px] text-failure">{state.message}</p>
        )}
      </form>
    </div>
  );
}

export function Disputes({ disputes }: { disputes: AdminDispute[] }) {
  if (disputes.length === 0) {
    return (
      <p className="px-5 py-4 text-[12px] text-muted">
        No open disputes. A dispute appears here when a reviewer rejects work the
        independent validator passed — the escrow is held until you arbitrate.
      </p>
    );
  }
  return <div className="divide-y divide-border">{disputes.map((d) => <DisputeCard key={d.objective_id} d={d} />)}</div>;
}
