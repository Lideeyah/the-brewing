import { Check } from "lucide-react";

const STEPS = [
  { n: 1, label: "Authenticate" },
  { n: 2, label: "Workspace" },
  { n: 3, label: "Treasury" },
  { n: 4, label: "Orientation" },
] as const;

/** First-run progress rail. `current` is the active step (1-4). */
export function OnboardingStepper({ current }: { current: number }) {
  return (
    <div className="mb-8 flex flex-wrap items-center justify-center gap-x-2 gap-y-2">
      {STEPS.map((s, i) => {
        const done = s.n < current;
        const active = s.n === current;
        return (
          <div key={s.n} className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <span
                className={`grid h-5 w-5 place-items-center rounded-md border text-[10px] font-operational ${
                  active
                    ? "border-accent bg-accent text-background"
                    : done
                      ? "border-success/40 bg-success/10 text-success"
                      : "border-border-strong bg-surface text-muted"
                }`}
              >
                {done ? <Check size={11} /> : s.n}
              </span>
              <span
                className={`font-operational text-[11px] uppercase tracking-wide ${
                  active ? "text-foreground" : "text-muted"
                }`}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span className="text-border-strong">→</span>
            )}
          </div>
        );
      })}
      <span className="text-border-strong">→</span>
      <span className="font-operational text-[11px] uppercase tracking-wide text-muted">
        Mission Control
      </span>
    </div>
  );
}
