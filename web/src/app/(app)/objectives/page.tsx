import Link from "next/link";
import { Plus } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import type { Objective } from "@/lib/types";
import { STATUS_META, formatTime, objRef } from "@/lib/objective-ui";

export default async function ObjectivesPage() {
  let objectives: Objective[] = [];
  try {
    objectives = await apiGet<Objective[]>("/objectives");
  } catch {
    objectives = [];
  }

  return (
    <>
      <Topbar title="Objectives" breadcrumb="brewing / objectives" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <Panel>
          <PanelHeader
            title="All objectives"
            meta={`${objectives.length} total`}
            action={
              <Link
                href="/coordinate"
                className="flex items-center gap-1.5 rounded-lg border border-border bg-elevated px-2.5 py-1 text-[12px] text-secondary hover:text-foreground"
              >
                <Plus size={13} /> New
              </Link>
            }
          />

          {objectives.length === 0 ? (
            <PanelBody>
              <p className="text-[13px] text-muted">
                No objectives yet.{" "}
                <Link href="/coordinate" className="text-accent hover:underline">
                  Coordinate one
                </Link>{" "}
                to begin.
              </p>
            </PanelBody>
          ) : (
            <div className="divide-y divide-border">
              {objectives.map((o) => {
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
                        {formatTime(o.created_at)}
                      </div>
                    </div>
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
      </div>
    </>
  );
}
