"use client";

import { useActionState } from "react";

import { updateAutomationPolicy } from "@/lib/actions";

type State = { ok: true; message: string } | { ok: false; message: string } | null;

export function AutomationPolicy({
  enabled,
  maxUsdc,
  minConfidence,
}: {
  enabled: boolean;
  maxUsdc?: string | null;
  minConfidence: number;
}) {
  const [state, action, pending] = useActionState<State, FormData>(
    updateAutomationPolicy,
    null,
  );

  return (
    <form action={action} className="space-y-4">
      <label className="flex items-start gap-3">
        <input
          type="checkbox"
          name="auto_settle_enabled"
          defaultChecked={enabled}
          className="mt-0.5 h-4 w-4 accent-accent"
        />
        <span>
          <span className="block text-[13px] font-medium text-foreground">
            Auto-settle objectives that clear the bar
          </span>
          <span className="mt-0.5 block text-[12px] leading-relaxed text-secondary">
            When the independent validator approves at or above your confidence
            floor, every success criterion is satisfied, and the deliverable is
            grounded in content-hashed proof-of-work, settlement releases
            automatically — no manual decision. You stay authoritative: this
            policy is yours to set, and anything short of the bar still waits for
            you.
          </span>
        </span>
      </label>

      <div className="grid grid-cols-1 gap-4 border-t border-border pt-4 sm:grid-cols-2">
        <div>
          <label className="font-operational text-[11px] uppercase tracking-wider text-muted">
            Confidence floor (%)
          </label>
          <input
            name="auto_settle_min_confidence"
            type="number"
            min={50}
            max={99}
            step={1}
            defaultValue={Math.round(minConfidence * 100)}
            className="mt-1 w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[13px] text-foreground focus:border-border-strong focus:outline-none"
          />
        </div>
        <div>
          <label className="font-operational text-[11px] uppercase tracking-wider text-muted">
            Value cap (USDC, blank = no cap)
          </label>
          <input
            name="auto_settle_max_usdc"
            type="number"
            min={0}
            step="0.000001"
            defaultValue={maxUsdc ?? ""}
            placeholder="e.g. 25 — only auto-settle at or below this"
            className="mt-1 w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {pending ? "Saving…" : "Save policy"}
        </button>
        {state?.ok && <p className="text-[12px] text-success">{state.message}</p>}
        {state && !state.ok && (
          <p className="text-[12px] text-failure">{state.message}</p>
        )}
      </div>
    </form>
  );
}
