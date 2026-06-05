import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  Check,
  ExternalLink,
  Fingerprint,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { StructureButton } from "@/components/app/structure-button";
import { LockEscrowButton } from "@/components/app/lock-escrow-button";
import { LifecycleActions } from "@/components/app/lifecycle-actions";
import { NonCustodialNote } from "@/components/app/non-custodial-note";
import { AssignAgent } from "@/components/app/assign-agent";
import { WorkflowPanel } from "@/components/app/workflow-panel";
import { CoordinationPanel } from "@/components/app/coordination-panel";
import { ProvenanceChain } from "@/components/app/provenance-chain";
import { SettlementRationale } from "@/components/app/settlement-rationale";
import { GovernanceRisks } from "@/components/app/governance-risks";
import { EvidenceTrail } from "@/components/app/evidence-trail";
import { Markdown } from "@/components/ui/markdown";
import { OnChainLedger } from "@/components/app/onchain-ledger";
import { ApiError, apiGet } from "@/lib/api";
import type { AgentIdentity, ObjectiveDetail } from "@/lib/types";
import { STATUS_META, eventTone, formatTime, objRef } from "@/lib/objective-ui";

function asArray(v: unknown): string[] {
  return Array.isArray(v) ? v.map((x) => String(x)) : [];
}
function asString(v: unknown): string | null {
  return typeof v === "string" || typeof v === "number" ? String(v) : null;
}

