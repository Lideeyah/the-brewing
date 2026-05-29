import { ShieldCheck } from "lucide-react";

import type { CustodyModel } from "@/lib/types";

/**
 * Non-custodial messaging shown anywhere escrow or settlement is referenced.
 *
 * The copy is custody-aware so it stays honest: when an escrow is genuinely
 * non-custodial (keys held by the tenant's agentic wallet) it states the full
 * guarantee; on the current custodial rail it states Brewing's stance and that
 * the agentic-wallet-controlled model is the target.
 */
export function NonCustodialNote({
  custodyModel = "custodial",
  controllerWallet,
  className = "",
}: {
  custodyModel?: CustodyModel;
  controllerWallet?: string | null;
  className?: string;
}) {
  const nonCustodial = custodyModel === "non_custodial";
  return (
    <div
      className={`flex items-start gap-2 rounded-lg border border-border bg-elevated/50 p-2.5 ${className}`}
    >
      <ShieldCheck size={14} className="mt-0.5 shrink-0 text-accent" />
      <div className="space-y-1">
        <p className="font-operational text-[11px] uppercase tracking-wider text-accent">
          {nonCustodial ? "Non-custodial escrow" : "Non-custodial by design"}
        </p>
        {nonCustodial ? (
          <p className="text-[11px] leading-relaxed text-muted">
            Brewing never holds, transmits, or custodies these funds. This is a
            tenant-scoped escrow account controlled by your agentic wallet —
            release and slash are authorized by your keys, not ours.
          </p>
        ) : (
          <p className="text-[11px] leading-relaxed text-muted">
            Brewing is custody-minimizing by design. Settlement currently runs
            through programmable wallets; tenant-scoped escrow with keys held by
            your agentic wallet — so Brewing can never move funds unilaterally —
            is the target model and is rolling out.
          </p>
        )}
        {nonCustodial && controllerWallet && (
          <p className="break-all font-operational text-[11px] text-muted">
            Controller wallet: {controllerWallet}
          </p>
        )}
      </div>
    </div>
  );
}
