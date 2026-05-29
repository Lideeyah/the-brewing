"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ExternalLink, Loader2, Lock } from "lucide-react";

import { lockEscrow, type LockEscrowResult } from "@/lib/actions";

export function LockEscrowButton({
  objectiveId,
  amountUsdc,
}: {
  objectiveId: string;
  amountUsdc: string;
}) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<Exclude<LockEscrowResult, { ok: true }> | null>(
    null,
  );
  const router = useRouter();

  return (
    <div className="space-y-3">
      <button
        disabled={pending}
        onClick={() =>
          startTransition(async () => {
            setError(null);
            const res = await lockEscrow(objectiveId);
            if (res.ok) {
              router.refresh();
            } else {
              setError(res);
            }
          })
        }
        className="flex items-center gap-2 rounded-lg bg-foreground px-3.5 py-2 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
      >
        {pending ? (
          <>
            <Loader2 size={15} className="animate-spin" />
            Locking escrow…
          </>
        ) : (
          <>
            <Lock size={15} />
            Lock {amountUsdc} USDC into escrow
          </>
        )}
      </button>

      {error && (
        <div className="rounded-lg border border-failure/30 bg-failure/5 p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-failure" />
            <div className="space-y-2">
              <p className="text-[12px] leading-relaxed text-foreground">
                {error.message ?? "Failed to lock escrow."}
              </p>
              {error.error === "insufficient_treasury_balance" && (
                <div className="space-y-1.5">
                  {error.treasury_address && (
                    <p className="break-all font-operational text-[11px] text-muted">
                      Treasury: {error.treasury_address}
                    </p>
                  )}
                  <a
                    href="https://faucet.circle.com"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[12px] text-accent hover:underline"
                  >
                    Fund treasury via Circle faucet
                    <ExternalLink size={12} />
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
