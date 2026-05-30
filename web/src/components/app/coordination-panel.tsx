"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Ban,
  Bot,
  CheckCircle2,
  Coins,
  GitBranch,
  Loader2,
  Lock,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { GovernanceRisks } from "@/components/app/governance-risks";
import { settleSubtask, validateSubtask } from "@/lib/actions";
import type {
  CoordinationGraph,
  CoordinationNode,
  WorkflowRole,
} from "@/lib/types";

type Tone = "success" | "pending" | "failure" | "neutral" | "active";

const VALIDATION_TONE: Record<string, Tone> = {
  pending: "pending",
  passed: "success",
  failed: "failure",
};
const SETTLEMENT_TONE: Record<string, Tone> = {
  pending: "neutral",
  settled: "success",
  slashed: "failure",
};
const DEP_STATE_META: Record<string, { tone: Tone; label: string }> = {
  ready: { tone: "active", label: "ready" },
  blocked: { tone: "pending", label: "blocked" },
  blocked_failed: { tone: "failure", label: "dependency failed" },
  cycle: { tone: "failure", label: "dependency cycle" },
};
const REC_TONE: Record<string, Tone> = {
  approved: "success",
  approved_with_conditions: "pending",
  rejected: "failure",
};
const REC_LABEL: Record<string, string> = {
  approved: "approved",
  approved_with_conditions: "approved · conditions",
  rejected: "rejected",
};

function criterionText(c: string | Record<string, unknown>): string {
  if (typeof c === "string") return c;
  const d = c["description"] ?? c["text"] ?? c["key"];
  return typeof d === "string" ? d : JSON.stringify(c);
}

/**
 * Coordination graph — the objective's sub-tasks as a dependency-ordered DAG.
 *
 * Renders the execution order (topological waves), each sub-task's contract
 * (dependencies, success criteria, evidence requirements, budget) and its own
 * validation + settlement state, with per-sub-task validate/settle actions. A
 * sub-task can only be validated once its prerequisites have passed, and only
 * settled once it has been validated — and the parent objective stays gated
 * until every required sub-task passes. This is coordination as the primitive:
 * one objective, many dependent sub-tasks, each independently verifiable and
 * independently settleable.
 */
