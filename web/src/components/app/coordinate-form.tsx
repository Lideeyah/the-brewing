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
      className="flex items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
    >
      {pending ? (
        <>
          <Loader2 size={15} className="animate-spin" />
          Drafting objective…
        </>
      ) : (
        <>
          Draft objective <ArrowRight size={15} />
        </>
      )}
    </button>
  );
}

export function CoordinateForm() {
  return (
    <form action={createObjective} className="space-y-4">
      <div>
        <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
          Operational intent
        </label>
        <textarea
          name="intent"
          required
          rows={6}
          placeholder="Describe what you need coordinated and settled. e.g. “Produce a competitive analysis of stablecoin settlement rails, with sources, delivered within 48 hours.”"
          className="w-full resize-y rounded-lg border border-border bg-background px-3.5 py-3 text-[13px] leading-relaxed text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
            Title (optional)
          </label>
          <input
            name="title"
            type="text"
            placeholder="Auto-derived from intent if left blank"
            className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
            Budget · USDC (optional)
          </label>
          <div className="relative">
            <input
              name="budget"
              type="number"
              min="0"
              step="0.000001"
              inputMode="decimal"
              placeholder="Copilot recommends if blank"
              className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 pr-14 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
            />
            <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 font-operational text-[11px] uppercase tracking-wider text-muted">
              USDC
            </span>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
            Definition of done (SLA)
          </label>
          <textarea
            name="definition_of_done"
            rows={3}
            placeholder="What does “done” mean to you? e.g. “At least 8 named competitors, each with pricing and a cited source.” Leave blank to let the Copilot propose the acceptance bar."
            className="w-full resize-y rounded-lg border border-border bg-background px-3.5 py-2.5 text-[13px] leading-relaxed text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1.5 block font-operational text-[11px] uppercase tracking-wider text-muted">
            Deadline · timeframe (SLA)
          </label>
          <input
            name="deadline"
            type="text"
            placeholder="e.g. 48 hours, or 2026-06-10"
            className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
          />
          <p className="mt-1.5 text-[11px] leading-snug text-muted">
            The service level the work is held to — a duration or an absolute
            due date.
          </p>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted">
          The Copilot structures governance, SLA, and settlement next.
        </p>
        <SubmitButton />
      </div>
    </form>
  );
}