export default async function ObjectiveDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let obj: ObjectiveDetail;
  try {
    obj = await apiGet<ObjectiveDetail>(`/objectives/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    throw err;
  }

  let agents: AgentIdentity[] = [];
  try {
    agents = await apiGet<AgentIdentity[]>("/agents");
  } catch {
    agents = [];
  }

  const meta = STATUS_META[obj.status];
  const gov = obj.governance_config;
  const sla = obj.sla_config;
  const settle = obj.settlement_config;
  const steps = obj.orchestration_plan?.steps ?? [];
  const isDraft = obj.status === "draft";
  const escrow = obj.escrow;
  const canLockEscrow = obj.status === "copilot_structured";
  const execution = obj.execution;
  const agentResults = obj.workflow.filter((r) => r.deliverable);
  const evaluation = obj.evaluation;
  const validation = obj.validation;
  const audit = obj.audit;
  const settlement = obj.settlement;
  const auditApproved = audit?.status === "approved";
  const assignedAgent = obj.assigned_agent;
  const settled = obj.status === "settled" || obj.status === "slashed";

  return (
    <>
      <Topbar title="Objective" breadcrumb={`brewing / objectives / ${objRef(obj.id)}`} />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl">
          <Link
            href="/objectives"
            className="mb-4 inline-flex items-center gap-1.5 text-[12px] text-muted hover:text-foreground"
          >
            <ArrowLeft size={13} /> All objectives
          </Link>

          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <span className="font-operational text-[12px] text-muted">
                  {objRef(obj.id)}
                </span>
                <StatusPill tone={meta.tone}>{meta.label}</StatusPill>
              </div>
              <h2 className="mt-2 text-[20px] font-semibold tracking-tight text-foreground">
                {obj.title}
              </h2>
              {obj.summary && (
                <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-secondary">
                  {obj.summary}
                </p>
              )}
            </div>
            <div className="shrink-0">
              {isDraft ? (
                <StructureButton objectiveId={obj.id} />
              ) : (
                <LifecycleActions
                  objectiveId={obj.id}
                  status={obj.status}
                  hasEvaluation={!!evaluation}
                  auditApproved={auditApproved}
                />
              )}
            </div>
          </div>

          {/* Intent + escrow */}
          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Panel className="lg:col-span-2">
              <PanelHeader title="Operational intent" />
              <PanelBody className="space-y-4">
                <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-secondary">
                  {obj.intent}
                </p>
                {(obj.definition_of_done || obj.deadline) && (
                  <div className="grid grid-cols-1 gap-3 border-t border-border pt-3 sm:grid-cols-2">
                    {obj.definition_of_done && (
                      <div>
                        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                          Definition of done · SLA
                        </p>
                        <p className="mt-1 whitespace-pre-wrap text-[13px] leading-relaxed text-foreground">
                          {obj.definition_of_done}
                        </p>
                      </div>
                    )}
                    {obj.deadline && (
                      <div>
                        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                          Deadline · SLA
                        </p>
                        <p className="mt-1 text-[13px] text-foreground">
                          {obj.deadline}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title="Settlement" />
              <PanelBody className="space-y-3">
                <Field label="Escrow budget" value={`${obj.escrow_amount_usdc} USDC`} mono />
                <Field
                  label="Release condition"
                  value={asString(settle?.release_condition) ?? "—"}
                />
                <Field label="Currency" value={asString(settle?.currency) ?? "USDC"} />

                {escrow && (
                  <div className="space-y-3 border-t border-border pt-3">
                    <div className="flex items-center justify-between">
                      <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                        Escrow
                      </p>
                      <StatusPill tone="success">{escrow.status}</StatusPill>
                    </div>
                    <Field
                      label="Locked"
                      value={`${escrow.amount_usdc} USDC`}
                      mono
                    />
                    {escrow.address && (
                      <div>
                        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                          Escrow account
                        </p>
                        {escrow.explorer_url ? (
                          <a
                            href={escrow.explorer_url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-0.5 inline-flex items-center gap-1 break-all font-operational text-[12px] text-accent hover:underline"
                          >
                            {escrow.address}
                            <ExternalLink size={11} className="shrink-0" />
                          </a>
                        ) : (
                          <p className="mt-0.5 break-all font-operational text-[12px] text-foreground">
                            {escrow.address}
                          </p>
                        )}
                      </div>
                    )}
                    {escrow.lock_tx_url && (
                      <div>
                        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                          Lock proof
                        </p>
                        <a
                          href={escrow.lock_tx_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-0.5 inline-flex items-center gap-1 break-all font-operational text-[12px] text-accent hover:underline"
                        >
                          {escrow.lock_tx_hash ?? "View transaction"}
                          <ExternalLink size={11} className="shrink-0" />
                        </a>
                      </div>
                    )}
                  </div>
                )}

                <NonCustodialNote
                  custodyModel={escrow?.custody_model}
                  controllerWallet={escrow?.controller_wallet}
                />

                {canLockEscrow && (
                  <div className="border-t border-border pt-3">
                    <LockEscrowButton
                      objectiveId={obj.id}
                      amountUsdc={obj.escrow_amount_usdc}
                    />
                    {obj.treasury_address && (
                      <p className="mt-2 break-all font-operational text-[11px] text-muted">
                        From treasury: {obj.treasury_address}
                      </p>
                    )}
                  </div>
                )}
              </PanelBody>
            </Panel>
          </div>

          {/* Executor agent + live reputation */}
          {!isDraft && (
            <Panel className="mt-4">
              <PanelHeader
                title="Executor agent"
                meta="reputation feedback loop"
              />
              <PanelBody className="space-y-3">
                {assignedAgent ? (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link
                          href={`/agents/${assignedAgent.id}`}
                          className="text-[14px] font-medium text-foreground hover:text-accent hover:underline"
                        >
                          {assignedAgent.name}
                        </Link>
                        {assignedAgent.rated ? (
                          <StatusPill tone="success">rated</StatusPill>
                        ) : (
                          <StatusPill tone="neutral">unrated</StatusPill>
                        )}
                      </div>
                      <p className="mt-1 break-all font-operational text-[11px] text-muted">
                        {assignedAgent.token_id}
                      </p>
                      <p className="mt-2 text-[12px] text-muted">
                        {settled
                          ? "Settlement outcome was folded into this agent's reputation automatically."
                          : "On settlement, the outcome updates this agent's trust score automatically."}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="font-operational text-[24px] leading-none text-foreground">
                        {assignedAgent.rated
                          ? assignedAgent.reputation_score.toFixed(1)
                          : "—"}
                      </div>
                      <div className="mt-1 text-[10px] uppercase tracking-wider text-muted">
                        trust score
                      </div>
                      <div className="mt-2 font-operational text-[11px] text-muted">
                        {assignedAgent.jobs_completed}✓ · {assignedAgent.jobs_failed}✗
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-[12px] text-muted">
                    Assign a registered agent as this objective&apos;s executor.
                    Its reputation will move with the settlement outcome.
                  </p>
                )}

                {!settled && (
                  <div className="border-t border-border pt-3">
                    <AssignAgent
                      objectiveId={obj.id}
                      agents={agents}
                      assignedId={assignedAgent?.id ?? null}
                    />
                  </div>
                )}
              </PanelBody>
            </Panel>
          )}

          {!isDraft && (
            <WorkflowPanel
              objectiveId={obj.id}
              roles={obj.workflow}
              feasibility={obj.feasibility}
              agents={agents}
              locked={settled}
            />
          )}

          {!isDraft && obj.coordination && (
            <CoordinationPanel
              objectiveId={obj.id}
              graph={obj.coordination}
              roles={obj.workflow}
            />
          )}

          {isDraft ? (
            <Panel className="mt-4">
              <PanelBody className="flex flex-col items-center gap-3 py-10 text-center">
                <p className="text-[13px] text-foreground">
                  This objective is a draft.
                </p>
                <p className="max-w-md text-[12px] text-muted">
                  Run the Coordination Copilot to structure governance rules,
                  SLA, settlement terms, and an execution-orchestration plan.
                </p>
                <div className="mt-1">
                  <StructureButton objectiveId={obj.id} />
                </div>
              </PanelBody>
            </Panel>
          ) : (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Panel>
                <PanelHeader title="Governance" />
                <PanelBody className="space-y-3">
                  <Field
                    label="Approval policy"
                    value={asString(gov?.approval_policy) ?? "—"}
                  />
                  <div>
                    <p className="mb-1.5 font-operational text-[11px] uppercase tracking-wider text-muted">
                      Validation criteria
                    </p>
                    <ul className="space-y-1.5">
                      {asArray(gov?.validation_criteria).map((c, i) => (
                        <li
                          key={i}
                          className="flex gap-2 text-[13px] text-secondary"
                        >
                          <span className="text-accent">·</span>
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <Field
                    label="Dispute policy"
                    value={asString(gov?.dispute_policy) ?? "—"}
                  />
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHeader title="SLA & Orchestration" />
                <PanelBody className="space-y-3">
                  <Field
                    label="Deadline"
                    value={
                      asString(sla?.deadline_hours)
                        ? `${asString(sla?.deadline_hours)}h`
                        : "—"
                    }
                    mono
                  />
                  <div>
                    <p className="mb-1.5 font-operational text-[11px] uppercase tracking-wider text-muted">
                      Orchestration plan
                    </p>
                    <ol className="space-y-2">
                      {steps.map((s, i) => (
                        <li key={i} className="flex gap-2.5">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-strong font-operational text-[10px] text-accent">
                            {i + 1}
                          </span>
                          <div>
                            <div className="text-[13px] text-foreground">
                              {s.title}
                            </div>
                            {s.detail && (
                              <div className="text-[12px] text-muted">
                                {s.detail}
                              </div>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  </div>
                </PanelBody>
              </Panel>
            </div>
          )}

          {/* Deliverable — the cumulative produced result */}
          {execution?.deliverable && (
            <Panel className="mt-4">
              <PanelHeader title="Deliverable" meta="cumulative result" />
              <PanelBody>
                <div className="max-h-[560px] overflow-y-auto rounded-lg border border-border bg-background p-4">
                  <Markdown>{execution.deliverable}</Markdown>
                </div>
              </PanelBody>
            </Panel>
          )}

          {/* Per-agent results — each role/agent's own contribution */}
          {agentResults.length > 0 && (
            <Panel className="mt-4">
              <PanelHeader
                title="Agent contributions"
                meta={`${agentResults.length} agent${agentResults.length === 1 ? "" : "s"}`}
              />
              <PanelBody className="space-y-2.5">
                {agentResults.map((r) => (
                  <details
                    key={r.id}
                    className="group rounded-lg border border-border bg-background"
                  >
                    <summary className="flex cursor-pointer items-center gap-3 px-4 py-3 text-[13px] text-foreground marker:content-['']">
                      <span className="font-operational text-[10px] uppercase tracking-wider text-accent">
                        {r.role_key}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-medium">
                        {r.assigned_agent?.name ?? r.title}
                      </span>
                      <span className="font-operational text-[11px] text-muted group-open:hidden">
                        view
                      </span>
                    </summary>
                    <div className="border-t border-border px-4 py-3">
                      <Markdown>{r.deliverable ?? ""}</Markdown>
                    </div>
                  </details>
                ))}
              </PanelBody>
            </Panel>
          )}

          {/* Execution orchestration */}
          {execution && (
            <Panel className="mt-4">
              <PanelHeader
                title="Execution orchestration"
                meta={execution.status}
              />
              <PanelBody>
                <details>
                  <summary className="cursor-pointer font-operational text-[11px] uppercase tracking-wider text-muted">
                    Show {execution.steps.length} coordination step
                    {execution.steps.length === 1 ? "" : "s"}
                  </summary>
                  <ol className="mt-3 space-y-3">
                  {execution.steps.map((s) => (
                    <li key={s.id} className="flex gap-2.5">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-strong font-operational text-[10px] text-accent">
                        {s.index + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[13px] text-foreground">
                            {s.title}
                          </span>
                          <StatusPill
                            tone={s.status === "completed" ? "success" : "pending"}
                          >
                            {s.status}
                          </StatusPill>
                        </div>
                        {s.output && (
                          <p className="mt-0.5 text-[12px] text-muted">
                            {s.output}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                  </ol>
                </details>
              </PanelBody>
            </Panel>
          )}

          {/* Independent validation (evidence-bound, executor-independent) */}
          {validation && (
            <Panel className="mt-4">
              <PanelHeader
                title="Independent validation"
                meta={`${validation.validator?.name ?? "Validator"} · evidence-bound`}
              />
              <PanelBody className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <ShieldCheck size={14} className="text-accent" />
                  <span className="text-[12px] text-muted">
                    Validator recommendation
                  </span>
                  <StatusPill tone={recMeta(validation.recommendation).tone}>
                    {recMeta(validation.recommendation).label}
                  </StatusPill>
                  <span className="font-operational text-[11px] text-muted">
                    {Math.round(validation.confidence * 100)}% confidence
                  </span>
                  {validation.independent_of_executor && (
                    <StatusPill tone="neutral" dot={false}>
                      independent of executor
                    </StatusPill>
                  )}
                </div>

                {validation.reasoning && (
                  <p className="text-[13px] leading-relaxed text-secondary">
                    {validation.reasoning}
                  </p>
                )}

                {validation.findings.length > 0 && (
                  <div>
                    <p className="mb-2 font-operational text-[11px] uppercase tracking-wider text-muted">
                      Evidence reviewed
                    </p>
                    <ul className="space-y-1.5">
                      {validation.findings.map((f, i) => (
                        <li
                          key={i}
                          className="flex items-center gap-2 text-[12px] text-secondary"
                        >
                          <span
                            className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                              f.errors
                                ? "bg-failure"
                                : f.quality === "strong"
                                  ? "bg-success"
                                  : "bg-pending"
                            }`}
                          />
                          <span className="truncate text-foreground">
                            {f.step_title ?? `Step ${(f.step_index ?? 0) + 1}`}
                          </span>
                          <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                            {f.output_kind} · {f.quality}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex items-start gap-2 border-t border-border pt-3">
                  <Fingerprint size={13} className="mt-0.5 shrink-0 text-muted" />
                  <div className="min-w-0">
                    <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                      Evidence hash
                    </p>
                    <p className="mt-0.5 break-all font-operational text-[11px] text-secondary">
                      {validation.evidence_hash}
                    </p>
                  </div>
                </div>

                {validation.outcome != null && (
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="text-muted">Reconciled vs. decision:</span>
                    <StatusPill tone={validation.upheld ? "success" : "failure"}>
                      {validation.upheld ? "upheld" : "overturned"}
                    </StatusPill>
                  </div>
                )}

                <p className="border-t border-border pt-3 text-[11px] text-muted">
                  Validation is performed by an identity distinct from the
                  executor and bound to a hash of the exact evidence reviewed —
                  execution never validates itself.
                </p>
              </PanelBody>
            </Panel>
          )}

          {/* Settlement rationale — "why did this agent get paid?" */}
          {obj.authorization && (
            <SettlementRationale
              authorization={obj.authorization}
              settlement={settlement}
            />
          )}

          {/* Evidence audit trail — output → evidence → validation → settlement */}
          {obj.evidence_trail && (
            <details className="mt-4 rounded-xl border border-border bg-surface">
              <summary className="cursor-pointer px-5 py-3.5 text-[13px] font-medium text-foreground">
                Evidence audit trail
                <span className="ml-2 font-operational text-[11px] text-muted">
                  output → evidence → validation → settlement
                </span>
              </summary>
              <div className="border-t border-border">
                <EvidenceTrail trail={obj.evidence_trail} />
              </div>
            </details>
          )}

          {/* AI governance evaluation (advisory) */}
          {evaluation && (
            <Panel className="mt-4">
              <PanelHeader
                title="Governance evaluation"
                meta={`Copilot · ${evaluation.source}`}
              />
              <PanelBody className="space-y-4">
                <div className="flex items-center gap-2">
                  <Sparkles size={14} className="text-accent" />
                  <span className="text-[12px] text-muted">
                    Copilot recommendation
                  </span>
                  <StatusPill tone={recMeta(evaluation.recommendation).tone}>
                    {recMeta(evaluation.recommendation).label}
                  </StatusPill>
                </div>

                {evaluation.reasoning && (
                  <p className="text-[13px] leading-relaxed text-secondary">
                    {evaluation.reasoning}
                  </p>
                )}

                <div>
                  <p className="mb-2 font-operational text-[11px] uppercase tracking-wider text-muted">
                    Criteria findings
                  </p>
                  <ul className="space-y-2">
                    {evaluation.findings.map((f, i) => (
                      <li key={i} className="flex gap-2.5">
                        <span
                          className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full ${
                            f.met
                              ? "bg-success/15 text-success"
                              : "bg-failure/15 text-failure"
                          }`}
                        >
                          {f.met ? <Check size={11} /> : <X size={11} />}
                        </span>
                        <div className="min-w-0">
                          <div className="text-[13px] text-foreground">
                            {f.criterion}
                          </div>
                          {f.assessment && (
                            <div className="text-[12px] text-muted">
                              {f.assessment}
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>

                {evaluation.risks && evaluation.risks.length > 0 && (
                  <GovernanceRisks risks={evaluation.risks} />
                )}

                {evaluation.conditions.length > 0 && (
                  <div>
                    <p className="mb-1.5 font-operational text-[11px] uppercase tracking-wider text-muted">
                      Conditions
                    </p>
                    <ul className="space-y-1.5">
                      {evaluation.conditions.map((c, i) => (
                        <li
                          key={i}
                          className="flex gap-2 text-[13px] text-secondary"
                        >
                          <span className="text-pending">·</span>
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="border-t border-border pt-3 text-[11px] text-muted">
                  Advisory only — a human reviewer issues the binding decision and
                  may override this recommendation.
                </p>
              </PanelBody>
            </Panel>
          )}

          {/* Validation + settlement outcome */}
          {(audit || settlement) && (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              {audit && (
                <Panel>
                  <PanelHeader title="Reviewer decision" meta="human-authoritative" />
                  <PanelBody className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                        Decision
                      </p>
                      <div className="flex items-center gap-1.5">
                        {audit.overridden && (
                          <StatusPill tone="pending" dot={false}>
                            override
                          </StatusPill>
                        )}
                        <StatusPill tone={auditApproved ? "success" : "failure"}>
                          {audit.status}
                        </StatusPill>
                      </div>
                    </div>
                    {audit.recommendation && (
                      <Field
                        label="Copilot recommended"
                        value={recMeta(audit.recommendation).label}
                      />
                    )}
                    {audit.notes && (
                      <p className="text-[13px] leading-relaxed text-secondary">
                        {audit.notes}
                      </p>
                    )}
                  </PanelBody>
                </Panel>
              )}

              {settlement && (
                <Panel>
                  <PanelHeader title="Settlement" />
                  <PanelBody className="space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                        Outcome
                      </p>
                      <StatusPill
                        tone={
                          settlement.status === "settled" ? "success" : "failure"
                        }
                      >
                        {settlement.status}
                      </StatusPill>
                    </div>
                    <Field
                      label={
                        settlement.status === "settled"
                          ? "Released to counterparty"
                          : "Returned to treasury"
                      }
                      value={`${settlement.amount_usdc} USDC`}
                      mono
                    />
                    <Field
                      label={
                        settlement.fee_basis
                          ? `Governed fee (${settlement.fee_basis})`
                          : "Governed fee"
                      }
                      value={`${settlement.fee_usdc} USDC`}
                      mono
                    />
                    {settlement.payout_address && (
                      <div>
                        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                          Payout account
                        </p>
                        {settlement.explorer_url ? (
                          <a
                            href={settlement.explorer_url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-0.5 inline-flex items-center gap-1 break-all font-operational text-[12px] text-accent hover:underline"
                          >
                            {settlement.payout_address}
                            <ExternalLink size={11} className="shrink-0" />
                          </a>
                        ) : (
                          <p className="mt-0.5 break-all font-operational text-[12px] text-foreground">
                            {settlement.payout_address}
                          </p>
                        )}
                      </div>
                    )}
                    {settlement.payout_tx_url && (
                      <div>
                        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                          Payout proof
                        </p>
                        <a
                          href={settlement.payout_tx_url}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-0.5 inline-flex items-center gap-1 break-all font-operational text-[12px] text-accent hover:underline"
                        >
                          {settlement.payout_tx_hash ?? "View transaction"}
                          <ExternalLink size={11} className="shrink-0" />
                        </a>
                      </div>
                    )}
                    <NonCustodialNote
                      custodyModel={escrow?.custody_model}
                      controllerWallet={escrow?.controller_wallet}
                    />
                  </PanelBody>
                </Panel>
              )}
            </div>
          )}

          {/* On-chain traceability — capital custody chain */}
          {!isDraft && (escrow || settlement) && (
            <Panel className="mt-4">
              <PanelHeader
                title="On-chain traceability"
                meta="treasury → escrow → validation → settlement"
              />
              <PanelBody>
                <ProvenanceChain
                  treasuryAddress={obj.treasury_address}
                  escrow={escrow}
                  validation={validation}
                  settlement={settlement}
                />
                <p className="mt-4 border-t border-border pt-3 text-[11px] text-muted">
                  Every hop that has settled on-chain carries a verifiable
                  proof — a transaction hash, an evidence hash, or an explorer
                  link — so the path from locked capital to final disbursement
                  is auditable end to end.
                </p>
              </PanelBody>
            </Panel>
          )}

          {/* On-chain movement ledger — every USDC transfer + proof */}
          {!isDraft && obj.onchain_ledger && (
            <OnChainLedger ledger={obj.onchain_ledger} />
          )}

          {/* Governance timeline */}
          <Panel className="mt-4">
            <PanelHeader title="Governance timeline" meta="append-only" />
            <PanelBody className="space-y-4">
              {obj.timeline.map((e, i) => {
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
                      {i < obj.timeline.length - 1 && (
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
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}

type RecTone = "success" | "pending" | "failure" | "neutral";

function recMeta(rec: string): { tone: RecTone; label: string } {
  switch (rec) {
    case "approved":
      return { tone: "success", label: "Approved" };
    case "approved_with_conditions":
      return { tone: "pending", label: "Approved with conditions" };
    case "rejected":
      return { tone: "failure", label: "Rejected" };
    default:
      return { tone: "neutral", label: rec };
  }
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
        {label}
      </p>
      <p
        className={`mt-0.5 text-[13px] text-foreground ${mono ? "font-operational" : ""}`}
      >
        {value}
      </p>
    </div>
  );
}
