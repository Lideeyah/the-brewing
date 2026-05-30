"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  Loader2,
  Pencil,
  Users,
  X,
} from "lucide-react";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { assignRole, updateRoleAllocation } from "@/lib/actions";
import type {
  AgentIdentity,
  FeasibilityReport,
  WorkflowRole,
} from "@/lib/types";

const ROLE_TONE: Record<
  WorkflowRole["status"],
  "success" | "pending" | "failure" | "active"
> = {
  pending: "pending",
  assigned: "active",
  completed: "success",
  failed: "failure",
};

function RoleRow({
  objectiveId,
  role,
  agents,
  locked,
}: {
  objectiveId: string;
  role: WorkflowRole;
  agents: AgentIdentity[];
  locked: boolean;
}) {
  const [selected, setSelected] = useState(role.assigned_agent_id ?? "");
  const [pending, startTransition] = useTransition();
  const [issues, setIssues] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [alloc, setAlloc] = useState(role.allocation_usdc);
  const [allocPending, startAllocTransition] = useTransition();
  const router = useRouter();

  function save() {
    if (!selected || selected === role.assigned_agent_id) return;
    startTransition(async () => {
      setIssues([]);
      setError(null);
      const res = await assignRole(objectiveId, role.id, selected);
      if (res.ok) {
        router.refresh();
      } else if (res.issues?.length) {
        setIssues(res.issues);
      } else {
        setError(res.message);
      }
    });
  }

  function saveAllocation() {
    const next = alloc.trim();
    if (!next || next === role.allocation_usdc) {
      setEditing(false);
      return;
    }
    startAllocTransition(async () => {
      setError(null);
      const res = await updateRoleAllocation(objectiveId, role.id, next);
      if (res.ok) {
        setEditing(false);
        router.refresh();
      } else {
        setError(res.message);
      }
    });
  }

  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
              {role.role_key}
            </span>
            <span className="text-[13px] font-medium text-foreground">
              {role.title}
            </span>
            <StatusPill tone={ROLE_TONE[role.status]}>{role.status}</StatusPill>
          </div>
          {role.description && (
            <p className="mt-1 max-w-xl text-[12px] leading-relaxed text-muted">
              {role.description}
            </p>
          )}
          {role.assigned_agent && (
            <p className="mt-1.5 flex items-center gap-1.5 text-[12px] text-secondary">
              <Bot size={12} className="text-accent" />
              {role.assigned_agent.name}
              {role.assigned_agent.rated
                ? ` · ${role.assigned_agent.reputation_score.toFixed(0)} trust`
                : " · unrated"}
            </p>
          )}
        </div>
        <div className="shrink-0 text-right">
          {editing ? (
            <div className="flex items-center gap-1.5">
              <input
                value={alloc}
                onChange={(e) => setAlloc(e.target.value)}
                inputMode="decimal"
                autoFocus
                className="w-24 rounded-lg border border-border bg-background px-2 py-1 text-right font-operational text-[13px] text-foreground focus:border-border-strong focus:outline-none"
              />
              <button
                onClick={saveAllocation}
                disabled={allocPending}
                className="rounded-md p-1 text-success hover:bg-elevated disabled:opacity-50"
                aria-label="Save allocation"
              >
                {allocPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Check size={14} />
                )}
              </button>
              <button
                onClick={() => {
                  setAlloc(role.allocation_usdc);
                  setEditing(false);
                }}
                className="rounded-md p-1 text-muted hover:bg-elevated"
                aria-label="Cancel"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-end gap-1.5">
              <div className="font-operational text-[15px] leading-none text-foreground">
                {role.allocation_usdc}
              </div>
              {!locked && (
                <button
                  onClick={() => setEditing(true)}
                  className="rounded-md p-1 text-muted hover:bg-elevated hover:text-foreground"
                  aria-label="Edit allocation"
                >
                  <Pencil size={12} />
                </button>
              )}
            </div>
          )}
          <div className="mt-1 text-[10px] uppercase tracking-wider text-muted">
            {role.outcome ? role.outcome : "USDC"}
          </div>
        </div>
      </div>

      {!locked && (
        <div className="mt-3 flex gap-2 border-t border-border pt-3">
          <div className="relative flex-1">
            <Bot
              size={13}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
            />
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full appearance-none rounded-lg border border-border bg-background py-2 pl-8 pr-3 text-[12px] text-foreground focus:border-border-strong focus:outline-none"
            >
              <option value="">Select an agent…</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                  {a.availability !== "available" ? ` · ${a.availability}` : ""}
                  {a.min_role_compensation_usdc
                    ? ` · min ${a.min_role_compensation_usdc}`
                    : ""}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={save}
            disabled={pending || !selected || selected === role.assigned_agent_id}
            className="flex items-center gap-1.5 rounded-lg bg-foreground px-3 py-1.5 text-[12px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {pending ? <Loader2 size={13} className="animate-spin" /> : null}
            {role.assigned_agent_id ? "Reassign" : "Assign"}
          </button>
        </div>
      )}

      {issues.length > 0 && (
        <ul className="mt-2 space-y-1">
          {issues.map((iss, i) => (
            <li
              key={i}
              className="flex items-start gap-2 text-[12px] text-failure"
            >
              <AlertTriangle size={13} className="mt-0.5 shrink-0" />
              {iss}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <div className="mt-2 flex items-start gap-2 text-[12px] text-failure">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}

export function WorkflowPanel({
  objectiveId,
  roles,
  feasibility,
  agents,
  locked,
}: {
  objectiveId: string;
  roles: WorkflowRole[];
  feasibility?: FeasibilityReport | null;
  agents: AgentIdentity[];
  locked: boolean;
}) {
  if (roles.length === 0) return null;

  const assignedCount = roles.filter((r) => r.assigned_agent_id).length;

  return (
    <Panel className="mt-4">
      <PanelHeader
        title="Workflow"
        meta={`${roles.length} role${roles.length === 1 ? "" : "s"} · ${assignedCount} assigned`}
      />
      <PanelBody className="space-y-3">
        <p className="flex items-center gap-1.5 text-[12px] text-muted">
          <Users size={13} className="text-accent" />
          The objective is decomposed into independently assignable roles. Each
          role carries its own settlement allocation and is filled by a separate
          agent.
        </p>

        {feasibility && (
          <div
            className={`rounded-lg border p-3 ${
              feasibility.feasible
                ? "border-success/30 bg-success/5"
                : "border-failure/30 bg-failure/5"
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {feasibility.feasible ? (
                  <CheckCircle2 size={15} className="text-success" />
                ) : (
                  <AlertTriangle size={15} className="text-failure" />
                )}
                <span className="text-[13px] font-medium text-foreground">
                  {feasibility.feasible
                    ? "Workflow is feasible"
                    : "Workflow is not yet feasible"}
                </span>
              </div>
              <div className="text-right font-operational text-[11px] text-muted">
                {feasibility.required_usdc} / {feasibility.budget_usdc} USDC
              </div>
            </div>
            {feasibility.recommendations.length > 0 && (
              <ul className="mt-2 space-y-1">
                {feasibility.recommendations.map((rec, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-[12px] text-secondary"
                  >
                    <span className="text-accent">·</span>
                    {rec}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="space-y-2">
          {roles.map((role) => (
            <RoleRow
              key={role.id}
              objectiveId={objectiveId}
              role={role}
              agents={agents}
              locked={locked}
            />
          ))}
        </div>
      </PanelBody>
    </Panel>
  );
}
