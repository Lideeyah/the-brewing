import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { StructureButton } from "@/components/app/structure-button";
import { LockEscrowButton } from "@/components/app/lock-escrow-button";
import { LifecycleActions } from "@/components/app/lifecycle-actions";
import { ApiError, apiGet } from "@/lib/api";
import type { ObjectiveDetail } from "@/lib/types";
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

  const meta = STATUS_META[obj.status];
  const gov = obj.governance_config;
  const sla = obj.sla_config;
  const settle = obj.settlement_config;
  const steps = obj.orchestration_plan?.steps ?? [];
  const isDraft = obj.status === "draft";
  const escrow = obj.escrow;
  const canLockEscrow = obj.status === "copilot_structured";
  const execution = obj.execution;
  const audit = obj.audit;
  const settlement = obj.settlement;
  const auditApproved = audit?.status === "approved";

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
                  auditApproved={auditApproved}
                />
              )}
            </div>
          </div>

          {/* Intent + escrow */}
          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Panel className="lg:col-span-2">
              <PanelHeader title="Operational intent" />
              <PanelBody>
                <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-secondary">
                  {obj.intent}
                </p>
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
                  </div>
                )}

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

          {/* Execution orchestration */}
          {execution && (
            <Panel className="mt-4">
              <PanelHeader
                title="Execution orchestration"
                meta={execution.status}
              />
              <PanelBody>
                <ol className="space-y-3">
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
              </PanelBody>
            </Panel>
          )}

          {/* Validation + settlement outcome */}
          {(audit || settlement) && (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              {audit && (
                <Panel>
                  <PanelHeader title="Governance validation" />
                  <PanelBody className="space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                        Decision
                      </p>
                      <StatusPill
                        tone={auditApproved ? "success" : "failure"}
                      >
                        {audit.status}
                      </StatusPill>
                    </div>
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
                      label="Governed fee (2.5%)"
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
                  </PanelBody>
                </Panel>
              )}
            </div>
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
