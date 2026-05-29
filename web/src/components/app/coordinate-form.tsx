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
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted">
          The Copilot structures governance, SLA, and settlement next.
        </p>
        <SubmitButton />
      </div>
    </form>
  );
}
