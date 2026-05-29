"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Play,
  Wallet,
  XCircle,
} from "lucide-react";

import {
  auditObjective,
  executeObjective,
  settleObjective,
  type LifecycleResult,
} from "@/lib/actions";
import type { ObjectiveStatus } from "@/lib/types";

type Run = () => Promise<LifecycleResult>;

export function LifecycleActions({
  objectiveId,
  status,
  auditApproved,
}: {
  objectiveId: string;
  status: ObjectiveStatus;
  auditApproved?: boolean;
}) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  function run(action: Run) {
    startTransition(async () => {
      setError(null);
      const res = await action();
      if (res.ok) router.refresh();
      else setError(res.message);
    });
  }

  if (
    status !== "escrow_locked" &&
    status !== "under_audit" &&
    status !== "governance_decision"
  ) {
    return null;
  }

  return (
    <div className="space-y-3">
      {status === "escrow_locked" && (
        <button
          disabled={pending}
          onClick={() => run(() => executeObjective(objectiveId))}
          className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {pending ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Play size={15} />
          )}
          Orchestrate execution
        </button>
      )}

      {status === "under_audit" && (
        <div className="flex flex-wrap gap-2">
          <button
            disabled={pending}
            onClick={() => run(() => auditObjective(objectiveId, "approve"))}
            className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {pending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <CheckCircle2 size={15} />
            )}
            Validate &amp; approve
          </button>
          <button
            disabled={pending}
            onClick={() => run(() => auditObjective(objectiveId, "reject"))}
            className="flex items-center gap-2 rounded-lg border border-border-strong px-3.5 py-2 text-[13px] font-medium text-secondary transition-colors hover:text-foreground disabled:opacity-60"
          >
            <XCircle size={15} />
            Reject
          </button>
        </div>
      )}

      {status === "governance_decision" && (
        <button
          disabled={pending}
          onClick={() => run(() => settleObjective(objectiveId))}
          className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
        >
          {pending ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Wallet size={15} />
          )}
          {auditApproved
            ? "Release settlement"
            : "Slash escrow to treasury"}
        </button>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-failure/30 bg-failure/5 p-3">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-failure" />
          <p className="text-[12px] leading-relaxed text-foreground">{error}</p>
        </div>
      )}
    </div>
  );
}
