"use client";

import { useState } from "react";
import { MessageSquarePlus, X } from "lucide-react";

import { FeedbackForm } from "@/components/app/feedback-form";

/**
 * Header-level feedback affordance: a single icon that opens a feedback modal,
 * so feedback is always one click away without adding a nav item.
 */
export function FeedbackButton() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Send feedback"
        title="Send feedback"
        className="flex h-8 w-8 items-center justify-center rounded-lg text-muted transition-colors hover:bg-elevated hover:text-foreground"
      >
        <MessageSquarePlus size={17} />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-background/70 p-4 pt-24 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-xl border border-border bg-surface shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
              <div>
                <h2 className="text-[14px] font-semibold text-foreground">
                  Send feedback
                </h2>
                <p className="text-[11px] text-muted">bugs · features · support</p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="flex h-7 w-7 items-center justify-center rounded-lg text-muted hover:bg-elevated hover:text-foreground"
              >
                <X size={15} />
              </button>
            </div>
            <div className="p-5">
              <FeedbackForm />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
