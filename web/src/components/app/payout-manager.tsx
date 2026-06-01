"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  ShieldCheck,
  ShieldAlert,
  Wallet,
  Copy,
  Check,
} from "lucide-react";

import { requestPayoutChallenge, verifyPayoutAddress } from "@/lib/actions";
import type { PayoutAddressEvent, PayoutChallenge } from "@/lib/types";
import { StatusPill } from "@/components/ui/status-pill";

function actionTone(
  action: string,
): "success" | "pending" | "failure" | "neutral" {
  if (action === "registered" || action === "changed") return "success";
  if (action === "verification_failed") return "failure";
  if (action === "cleared") return "neutral";
  return "pending"; // challenge_issued
}

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

const inputCls =
  "w-full rounded-lg border border-border bg-background px-3.5 py-2.5 font-operational text-[12px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none";

export function PayoutManager({
  agentId,
  address,
  blockchain,
  verified,
  verifiedAt,
  history,
}: {
  agentId: string;
  address?: string | null;
  blockchain?: string | null;
  verified: boolean;
  verifiedAt?: string | null;
  history: PayoutAddressEvent[];
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const [open, setOpen] = useState(false);
  const [addr, setAddr] = useState("");
  const [chain, setChain] = useState(blockchain ?? "SOL-DEVNET");
  const [challenge, setChallenge] = useState<PayoutChallenge | null>(null);
  const [signature, setSignature] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function issueChallenge() {
    startTransition(async () => {
      setError(null);
      const res = await requestPayoutChallenge(agentId, addr, chain);
      if (res.ok) setChallenge(res.challenge);
      else setError(res.message);
    });
  }

  function verify() {
    startTransition(async () => {
      setError(null);
      const res = await verifyPayoutAddress(agentId, signature);
      if (res.ok) {
        setOpen(false);
        setChallenge(null);
        setSignature("");
        setAddr("");
        router.refresh();
      } else {
        setError(res.message);
      }
    });
  }

  function copyChallenge() {
    if (!challenge) return;
    navigator.clipboard?.writeText(challenge.challenge).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className="space-y-4">
      {/* Current state */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Wallet size={14} className="shrink-0 text-muted" />
            <span className="text-[12px] text-muted">Settlement destination</span>
            {address ? (
              verified ? (
                <StatusPill tone="success">verified</StatusPill>
              ) : (
                <StatusPill tone="pending">unverified</StatusPill>
              )
            ) : (
              <StatusPill tone="neutral">none</StatusPill>
            )}
          </div>
          {address ? (
            <p className="mt-1.5 break-all font-operational text-[12px] text-foreground">
              {address}
            </p>
          ) : (
            <p className="mt-1.5 text-[12px] text-muted">
              No payout address registered. Until one is proven, settlement falls
              back to a freshly minted wallet.
            </p>
          )}
          {address && verified && verifiedAt && (
            <p className="mt-1 font-operational text-[11px] text-muted">
              proven {formatTime(verifiedAt)}
            </p>
          )}
        </div>
        <button
          onClick={() => {
            setOpen((v) => !v);
            setError(null);
            setChallenge(null);
          }}
          className="shrink-0 rounded-lg border border-border bg-elevated px-3 py-1.5 text-[12px] font-medium text-foreground transition-colors hover:bg-elevated/70"
        >
          {address ? "Change address" : "Register address"}
        </button>
      </div>

      {/* Proof-of-control flow */}
      {open && (
        <div className="space-y-3 rounded-lg border border-border bg-background p-4">
          <div className="flex items-center gap-2">
            <ShieldCheck size={14} className="text-accent" />
            <p className="text-[12px] font-medium text-foreground">
              Prove control of the payout wallet
            </p>
          </div>
          <p className="text-[11px] leading-relaxed text-muted">
            Brewing never holds the key. The wallet signs a one-time challenge
            client-side; only the signature is submitted. The address is bound as
            a settlement destination only after the signature verifies against it.
          </p>

          {/* Step 1: candidate address → challenge */}
          {!challenge ? (
            <div className="space-y-2.5">
              <input
                value={addr}
                onChange={(e) => setAddr(e.target.value)}
                placeholder="Payout wallet address (base58)"
                className={inputCls}
              />
              <input
                value={chain}
                onChange={(e) => setChain(e.target.value)}
                placeholder="Blockchain (e.g. SOL-DEVNET)"
                className={inputCls}
              />
              <button
                onClick={issueChallenge}
                disabled={pending || !addr.trim()}
                className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {pending ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <ShieldCheck size={15} />
                )}
                Issue challenge
              </button>
            </div>
          ) : (
            /* Step 2: sign challenge → verify */
            <div className="space-y-2.5">
              <div>
                <div className="flex items-center justify-between">
                  <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
                    Challenge to sign
                  </p>
                  <button
                    onClick={copyChallenge}
                    className="flex items-center gap-1 text-[11px] text-accent hover:underline"
                  >
                    {copied ? <Check size={11} /> : <Copy size={11} />}
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded-md border border-border bg-elevated p-2.5 font-operational text-[11px] leading-relaxed text-secondary">
                  {challenge.challenge}
                </pre>
                <p className="mt-1 font-operational text-[10px] text-muted">
                  for {challenge.address}
                </p>
              </div>
              <input
                value={signature}
                onChange={(e) => setSignature(e.target.value)}
                placeholder="Signature (base58 or hex)"
                className={inputCls}
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={verify}
                  disabled={pending || !signature.trim()}
                  className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
                >
                  {pending ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <ShieldCheck size={15} />
                  )}
                  Verify &amp; bind
                </button>
                <button
                  onClick={() => setChallenge(null)}
                  className="rounded-lg border border-border px-3 py-2 text-[12px] text-secondary hover:text-foreground"
                >
                  Back
                </button>
              </div>
            </div>
          )}

          {error && (
            <p className="flex items-center gap-1.5 text-[12px] text-failure">
              <ShieldAlert size={13} className="shrink-0" />
              {error}
            </p>
          )}
        </div>
      )}

      {/* Audit trail */}
      {history.length > 0 && (
        <div className="border-t border-border pt-3">
          <p className="mb-2 font-operational text-[11px] uppercase tracking-wider text-muted">
            Payout audit trail
          </p>
          <ul className="space-y-2">
            {history.map((ev) => (
              <li key={ev.id} className="flex items-start gap-2.5">
                <span className="mt-0.5 shrink-0">
                  <StatusPill tone={actionTone(ev.action)} dot={false}>
                    {ev.action.replace(/_/g, " ")}
                  </StatusPill>
                </span>
                <div className="min-w-0 flex-1">
                  {ev.new_address && (
                    <p className="break-all font-operational text-[11px] text-secondary">
                      {ev.new_address}
                    </p>
                  )}
                  {ev.note && (
                    <p className="text-[11px] text-muted">{ev.note}</p>
                  )}
                </div>
                <span className="shrink-0 font-operational text-[10px] text-muted">
                  {formatTime(ev.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
