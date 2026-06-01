"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, Bot, Loader2 } from "lucide-react";

import { assignAgent } from "@/lib/actions";
import type { AgentIdentity } from "@/lib/types";

export function AssignAgent({
  objectiveId,
  agents,
  assignedId,
}: {
  objectiveId: string;
  agents: AgentIdentity[];
  assignedId?: string | null;
}) {
  const [selected, setSelected] = useState(assignedId ?? "");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  if (agents.length === 0) {
    return (
      <p className="text-[12px] text-muted">
        No registered agents yet. Register one on the{" "}
        <Link href="/agents" className="text-accent hover:underline">
          Agents
        </Link>{" "}
        page to assign an executor.
      </p>
    );
  }

  function save() {
    if (!selected || selected === assignedId) return;
    startTransition(async () => {
      setError(null);
      const res = await assignAgent(objectiveId, selected);
      if (res.ok) router.refresh();
      else setError(res.message);
    });
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Bot
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
          />
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full appearance-none rounded-lg border border-border bg-background py-2.5 pl-9 pr-3 text-[13px] text-foreground focus:border-border-strong focus:outline-none"
          >
            <option value="">Select an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
                {a.rated ? ` · ${a.reputation_score.toFixed(0)} trust` : " · unrated"}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={save}
          disabled={pending || !selected || selected === assignedId}
          className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {pending ? <Loader2 size={15} className="animate-spin" /> : null}
          {assignedId ? "Reassign" : "Assign"}
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-2 text-[12px] text-failure">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
