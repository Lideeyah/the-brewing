"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Check,
  Loader2,
  Lock,
  ShieldCheck,
  X,
} from "lucide-react";

import { commitFeedback, revealFeedback } from "@/lib/actions";
import type { AgentFeedback, FeedbackCommitment } from "@/lib/types";
import { StatusPill } from "@/components/ui/status-pill";

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function FeedbackPanel({
  agentId,
  feedback,
}: {
  agentId: string;
  feedback: AgentFeedback;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);

  const open = feedback.objectives.filter((o) => !o.committed);

  function commit() {
    if (!selected) return;
    startTransition(async () => {
      setError(null);
      const res = await commitFeedback(agentId, selected);
      if (res.ok) {
        setSelected("");
        router.refresh();
      } else {
        setError(res.message);
      }
    });
  }

  return (
    <div className="space-y-4">
      <p className="text-[12px] leading-relaxed text-muted">
        Blind-signature feedback binds this agent to its evaluation{" "}
        <span className="text-secondary">before</span> the outcome is revealed.
        The signature is captured at commit time, so the agent cannot decline a
        review once it sees a negative result — selective participation is
        structurally impossible.
      </p>

      {/* Commit a new feedback round */}
      <div className="space-y-2 rounded-lg border border-border bg-background p-4">
        <div className="flex items-center gap-2">
          <Lock size={13} className="text-accent" />
          <p className="text-[12px] font-medium text-foreground">
            Commit feedback
          </p>
        </div>
        {open.length === 0 ? (
          <p className="text-[12px] text-muted">
            No objectives available to commit. Feedback can be committed for any
            objective this agent contributed to that isn&apos;t already bound.
          </p>
        ) : (
          <div className="flex gap-2">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full appearance-none rounded-lg border border-border bg-background px-3 py-2.5 text-[13px] text-foreground focus:border-border-strong focus:outline-none"
            >
              <option value="">Select an objective…</option>
              {open.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.title} · {o.status}
                </option>
              ))}
            </select>
            <button
              onClick={commit}
              disabled={pending || !selected}
              className="flex shrink-0 items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {pending ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <Lock size={14} />
              )}
              Commit
            </button>
          </div>
        )}
        {error && (
          <div className="flex items-start gap-2 text-[12px] text-failure">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Commitment audit trail */}
      {feedback.commitments.length === 0 ? (
        <p className="text-[12px] text-muted">
          No commitments yet. Once feedback is committed it appears here as a
          signed, pre-reveal record.
        </p>
      ) : (
        <div className="border-t border-border pt-3">
          <p className="mb-2 font-operational text-[11px] uppercase tracking-wider text-muted">
            Commitment trail
          </p>
          <ul className="space-y-2.5">
            {feedback.commitments.map((c) => (
              <CommitmentRow key={c.id} agentId={agentId} commitment={c} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function CommitmentRow({
  agentId,
  commitment: c,
}: {
  agentId: string;
  commitment: FeedbackCommitment;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [note, setNote] = useState("");
  const [revealing, setRevealing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reveal(success: boolean) {
    startTransition(async () => {
      setError(null);
      const res = await revealFeedback(agentId, c.id, success, note);
      if (res.ok) router.refresh();
      else setError(res.message);
    });
  }

  return (
    <li className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {c.revealed ? (
              <StatusPill tone={c.outcome === "success" ? "success" : "failure"}>
                {c.outcome ?? "revealed"}
              </StatusPill>
            ) : (
              <StatusPill tone="pending">committed</StatusPill>
            )}
            <Link
              href={`/objectives/${c.objective_id}`}
              className="truncate text-[12px] text-foreground hover:underline"
            >
              {c.objective_title ?? "objective"}
            </Link>
          </div>
          <p className="mt-1 break-all font-operational text-[10px] text-muted">
            {c.commitment_hash.slice(0, 24)}… · sig {c.signature.slice(0, 12)}…
          </p>
        </div>
        <span className="shrink-0 font-operational text-[10px] text-muted">
          {formatTime(c.created_at)}
        </span>
      </div>

      {/* Reveal controls — only while still bound */}
      {!c.revealed && (
        <div className="mt-2.5 space-y-2 border-t border-border pt-2.5">
          {revealing ? (
            <>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Note (optional) — the evidence behind this outcome"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-[12px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={() => reveal(true)}
                  disabled={pending}
                  className="flex items-center gap-1.5 rounded-lg bg-foreground px-3 py-2 text-[12px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {pending ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Check size={14} />
                  )}
                  Reveal success
                </button>
                <button
                  onClick={() => reveal(false)}
                  disabled={pending}
                  className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-[12px] font-medium text-failure transition-colors hover:border-failure/50 disabled:opacity-50"
                >
                  <X size={14} />
                  Reveal failure
                </button>
                <button
                  onClick={() => {
                    setRevealing(false);
                    setError(null);
                  }}
                  className="rounded-lg px-2 py-2 text-[12px] text-secondary hover:text-foreground"
                >
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <button
              onClick={() => setRevealing(true)}
              className="flex items-center gap-1.5 text-[12px] text-accent hover:underline"
            >
              <ShieldCheck size={13} /> Reveal outcome
            </button>
          )}
          {error && (
            <div className="flex items-start gap-2 text-[12px] text-failure">
              <AlertTriangle size={13} className="mt-0.5 shrink-0" />
              {error}
            </div>
          )}
        </div>
      )}

      {c.revealed && c.revealed_at && (
        <p className="mt-2 font-operational text-[10px] text-muted">
          revealed {formatTime(c.revealed_at)}
        </p>
      )}
    </li>
  );
}
