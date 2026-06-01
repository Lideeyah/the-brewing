import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ShieldCheck, Wallet, Activity } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { TrustDimensions } from "@/components/app/trust-dimensions";
import { PayoutManager } from "@/components/app/payout-manager";
import { FeedbackPanel } from "@/components/app/feedback-panel";
import { ApiError, apiGet } from "@/lib/api";
import type { AgentDetail, AgentFeedback } from "@/lib/types";
import { formatTime } from "@/lib/objective-ui";

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

export default async function AgentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let agent: AgentDetail;
  try {
    agent = await apiGet<AgentDetail>(`/agents/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  let feedback: AgentFeedback = { commitments: [], objectives: [] };
  try {
    feedback = await apiGet<AgentFeedback>(`/agents/${id}/feedback`);
  } catch {
    // Non-fatal: the feedback panel degrades to an empty state.
  }

  return (
    <>
      <Topbar title="Agent" breadcrumb="brewing / registry / agent" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl">
          <Link
            href="/agents"
            className="mb-4 inline-flex items-center gap-1.5 text-[12px] text-muted hover:text-foreground"
          >
            <ArrowLeft size={13} /> Registry
          </Link>

          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-[20px] font-semibold tracking-tight text-foreground">
                  {agent.name}
                </h2>
                {agent.rated ? (
                  <span className="inline-flex items-center gap-1">
                    <ShieldCheck size={14} className="text-success" />
                    <StatusPill tone="success">verified</StatusPill>
                  </span>
                ) : (
                  <StatusPill tone="neutral">unverified</StatusPill>
                )}
                {agent.discoverable && (
                  <StatusPill tone="active" dot={false}>
                    hireable
                  </StatusPill>
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
              <p className="mt-2 break-all font-operational text-[11px] text-muted">
                {agent.token_id}
              </p>
              {agent.description && (
                <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-secondary">
                  {agent.description}
                </p>
              )}
            </div>
            <div className="shrink-0 text-right">
              <div className="font-operational text-[28px] leading-none text-foreground">
                {agent.rated ? agent.reputation_score.toFixed(1) : "—"}
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-wider text-muted">
                trust score
              </div>
            </div>
          </div>

          {/* Stats + economics */}
          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Panel className="lg:col-span-2">
              <PanelHeader title="Track record" meta="settled outcomes" />
              <PanelBody className="space-y-4">
                <div className="grid grid-cols-3 gap-2 text-center">
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

                {agent.capabilities.length > 0 && (
                  <div className="border-t border-border pt-3">
                    <p className="mb-2 font-operational text-[11px] uppercase tracking-wider text-muted">
                      Capabilities
                    </p>
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
                  </div>
                )}

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
                  {agent.pricing && (
                    <span>
                      pricing{" "}
                      <span className="text-secondary">{agent.pricing}</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1.5 border-t border-border pt-3 font-operational text-[11px] text-muted">
                  <Wallet size={12} className="shrink-0" />
                  <span className="break-all">{agent.owner}</span>
                </div>
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader title="Reputation dimensions" meta="evidence-backed" />
              <PanelBody>
                {agent.trust_dimensions.length > 0 ? (
                  <TrustDimensions dimensions={agent.trust_dimensions} />
                ) : (
                  <p className="text-[12px] text-muted">
                    No dimensional signal yet. Reputation accrues from settled
                    outcomes, so axes populate as this agent completes work.
                  </p>
                )}
              </PanelBody>
            </Panel>
          </div>

          {/* Payout destination — Escrow V1.5 proof-of-control */}
          <Panel className="mt-4">
            <PanelHeader
              title="Payout destination"
              meta="proof-of-control · Escrow V1.5"
            />
            <PanelBody>
              <PayoutManager
                agentId={agent.id}
                address={agent.payout_address}
                blockchain={agent.payout_blockchain}
                verified={agent.payout_address_verified}
                verifiedAt={agent.payout_address_verified_at}
                history={agent.payout_history}
              />
            </PanelBody>
          </Panel>

          {/* Blind-signature feedback — commit then reveal */}
          <Panel className="mt-4">
            <PanelHeader
              title="Blind-signature feedback"
              meta="commit before reveal"
            />
            <PanelBody>
              <FeedbackPanel agentId={agent.id} feedback={feedback} />
            </PanelBody>
          </Panel>

          {/* Reputation history */}
          <Panel className="mt-4">
            <PanelHeader
              title="Reputation history"
              meta={`${agent.reputation_history.length} events`}
            />
            <PanelBody className="p-0">
              {agent.reputation_history.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-10 text-center">
                  <Activity size={20} className="text-accent" />
                  <p className="text-[13px] text-foreground">No outcomes yet</p>
                  <p className="max-w-md text-[12px] text-muted">
                    Each settled objective folds an outcome into this timeline,
                    moving the trust score with evidence.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {agent.reputation_history.map((ev) => {
                    const up = ev.delta >= 0;
                    return (
                      <li
                        key={ev.id}
                        className="flex items-center gap-3 px-5 py-3.5"
                      >
                        <span
                          className={`font-operational text-[13px] ${
                            up ? "text-success" : "text-failure"
                          }`}
                        >
                          {up ? "+" : ""}
                          {ev.delta.toFixed(2)}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-operational text-[10px] text-accent">
                              {ev.kind}
                            </span>
                            {ev.objective_id && (
                              <Link
                                href={`/objectives/${ev.objective_id}`}
                                className="font-operational text-[10px] text-muted hover:text-foreground hover:underline"
                              >
                                objective
                              </Link>
                            )}
                          </div>
                          {ev.note && (
                            <p className="mt-0.5 text-[12px] text-secondary">
                              {ev.note}
                            </p>
                          )}
                        </div>
                        <span className="shrink-0 font-operational text-[11px] text-muted">
                          score {ev.score_after.toFixed(1)}
                        </span>
                        <span className="shrink-0 font-operational text-[10px] text-muted">
                          {formatTime(ev.created_at)}
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
