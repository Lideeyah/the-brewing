"use client";

import { useFormStatus } from "react-dom";
import { ArrowRight, Loader2 } from "lucide-react";

import { createObjective } from "@/lib/actions";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex h-[42px] shrink-0 items-center justify-center gap-2 rounded-lg bg-foreground px-4 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
    >
      {pending ? (
        <>
          <Loader2 size={15} className="animate-spin" />
          Drafting…
        </>
      ) : (
        <>
          Coordinate <ArrowRight size={15} />
        </>
      )}
    </button>
  );
}

/**
 * Compact "new objective + budget" launcher for the dashboard, so an operator
 * can start coordination without first navigating to the Coordinate page. Posts
 * to the same server action; the budget is the USDC locked into escrow.
 */
export function QuickCoordinate() {
  return (
    <form
      action={createObjective}
      className="flex flex-col gap-3 sm:flex-row sm:items-end"
    >
      <div className="min-w-0 flex-1">
        <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
          Operational intent
        </label>
        <input
          name="intent"
          type="text"
          required
          placeholder="e.g. Produce a competitive analysis of stablecoin settlement rails, with sources, in 48h."
          className="h-[42px] w-full rounded-lg border border-border bg-background px-3.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
      </div>
      <div className="sm:w-44">
        <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
          Budget · USDC
        </label>
        <div className="relative">
          <input
            name="budget"
            type="number"
            min="0"
            step="0.000001"
            inputMode="decimal"
            placeholder="Auto"
            className="h-[42px] w-full rounded-lg border border-border bg-background px-3.5 pr-14 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
          />
          <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 font-operational text-[11px] uppercase tracking-wider text-muted">
            USDC
          </span>
        </div>
      </div>
      <SubmitButton />
    </form>
  );
}
