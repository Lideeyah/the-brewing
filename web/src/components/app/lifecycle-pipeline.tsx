import { ChevronRight } from "lucide-react";

import { LIFECYCLE_PHASES, phaseCount } from "@/lib/objective-ui";

/**
 * Renders objective counts across the six canonical lifecycle edges
 * (Intent -> Governance -> Escrow -> Execution -> Validation -> Settlement),
 * making the whole coordination loop legible at a glance.
 */
export function LifecyclePipeline({
  statusCounts,
}: {
  statusCounts: Record<string, number>;
}) {
  return (
    <div className="flex items-stretch gap-1 overflow-x-auto px-5 py-4">
      {LIFECYCLE_PHASES.map((phase, i) => {
        const count = phaseCount(statusCounts, phase.statuses);
        const active = count > 0;
        return (
          <div key={phase.key} className="flex items-center gap-1">
            <div
              className={`flex min-w-[92px] flex-col rounded-lg border px-3 py-2.5 transition-colors ${
                active
                  ? "border-accent/30 bg-accent/5"
                  : "border-border bg-surface"
              }`}
            >
              <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                {phase.label}
              </span>
              <span
                className={`mt-1 font-operational text-[20px] leading-none tracking-tight ${
                  active ? "text-foreground" : "text-muted/50"
                }`}
              >
                {count}
              </span>
            </div>
            {i < LIFECYCLE_PHASES.length - 1 && (
              <ChevronRight
                size={14}
                className="shrink-0 text-border-strong"
                aria-hidden
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