export function CoordinationPanel({
  objectiveId,
  graph,
  roles,
}: {
  objectiveId: string;
  graph: CoordinationGraph;
  roles: WorkflowRole[];
}) {
  if (!graph || graph.nodes.length === 0) return null;

  const rolesById = new Map(roles.map((r) => [r.id, r]));
  const nodesById = new Map(graph.nodes.map((n) => [n.role_id, n]));
  const titleById = (id: string) => nodesById.get(id)?.title ?? "sub-task";

  return (
    <Panel className="mt-4">
      <PanelHeader
        title="Coordination graph"
        meta={`${graph.nodes.length} sub-tasks · ${graph.waves.length} execution wave${
          graph.waves.length === 1 ? "" : "s"
        }`}
      />
      <PanelBody className="space-y-4">
        <p className="flex items-center gap-1.5 text-[12px] text-muted">
          <GitBranch size={13} className="text-accent" />
          The objective is decomposed into dependent sub-tasks. Each settles
          independently once it passes its own validation; the parent objective
          settles only after every required sub-task passes.
        </p>

        {/* Parent settle gate */}
        <div
          className={`flex flex-wrap items-center gap-2 rounded-lg border p-3 ${
            graph.parent_settleable
              ? "border-success/30 bg-success/5"
              : "border-border bg-elevated"
          }`}
        >
          {graph.parent_settleable ? (
            <CheckCircle2 size={15} className="text-success" />
          ) : (
            <Lock size={15} className="text-muted" />
          )}
          <span className="text-[13px] font-medium text-foreground">
            {graph.parent_settleable
              ? "All required sub-tasks passed — parent objective can settle"
              : "Parent objective is gated on required sub-tasks"}
          </span>
          <span className="font-operational text-[11px] text-muted">
            {graph.required_passed}/{graph.required_total} required passed
            {graph.required_failed > 0 ? ` · ${graph.required_failed} failed` : ""}
          </span>
          {graph.has_cycle && (
            <StatusPill tone="failure" dot={false}>
              dependency cycle detected
            </StatusPill>
          )}
        </div>

        {/* Execution waves */}
        <div className="space-y-3">
          {graph.waves.map((wave, wi) => (
            <div key={wi} className="rounded-lg border border-border">
              <div className="flex items-center gap-2 border-b border-border px-3 py-2">
                <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                  Wave {wi + 1}
                </span>
                <span className="text-[11px] text-muted">
                  {wi === 0
                    ? "no prerequisites — starts first"
                    : "runs after its dependencies pass"}
                </span>
              </div>
              <div className="space-y-2 p-2">
                {wave.map((roleId) => {
                  const node = nodesById.get(roleId);
                  const role = rolesById.get(roleId);
                  if (!node || !role) return null;
                  return (
                    <SubTaskCard
                      key={roleId}
                      objectiveId={objectiveId}
                      node={node}
                      role={role}
                      titleById={titleById}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </PanelBody>
    </Panel>
  );
}

function SubTaskCard({
  objectiveId,
  node,
  role,
  titleById,
}: {
  objectiveId: string;
  node: CoordinationNode;
  role: WorkflowRole;
  titleById: (id: string) => string;
}) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const dep = DEP_STATE_META[node.dependency_state] ?? {
    tone: "neutral" as Tone,
    label: node.dependency_state,
  };
  const canValidate = node.ready; // deps satisfied + not yet validated
  const canSettle =
    node.validation_status !== "pending" && node.settlement_status === "pending";

  function run(action: "validate" | "settle") {
    startTransition(async () => {
      setError(null);
      const res =
        action === "validate"
          ? await validateSubtask(objectiveId, role.id)
          : await settleSubtask(objectiveId, role.id);
      if (res.ok) router.refresh();
      else setError(res.message);
    });
  }

  const auth = role.authorization;

  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
              {role.role_key}
            </span>
            <span className="text-[13px] font-medium text-foreground">
              {role.title}
            </span>
            {role.required ? (
              <StatusPill tone="neutral" dot={false}>
                required
              </StatusPill>
            ) : (
              <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                optional
              </span>
            )}
            <StatusPill tone={dep.tone} dot={false}>
              {dep.label}
            </StatusPill>
          </div>

          {role.assigned_agent ? (
            <p className="mt-1.5 flex items-center gap-1.5 text-[12px] text-secondary">
              <Bot size={12} className="text-accent" />
              {role.assigned_agent.name}
              {role.assigned_agent.rated
                ? ` · ${role.assigned_agent.reputation_score.toFixed(0)} trust`
                : " · unrated"}
            </p>
          ) : (
            <p className="mt-1.5 text-[12px] text-muted">No agent assigned.</p>
          )}

          {node.depends_on.length > 0 && (
            <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
              <ArrowRight size={11} className="text-muted" />
              depends on{" "}
              {node.depends_on.map((d, i) => (
                <span key={d} className="text-secondary">
                  {titleById(d)}
                  {i < node.depends_on.length - 1 ? "," : ""}
                </span>
              ))}
            </p>
          )}
        </div>

        <div className="shrink-0 text-right">
          <div className="font-operational text-[15px] leading-none text-foreground">
            {role.allocation_usdc}
          </div>
          <div className="mt-1 font-operational text-[10px] uppercase tracking-wider text-muted">
            {role.outcome ?? "USDC"}
          </div>
        </div>
      </div>

      {/* Sub-task contract: success criteria + evidence requirements */}
      {role.success_criteria.length > 0 && (
        <div className="mt-3 space-y-1.5 border-t border-border pt-3">
          <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
            Success criteria
          </p>
          <ul className="space-y-1">
            {role.success_criteria.map((c, i) => (
              <li
                key={i}
                className="flex gap-2 text-[12px] leading-relaxed text-secondary"
              >
                <span className="text-accent">·</span>
                {criterionText(c)}
              </li>
            ))}
          </ul>
          {role.required_evidence_kinds.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
                evidence
              </span>
              {role.required_evidence_kinds.map((k) => (
                <span
                  key={k}
                  className="rounded border border-border bg-elevated px-1.5 py-0.5 font-operational text-[10px] text-secondary"
                >
                  {k.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Validation + settlement state */}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <span className="flex items-center gap-1.5 text-[12px] text-muted">
          <ShieldCheck size={13} className="text-muted" />
          validation
        </span>
        <StatusPill tone={VALIDATION_TONE[node.validation_status] ?? "neutral"}>
          {node.validation_status}
        </StatusPill>
        <span className="flex items-center gap-1.5 text-[12px] text-muted">
          <Coins size={13} className="text-muted" />
          settlement
        </span>
        <StatusPill tone={SETTLEMENT_TONE[node.settlement_status] ?? "neutral"}>
          {node.settlement_status}
        </StatusPill>
        {auth && (
          <span className="font-operational text-[11px] text-muted">
            {auth.criteria_satisfied}/{auth.criteria_total} criteria satisfied
          </span>
        )}
      </div>

      {/* Per-sub-task "why paid" binding */}
      {auth && node.settlement_status === "settled" && (
        <p className="mt-2 break-all font-operational text-[10px] text-muted">
          bound to {auth.evidence_hash}
        </p>
      )}

      {/* Advisory Copilot reasoning scoped to this sub-task */}
      {role.evaluation && (
        <div className="mt-3 space-y-2 rounded-lg border border-border bg-elevated/50 p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <Sparkles size={12} className="text-accent" />
            <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
              Copilot review
            </span>
            <StatusPill
              tone={REC_TONE[role.evaluation.recommendation] ?? "neutral"}
              dot={false}
            >
              {REC_LABEL[role.evaluation.recommendation] ??
                role.evaluation.recommendation}
            </StatusPill>
            <span className="font-operational text-[10px] text-muted">
              advisory
            </span>
          </div>
          {role.evaluation.reasoning && (
            <p className="text-[12px] leading-relaxed text-secondary">
              {role.evaluation.reasoning}
            </p>
          )}
          {role.evaluation.risks && role.evaluation.risks.length > 0 && (
            <GovernanceRisks risks={role.evaluation.risks} compact />
          )}
          {role.evaluation.conditions.length > 0 && (
            <ul className="space-y-1">
              {role.evaluation.conditions.map((c, i) => (
                <li
                  key={i}
                  className="flex gap-1.5 text-[11px] leading-relaxed text-secondary"
                >
                  <span className="text-pending">·</span>
                  {c}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          onClick={() => run("validate")}
          disabled={pending || !canValidate}
          className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12px] font-medium text-foreground transition-colors hover:bg-elevated disabled:opacity-40"
        >
          {pending ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <ShieldCheck size={13} />
          )}
          Validate sub-task
        </button>
        <button
          onClick={() => run("settle")}
          disabled={pending || !canSettle}
          className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-opacity disabled:opacity-40 ${
            node.validation_status === "failed"
              ? "bg-failure/90 text-background hover:opacity-90"
              : "bg-foreground text-background hover:opacity-90"
          }`}
        >
          {pending ? (
            <Loader2 size={13} className="animate-spin" />
          ) : node.validation_status === "failed" ? (
            <Ban size={13} />
          ) : (
            <Coins size={13} />
          )}
          {node.validation_status === "failed"
            ? "Slash allocation"
            : "Settle sub-task"}
        </button>

        {node.settlement_status === "settled" && (
          <span className="flex items-center gap-1 text-[11px] text-success">
            <CheckCircle2 size={12} /> released
          </span>
        )}
        {node.settlement_status === "slashed" && (
          <span className="flex items-center gap-1 text-[11px] text-failure">
            <XCircle size={12} /> slashed
          </span>
        )}
      </div>

      {error && (
        <div className="mt-2 flex items-start gap-2 text-[12px] text-failure">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
