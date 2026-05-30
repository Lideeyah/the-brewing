"use client";

import { useState, useTransition } from "react";
import { Loader2, Search, ShieldCheck } from "lucide-react";

import { lookupTrust } from "@/lib/actions";
import type { TrustScore } from "@/lib/types";
import { StatusPill } from "@/components/ui/status-pill";

export function TrustLookup() {
  const [token, setToken] = useState("");
  const [pending, startTransition] = useTransition();
  const [result, setResult] = useState<TrustScore | null>(null);
  const [error, setError] = useState<string | null>(null);

  function run() {
    startTransition(async () => {
      setError(null);
      setResult(null);
      const res = await lookupTrust(token);
      if (res.ok) setResult(res.trust);
      else setError(res.message);
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
          />
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="Query trust by identity token (0x…)"
            className="w-full rounded-lg border border-border bg-background py-2.5 pl-9 pr-3 font-operational text-[12px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
          />
        </div>
        <button
          onClick={run}
          disabled={pending}
          className="flex items-center gap-2 rounded-lg border border-border-strong bg-elevated px-3.5 py-2 text-[13px] font-medium text-foreground transition-colors hover:bg-elevated/70 disabled:opacity-60"
        >
          {pending ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
          Look up
        </button>
      </div>

      {error && (
        <p className="text-[12px] text-failure">{error}</p>
      )}

      {result && (
        <div className="rounded-lg border border-border bg-background p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[14px] font-medium text-foreground">
                  {result.name}
                </span>
                {result.rated ? (
                  <StatusPill tone="success">rated</StatusPill>
                ) : (
                  <StatusPill tone="neutral">unrated</StatusPill>
                )}
              </div>
              <p className="mt-0.5 break-all font-operational text-[11px] text-muted">
                {result.token_id}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <div className="font-operational text-[22px] leading-none text-foreground">
                {result.rated ? result.reputation_score.toFixed(1) : "—"}
              </div>
              <div className="mt-1 text-[10px] uppercase tracking-wider text-muted">
                trust score
              </div>
            </div>
          </div>

          {result.description && (
            <p className="mt-3 text-[12px] leading-relaxed text-secondary">
              {result.description}
            </p>
          )}

          <div className="mt-3 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
            <Stat
              label="Success"
              value={
                result.success_rate != null
                  ? `${(result.success_rate * 100).toFixed(0)}%`
                  : "—"
              }
            />
            <Stat label="Completed" value={String(result.jobs_completed)} />
            <Stat label="Failed" value={String(result.jobs_failed)} />
          </div>

          {result.pricing && (
            <p className="mt-3 font-operational text-[11px] text-muted">
              Pricing: <span className="text-secondary">{result.pricing}</span>
            </p>
          )}
        </div>
      )}
    </div>
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
