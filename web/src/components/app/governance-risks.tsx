import { AlertTriangle, ShieldAlert, ShieldQuestion } from "lucide-react";

import type { GovernanceRisk } from "@/lib/types";

const SEVERITY_META: Record<
  string,
  { label: string; cls: string; rank: number }
> = {
  high: {
    label: "high",
    cls: "border-failure/30 bg-failure/5 text-failure",
    rank: 3,
  },
  medium: {
    label: "medium",
    cls: "border-pending/30 bg-pending/5 text-pending",
    rank: 2,
  },
  low: {
    label: "low",
    cls: "border-border bg-elevated text-secondary",
    rank: 1,
  },
};

function severityIcon(severity: string) {
  if (severity === "high") return <ShieldAlert size={13} className="text-failure" />;
  if (severity === "medium")
    return <AlertTriangle size={13} className="text-pending" />;
  return <ShieldQuestion size={13} className="text-muted" />;
}

/**
 * Advisory risk register produced by the Copilot during governance evaluation.
 *
 * Risks are surfaced even when the recommendation is "approved" — they are
 * governance intelligence the reviewer weighs, never an automatic veto. Ordered
 * by severity so the sharpest flags read first.
 */
export function GovernanceRisks({
  risks,
  compact = false,
}: {
  risks: GovernanceRisk[];
  compact?: boolean;
}) {
  if (!risks || risks.length === 0) return null;

  const ordered = [...risks].sort(
    (a, b) =>
      (SEVERITY_META[b.severity]?.rank ?? 0) -
      (SEVERITY_META[a.severity]?.rank ?? 0),
  );

  return (
    <div>
      <p
        className={`mb-2 flex items-center gap-1.5 font-operational uppercase tracking-wider text-muted ${
          compact ? "text-[10px]" : "text-[11px]"
        }`}
      >
        <AlertTriangle size={compact ? 11 : 12} className="text-pending" />
        Risk register
        <span className="font-normal normal-case tracking-normal text-muted/70">
          · advisory
        </span>
      </p>
      <ul className="space-y-1.5">
        {ordered.map((r, i) => {
          const meta = SEVERITY_META[r.severity] ?? SEVERITY_META.low;
          return (
            <li
              key={i}
              className={`flex items-start gap-2 rounded-lg border px-2.5 py-1.5 ${meta.cls}`}
            >
              <span className="mt-0.5 shrink-0">{severityIcon(r.severity)}</span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-operational text-[10px] uppercase tracking-wider opacity-80">
                    {r.category}
                  </span>
                  <span className="rounded border border-current/20 px-1 py-px font-operational text-[9px] uppercase tracking-wider opacity-90">
                    {meta.label}
                  </span>
                </div>
                <p
                  className={`leading-relaxed text-foreground ${
                    compact ? "text-[11px]" : "text-[12px]"
                  }`}
                >
                  {r.detail}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
