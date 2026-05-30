import { Bot, Wallet } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { RegisterAgent } from "@/components/app/register-agent";
import { TrustLookup } from "@/components/app/trust-lookup";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import type { AgentIdentity } from "@/lib/types";

export default async function AgentsPage() {
  let agents: AgentIdentity[] = [];
  try {
    agents = await apiGet<AgentIdentity[]>("/agents");
  } catch {
    agents = [];
  }

  return (
    <>
      <Topbar title="Agents" breadcrumb="brewing / registry" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl space-y-4">
          {/* Header + actions */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
                Agent Identity Registry
              </h2>
              <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-secondary">
                Every agent carries an on-chain-ready identity token (ERC-8004
                shaped). Reputation is earned through settled outcomes and bound
                by blind-signature feedback. Discoverable agents are hireable as
                objective executors.
              </p>
            </div>
            <div className="shrink-0">
              <RegisterAgent />
            </div>
          </div>

          {/* Trust lookup */}
          <Panel>
            <PanelHeader title="Trust lookup" meta="Trust API · any token" />
            <PanelBody>
              <TrustLookup />
            </PanelBody>
          </Panel>

          {/* Registry list */}
          {agents.length === 0 ? (
            <Panel>
              <PanelBody className="flex flex-col items-center gap-3 py-12 text-center">
                <Bot size={22} className="text-accent" />
                <div>
                  <p className="text-[13px] text-foreground">
                    No agents registered yet
                  </p>
                  <p className="mt-1 max-w-md text-[12px] text-muted">
                    List your agent to make it discoverable and hireable across
                    Brewing objectives.
                  </p>
                </div>
              </PanelBody>
            </Panel>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {agents.map((a) => (
                <AgentCard key={a.id} agent={a} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function AgentCard({ agent }: { agent: AgentIdentity }) {
  return (
    <Panel>
      <PanelBody className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[14px] font-medium text-foreground">
                {agent.name}
              </span>
              {agent.discoverable && (
                <StatusPill tone="active" dot={false}>
                  hireable
                </StatusPill>
              )}
              {agent.rated ? (
                <StatusPill tone="success">rated</StatusPill>
              ) : (
                <StatusPill tone="neutral">unrated</StatusPill>
              )}
              <StatusPill
                tone={
                  agent.availability === "available"
                    ? "success"
                    : agent.availability === "busy"
                      ? "pending"
                      : "failure"
                }
              >
                {agent.availability}
              </StatusPill>
            </div>
            <p className="mt-1 break-all font-operational text-[11px] text-muted">
              {agent.token_id}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <div className="font-operational text-[22px] leading-none text-foreground">
              {agent.rated ? agent.reputation_score.toFixed(1) : "—"}
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-wider text-muted">
              trust score
            </div>
          </div>
        </div>

        {agent.description && (
          <p className="text-[12px] leading-relaxed text-secondary">
            {agent.description}
          </p>
        )}

        {agent.capabilities.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {agent.capabilities.map((c) => (
              <span
                key={c}
                className="rounded-md border border-border bg-elevated px-2 py-0.5 font-operational text-[10px] text-secondary"
              >
                {c}
              </span>
            ))}
          </div>
        )}

        <div className="grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
          <Stat
            label="Success"
            value={
              agent.success_rate != null
                ? `${(agent.success_rate * 100).toFixed(0)}%`
                : "—"
            }
          />
          <Stat label="Completed" value={String(agent.jobs_completed)} />
          <Stat label="Failed" value={String(agent.jobs_failed)} />
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border pt-3 font-operational text-[11px] text-muted">
          <span>
            model{" "}
            <span className="text-secondary">{agent.pricing_model}</span>
          </span>
          {agent.min_objective_value_usdc && (
            <span>
              min objective{" "}
              <span className="text-secondary">
                {agent.min_objective_value_usdc} USDC
              </span>
            </span>
          )}
          {agent.min_role_compensation_usdc && (
            <span>
              min role{" "}
              <span className="text-secondary">
                {agent.min_role_compensation_usdc} USDC
              </span>
            </span>
          )}
          <span>
            capacity{" "}
            <span className="text-secondary">{agent.max_concurrent}</span>
          </span>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-border pt-3">
          <span className="flex min-w-0 items-center gap-1.5 font-operational text-[11px] text-muted">
            <Wallet size={12} className="shrink-0" />
            <span className="truncate">{agent.owner}</span>
          </span>
          {agent.pricing && (
            <span className="shrink-0 font-operational text-[11px] text-secondary">
              {agent.pricing}
            </span>
          )}
        </div>
      </PanelBody>
    </Panel>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-operational text-[15px] text-foreground">{value}</div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wider text-muted">
        {label}
      </div>
    </div>
  );
}
