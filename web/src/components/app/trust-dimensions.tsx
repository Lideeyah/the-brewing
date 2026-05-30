import type { ReputationDimension } from "@/lib/types";

/**
 * Multidimensional reputation breakdown. Each axis is an evidence-backed ratio
 * with its own sample size; an axis with no sample shows "no data" rather than
 * a misleading zero bar.
 */
export function TrustDimensions({
  dimensions,
}: {
  dimensions: ReputationDimension[];
}) {
  if (!dimensions || dimensions.length === 0) return null;

  return (
    <div className="space-y-2.5">
      {dimensions.map((d) => {
        const has = d.value != null;
        const pct = has ? Math.round((d.value as number) * 100) : 0;
        return (
          <div key={d.key}>
            <div className="flex items-baseline justify-between gap-2">
              <span
                className="text-[12px] text-secondary"
                title={d.hint ?? undefined}
              >
                {d.label}
              </span>
              <span className="font-operational text-[11px] text-muted">
                {has ? `${pct}%` : "no data"}
                {d.sample_size > 0 ? ` · n=${d.sample_size}` : ""}
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-elevated">
              {has && (
                <div
                  className={
                    pct >= 75
                      ? "h-full rounded-full bg-success"
                      : pct >= 50
                        ? "h-full rounded-full bg-accent"
                        : "h-full rounded-full bg-failure"
                  }
                  style={{ width: `${pct}%` }}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
