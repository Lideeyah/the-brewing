import {
  ArrowUpRight,
  CircleDollarSign,
  GitBranch,
  ShieldCheck,
  Target,
} from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";

// Placeholder operational data — wired to the API in the next slice.
const metrics = [
  { label: "Active Objectives", value: "7", delta: "+2", icon: Target },
  { label: "Escrowed (USDC)", value: "4,200", delta: "locked", icon: CircleDollarSign },
  { label: "Pending Governance", value: "3", delta: "review", icon: ShieldCheck },
  { label: "Settlement Rate", value: "96.4%", delta: "+1.2%", icon: GitBranch },
];

const objectives = [
  {
    id: "OBJ-7F3A",
    title: "Competitive intelligence — African AI startups",
    stage: "Executing",
    tone: "active" as const,
    escrow: "1,000",
    sla: "48h",
  },
  {
    id: "OBJ-1C90",
    title: "Smart contract security audit — settlement module",
    stage: "Under Audit",
    tone: "pending" as const,
    escrow: "2,500",
    sla: "72h",
  },
  {
    id: "OBJ-04BD",
    title: "Compliance documentation — Q2 treasury activity",
    stage: "Settled",
    tone: "success" as const,
    escrow: "700",
    sla: "—",
  },
  {
    id: "OBJ-9AE2",
    title: "Market research — stablecoin settlement rails",
    stage: "Governance",
    tone: "pending" as const,
    escrow: "1,200",
    sla: "24h",
  },
];

const timeline = [
  { t: "13:42:08", kind: "settlement.released", msg: "OBJ-04BD settled — 700 USDC routed to payee", tone: "success" as const },
  { t: "13:39:51", kind: "audit.approved", msg: "OBJ-04BD passed SLA validation", tone: "success" as const },
  { t: "13:31:20", kind: "escrow.locked", msg: "OBJ-9AE2 locked 1,200 USDC", tone: "active" as const },
  { t: "13:28:03", kind: "objective.created", msg: "OBJ-9AE2 structured by Coordination Copilot", tone: "neutral" as const },
  { t: "12:58:44", kind: "governance.disputed", msg: "OBJ-1C90 escalated to auditor review", tone: "failure" as const },
];

export default function DashboardPage() {
  return (
    <>
      <Topbar title="Mission Control" breadcrumb="brewing / operations" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        {/* Operational metrics */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {metrics.map((m) => (
            <Panel key={m.label} className="bg-surface">
              <PanelBody className="p-4">
                <div className="flex items-start justify-between">
                  <m.icon size={16} className="text-muted" />
                  <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                    {m.delta}
                  </span>
                </div>
                <div className="mt-3 font-operational text-[26px] leading-none tracking-tight text-foreground">
                  {m.value}
                </div>
                <div className="mt-2 text-[12px] text-secondary">{m.label}</div>
              </PanelBody>
            </Panel>
          ))}
        </div>

        {/* Coordination + timeline */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Panel className="lg:col-span-2">
            <PanelHeader
              title="Coordination Overview"
              meta="4 active"
              action={
                <button className="flex items-center gap-1 text-[12px] text-secondary hover:text-foreground">
                  View all <ArrowUpRight size={13} />
                </button>
              }
            />
            <div className="divide-y divide-border">
              {objectives.map((o) => (
                <div
                  key={o.id}
                  className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-elevated/40"
                >
                  <span className="font-operational text-[11px] text-muted">
                    {o.id}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[13px] text-foreground">
                    {o.title}
                  </span>
                  <span className="font-operational text-[11px] text-secondary">
                    {o.escrow} USDC
                  </span>
                  <span className="w-10 text-right font-operational text-[11px] text-muted">
                    {o.sla}
                  </span>
                  <StatusPill tone={o.tone}>{o.stage}</StatusPill>
                </div>
              ))}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Governance Timeline" meta="live" />
            <PanelBody className="space-y-4">
              {timeline.map((e, i) => (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <span
                      className={`mt-1 h-2 w-2 rounded-full ${
                        e.tone === "success"
                          ? "bg-success"
                          : e.tone === "failure"
                            ? "bg-failure"
                            : e.tone === "active"
                              ? "bg-accent"
                              : "bg-muted"
                      }`}
                    />
                    {i < timeline.length - 1 && (
                      <span className="mt-1 w-px flex-1 bg-border" />
                    )}
                  </div>
                  <div className="pb-1">
                    <div className="flex items-center gap-2">
                      <span className="font-operational text-[10px] text-muted">
                        {e.t}
                      </span>
                      <span className="font-operational text-[10px] text-accent">
                        {e.kind}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[12px] leading-snug text-secondary">
                      {e.msg}
                    </p>
                  </div>
                </div>
              ))}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}
