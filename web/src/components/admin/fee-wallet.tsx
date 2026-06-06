"use client";

import { useActionState } from "react";

import { withdrawFees } from "@/lib/admin-actions";

type State =
  | { ok: true; message: string; explorer?: string }
  | { ok: false; message: string }
  | null;

export function FeeWallet({
  address,
  balance,
}: {
  address?: string | null;
  balance?: string | null;
}) {
  const [state, action, pending] = useActionState<State, FormData>(
    async (_prev, formData) => withdrawFees(formData),
    null,
  );

  if (!address) {
    return (
      <p className="px-5 py-4 text-[12px] text-muted">
        No platform fee wallet configured. Set PLATFORM_FEE_WALLET_ADDRESS and
        PLATFORM_FEE_WALLET_ID.
      </p>
    );
  }

  return (
    <div className="space-y-4 p-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
            Available balance
          </p>
          <p className="mt-1 font-operational text-[28px] leading-none text-foreground">
            {balance ?? "—"} <span className="text-[15px] text-muted">USDC</span>
          </p>
        </div>
        <a
          href={`https://explorer.solana.com/address/${address}?cluster=devnet`}
          target="_blank"
          rel="noreferrer"
          className="text-[12px] text-accent hover:underline"
        >
          View on explorer ↗
        </a>
      </div>

      <div className="border-t border-border pt-3">
        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
          Wallet address
        </p>
        <p className="mt-0.5 break-all font-operational text-[12px] text-foreground">
          {address}
        </p>
      </div>

      <form action={action} className="space-y-2.5 border-t border-border pt-3">
        <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
          Withdraw
        </p>
        <input
          name="destination_address"
          required
          placeholder="Destination Solana address (your wallet / exchange deposit)"
          className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 font-operational text-[12px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
        <div className="flex items-center gap-2">
          <input
            name="amount_usdc"
            type="number"
            min="0"
            step="0.000001"
            placeholder="Amount (blank = full balance)"
            className="flex-1 rounded-lg border border-border bg-background px-3.5 py-2.5 text-[12px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
          />
          <button
            type="submit"
            disabled={pending}
            className="shrink-0 rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {pending ? "Sending…" : "Withdraw"}
          </button>
        </div>
        {state?.ok && (
          <p className="text-[12px] text-success">
            {state.message}{" "}
            {state.explorer && (
              <a href={state.explorer} target="_blank" rel="noreferrer" className="underline">
                view tx ↗
              </a>
            )}
          </p>
        )}
        {state && !state.ok && (
          <p className="text-[12px] text-failure">{state.message}</p>
        )}
      </form>
    </div>
  );
}
