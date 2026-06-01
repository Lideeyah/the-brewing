import Link from "next/link";
import { ClipboardCheck, ArrowRight } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import type { Objective } from "@/lib/types";
import { STATUS_META, formatTime, objRef } from "@/lib/objective-ui";

const AWAITING = new Set(["under_audit", "governance_decision"]);
const DECIDED = new Set(["settled", "slashed"]);

function ObjectiveRow({ o, cta }: { o: Objective; cta?: boolean }) {
  const meta = STATUS_META[o.status];
  return (
    <Link
      href={`/objectives/${o.id}`}
      className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-elevated/40"
    >
      <span className="font-operational text-[11px] text-muted">
        {objRef(o.id)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] text-foreground">{o.title}</div>
        <div className="mt-0.5 font-operational text-[11px] text-muted">
          {o.escrow_amount_usdc} USDC · {formatTime(o.updated_at)}
        </div>
      </div>
      <StatusPill tone={meta.tone}>{meta.label}</StatusPill>
      {cta && <ArrowRight size={14} className="shrink-0 text-muted" />}
    </Link>
  );
}

export default async function AuditorPage() {
  let objectives: Objective[] = [];
  try {
    objectives = await apiGet<Objective[]>("/objectives");
  } catch {
    objectives = [];
  }

  const awaiting = objectives.filter((o) => AWAITING.has(o.status));
  const decided = objectives.filter((o) => DECIDED.has(o.status)).slice(0, 10);

  return (
    <>
      <Topbar title="Auditor" breadcrumb="brewing / auditor" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
              Auditor Worklist
            </h2>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-secondary">
              The human-authoritative review queue. Each objective here has
              execution evidence ready; open it to evaluate, then issue the
              binding approve or reject decision that releases or slashes escrow.
            </p>
          </div>

          {/* Awaiting decision */}
          <Panel>
            <PanelHeader
              title="Awaiting decision"
              meta={`${awaiting.length} in queue`}
            />
            <PanelBody className="p-0">
              {awaiting.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                  <ClipboardCheck size={22} className="text-accent" />
                  <p className="text-[13px] text-foreground">Queue is clear</p>
                  <p className="max-w-md text-[12px] text-muted">
                    No objectives are currently awaiting a reviewer decision. They
                    arrive here after execution and evaluation.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {awaiting.map((o) => (
                    <ObjectiveRow key={o.id} o={o} cta />
                  ))}
                </div>
              )}
            </PanelBody>
          </Panel>

          {/* Recently decided */}
          {decided.length > 0 && (
            <Panel>
              <PanelHeader title="Recently decided" meta="settled / slashed" />
              <PanelBody className="p-0">
                <div className="divide-y divide-border">
                  {decided.map((o) => (
                    <ObjectiveRow key={o.id} o={o} />
                  ))}
                </div>
              </PanelBody>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
