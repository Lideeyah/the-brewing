"use client";

import { useActionState } from "react";

import { submitFeedback } from "@/lib/actions";

type State = { ok: boolean; message?: string } | null;

export function FeedbackForm() {
  const [state, action, pending] = useActionState<State, FormData>(
    async (_prev, formData) => submitFeedback(formData),
    null,
  );

  if (state?.ok) {
    return (
      <div className="rounded-lg border border-border bg-background p-4 text-[13px] text-secondary">
        Thanks — your feedback was received. We read everything.
      </div>
    );
  }

  return (
    <form action={action} className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {(["general", "bug", "feature", "support"] as const).map((c, i) => (
          <label
            key={c}
            className="flex cursor-pointer items-center gap-1.5 text-[12px] text-secondary"
          >
            <input
              type="radio"
              name="category"
              value={c}
              defaultChecked={i === 0}
              className="accent-accent"
            />
            <span className="capitalize">{c}</span>
          </label>
        ))}
      </div>
      <textarea
        name="message"
        required
        rows={4}
        placeholder="Tell us what's working, what's broken, or what you need. Bugs, feature requests, and support questions all land in our admin console."
        className="w-full resize-y rounded-lg border border-border bg-background px-3.5 py-3 text-[13px] leading-relaxed text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
      />
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-foreground px-4 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {pending ? "Sending…" : "Send feedback"}
        </button>
        {state && !state.ok && state.message && (
          <span className="text-[12px] text-failure">{state.message}</span>
        )}
      </div>
    </form>
  );
}
