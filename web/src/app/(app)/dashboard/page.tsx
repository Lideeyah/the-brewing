import Link from "next/link";
import { ArrowUpRight, Sparkles } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { LifecyclePipeline } from "@/components/app/lifecycle-pipeline";
import { NonCustodialNote } from "@/components/app/non-custodial-note";
import { QuickCoordinate } from "@/components/app/quick-coordinate";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import type { Kpis, Overview } from "@/lib/types";
import {
  STATUS_META,
  eventTone,
  formatTime,
  objRef,
} from "@/lib/objective-ui";

export default async function DashboardPage() {
  let overview: Overview | null = null;
  try {
    overview = await apiGet<Overview>("/workspaces/current/overview");
  } catch {
    overview = null;
  }

  let kpis: Kpis | null = null;
  try {
    kpis = await apiGet<Kpis>("/analytics/kpis");
  } catch {
    kpis = null;
  }

  const metrics = overview?.metrics ?? [];
  const kpiMetrics = kpis?.metrics ?? [];
  const objectives = overview?.objectives ?? [];
  const events = overview?.recent_events ?? [];
  const statusCounts = overview?.status_counts ?? {};
  const totalObjectives = Object.values(statusCounts).reduce((a, b) => a + b, 0);

  return (
    <>
      <Topbar title="Mission Control" breadcrumb="brewing / operations" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {/* Quick coordinate launcher — start an objective + set its budget here */}
        <Panel className="mb-4 bg-surface">
          <PanelHeader title="New objective" meta="set budget → coordinate" />
          <PanelBody>
            <QuickCoordinate />
          </PanelBody>
        </Panel>

        {/* Operational metrics */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {metrics.map((m) => (
            <Panel key={m.label} className="bg-surface">
              <PanelBody className="p-4">
                {m.hint && (
                  <div className="flex items-start justify-start">
                    <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                      {m.hint}
                    </span>
                  </div>
                )}
                <div className="mt-3 font-operational text-[24px] leading-none tracking-tight text-foreground">
                  {m.value}
                </div>
                <div className="mt-2 text-[12px] text-secondary">{m.label}</div>
              </PanelBody>
            </Panel>
          ))}
        </div>

        <NonCustodialNote className="mt-4" />

        {/* Governed settlement KPIs — board-level network health */}
        {kpiMetrics.length > 0 && (
          <Panel className="mt-4">
            <PanelHeader title="Settlement KPIs" meta="all-time" />
            <div className="grid grid-cols-2 divide-x divide-y divide-border lg:grid-cols-5">
              {kpiMetrics.map((m) => (
                <div key={m.key} className="p-4">
                  <div className="font-operational text-[20px] leading-none tracking-tight text-foreground">
                    {m.value}
                  </div>
                  <div className="mt-2 text-[12px] text-secondary">{m.label}</div>
                  {m.hint && (
                    <div className="mt-1 text-[10px] leading-snug text-muted">
                      {m.hint}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Panel>
        )}

        {/* Lifecycle pipeline — the Intent -> Settlement loop at a glance */}
        {totalObjectives > 0 && (
          <Panel className="mt-4">
            <PanelHeader
              title="Lifecycle"
              meta="Intent → Settlement"
            />
            <LifecyclePipeline statusCounts={statusCounts} />
          </Panel>
        )}

        {/* Coordination + timeline */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Panel className="lg:col-span-2">
            <PanelHeader
              title="Coordination Overview"
              meta={`${objectives.length} objective${objectives.length === 1 ? "" : "s"}`}
              action={
                <Link
                  href="/objectives"
                  className="flex items-center gap-1 text-[12px] text-secondary hover:text-foreground"
                >
                  View all <ArrowUpRight size={13} />
                </Link>
              }
            />
            {objectives.length === 0 ? (
              <EmptyObjectives />
            ) : (
              <div className="divide-y divide-border">
                {objectives.map((o) => {
                  const meta = STATUS_META[o.status];
                  return (
                    <Link
                      key={o.id}
                      href={`/objectives/${o.id}`}
                      className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-elevated/40"
                    >
                      <span className="font-operational text-[11px] text-muted">
                        {objRef(o.id)}
                      </span>
                      <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">
                        {o.title}
                      </span>
                      <span className="font-operational text-[11px] text-secondary">
                        {o.escrow_amount_usdc} USDC
                      </span>
                      <StatusPill tone={meta.tone}>{meta.label}</StatusPill>
                    </Link>
                  );
                })}
              </div>
            )}
          </Panel>

          <Panel>
            <PanelHeader title="Governance Timeline" meta="live" />
            {events.length === 0 ? (
              <PanelBody>
                <p className="text-[12px] text-muted">
                  No governance events yet. Coordinate an objective to begin the
                  lifecycle.
                </p>
              </PanelBody>
            ) : (
              <PanelBody className="space-y-4">
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
                        <div className="flex flex-wrap items-center gap-2">
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
              </PanelBody>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}

function EmptyObjectives() {
  return (
    <PanelBody className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <Sparkles size={20} className="text-accent" />
      <div>
        <p className="text-[13px] text-foreground">No objectives yet</p>
        <p className="mt-1 text-[12px] text-muted">
          Express an operational intent and the Coordination Copilot will
          structure it.
        </p>
      </div>
      <Link
        href="/coordinate"
        className="mt-1 rounded-lg bg-foreground px-3 py-1.5 text-[13px] font-medium text-background hover:opacity-90"
      >
        Coordinate an objective
      </Link>
    </PanelBody>
  );
}
