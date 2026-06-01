import Link from "next/link";
import { ShieldCheck, Scale } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import type { Objective, Overview } from "@/lib/types";
import { STATUS_META, eventTone, formatTime, objRef } from "@/lib/objective-ui";

const GOVERNANCE_KINDS = [
  "structur",
  "evaluat",
  "decision",
  "approv",
  "reject",
  "audit",
  "govern",
  "dispute",
];

function isGovernanceEvent(kind: string): boolean {
  const k = kind.toLowerCase();
  return GOVERNANCE_KINDS.some((g) => k.includes(g));
}

export default async function GovernancePage() {
  let overview: Overview | null = null;
  let objectives: Objective[] = [];
  try {
    [overview, objectives] = await Promise.all([
      apiGet<Overview>("/workspaces/current/overview"),
      apiGet<Objective[]>("/objectives"),
    ]);
  } catch {
    overview = null;
    objectives = [];
  }

  const decisions = (overview?.recent_events ?? []).filter((e) =>
    isGovernanceEvent(e.kind),
  );
  const inGovernance = objectives.filter(
    (o) => o.status === "under_audit" || o.status === "governance_decision",
  );

  return (
    <>
      <Topbar title="Governance" breadcrumb="brewing / governance" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
              Governance
            </h2>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-secondary">
              Every settlement is gated by an explicit decision. The Coordination
              Copilot evaluates execution evidence against each objective&apos;s
              validation criteria and produces an advisory recommendation — but a
              human reviewer always issues the binding call, and may override it.
            </p>
          </div>

          {/* Objectives currently in governance */}
          <Panel>
            <PanelHeader
              title="Open for decision"
              meta={`${inGovernance.length} awaiting`}
            />
            <PanelBody className="p-0">
              {inGovernance.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-10 text-center">
                  <ShieldCheck size={20} className="text-accent" />
                  <p className="text-[13px] text-foreground">
                    Nothing awaiting governance
                  </p>
                  <p className="max-w-md text-[12px] text-muted">
                    Objectives appear here once execution completes and evidence
                    is ready to be evaluated and decided.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {inGovernance.map((o) => {
                    const meta = STATUS_META[o.status];
                    return (
                      <Link
                        key={o.id}
                        href={`/objectives/${o.id}`}
                        className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-elevated/40"
                      >
                        <span className="font-operational text-[11px] text-muted">
                          {objRef(o.id)}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-[13px] text-foreground">
                            {o.title}
                          </div>
                          <div className="mt-0.5 font-operational text-[11px] text-muted">
                            {o.escrow_amount_usdc} USDC at stake
                          </div>
                        </div>
                        <StatusPill tone={meta.tone}>{meta.label}</StatusPill>
                      </Link>
                    );
                  })}
                </div>
              )}
            </PanelBody>
          </Panel>

          {/* Decision record */}
          <Panel>
            <PanelHeader title="Decision record" meta="append-only" />
            <PanelBody className="p-0">
              {decisions.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-10 text-center">
                  <Scale size={20} className="text-accent" />
                  <p className="text-[13px] text-foreground">
                    No governance events yet
                  </p>
                  <p className="max-w-md text-[12px] text-muted">
                    Structuring, evaluation, and decision events are recorded here
                    as objectives move through the loop.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {decisions.map((e) => {
                    const tone = eventTone(e.kind);
                    return (
                      <li
                        key={e.id}
                        className="flex items-start gap-3 px-5 py-3.5"
                      >
                        <span
                          className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                            tone === "success"
                              ? "bg-success"
                              : tone === "failure"
                                ? "bg-failure"
                                : tone === "active"
                                  ? "bg-accent"
                                  : "bg-muted"
                          }`}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
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
                        <span className="shrink-0 font-operational text-[10px] text-muted">
                          {formatTime(e.created_at)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}
