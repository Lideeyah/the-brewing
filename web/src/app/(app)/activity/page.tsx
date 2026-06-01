import { Activity } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { apiGet } from "@/lib/api";
import type { Overview } from "@/lib/types";
import {
  LIFECYCLE_PHASES,
  eventTone,
  formatTime,
  phaseCount,
} from "@/lib/objective-ui";

export default async function ActivityPage() {
  let overview: Overview | null = null;
  try {
    overview = await apiGet<Overview>("/workspaces/current/overview");
  } catch {
    overview = null;
  }

  const events = overview?.recent_events ?? [];
  const counts = overview?.status_counts ?? {};

  return (
    <>
      <Topbar title="Observability" breadcrumb="brewing / observability" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
              Observability
            </h2>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-secondary">
              A single, append-only stream of every governance event across the
              workspace — structuring, escrow locks, executions, validations,
              decisions, and settlements — as the coordination loop advances.
            </p>
          </div>

          {/* Lifecycle distribution */}
          <Panel>
            <PanelHeader title="Lifecycle distribution" meta="objectives by phase" />
            <PanelBody>
              <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
                {LIFECYCLE_PHASES.map((p) => (
                  <div
                    key={p.key}
                    className="rounded-lg border border-border bg-background p-3 text-center"
                  >
                    <div className="font-operational text-[20px] leading-none text-foreground">
                      {phaseCount(counts, p.statuses)}
                    </div>
                    <div className="mt-1.5 text-[10px] uppercase tracking-wider text-muted">
                      {p.label}
                    </div>
                  </div>
                ))}
              </div>
            </PanelBody>
          </Panel>

          {/* Event stream */}
          <Panel>
            <PanelHeader
              title="Event stream"
              meta={`${events.length} recent`}
            />
            <PanelBody className="p-0">
              {events.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                  <Activity size={22} className="text-accent" />
                  <p className="text-[13px] text-foreground">No activity yet</p>
                  <p className="max-w-md text-[12px] text-muted">
                    Coordinate an objective and its lifecycle events will stream
                    here as they happen.
                  </p>
                </div>
              ) : (
                <div className="px-5 py-4 space-y-4">
                  {events.map((e, i) => {
                    const tone = eventTone(e.kind);
                    return (
                      <div key={e.id} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <span
                            className={`mt-1 h-2 w-2 rounded-full ${
                              tone === "success"
                                ? "bg-success"
                                : tone === "failure"
                                  ? "bg-failure"
                                  : tone === "active"
                                    ? "bg-accent"
                                    : "bg-muted"
                            }`}
                          />
                          {i < events.length - 1 && (
                            <span className="mt-1 w-px flex-1 bg-border" />
                          )}
                        </div>
                        <div className="pb-1">
                          <div className="flex items-center gap-2">
                            <span className="font-operational text-[10px] text-muted">
                              {formatTime(e.created_at)}
                            </span>
                            <span className="font-operational text-[10px] text-accent">
                              {e.kind}
                            </span>
                            {e.actor && (
                              <span className="font-operational text-[10px] text-muted">
                                · {e.actor}
                              </span>
                            )}
                          </div>
                          <p className="mt-0.5 text-[12px] leading-snug text-secondary">
                            {e.message}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}
