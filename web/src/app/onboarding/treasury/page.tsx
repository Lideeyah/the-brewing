import { redirect } from "next/navigation";
import { ArrowUpRight, ShieldCheck, Wallet, Coins } from "lucide-react";

import { OnboardingStepper } from "@/components/onboarding/stepper";
import { ActivateForm } from "@/components/onboarding/activate-form";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import { getWorkspaceState } from "@/lib/onboarding";
import type { Overview } from "@/lib/types";

function prettyNetwork(value?: string | null): string {
  if (value === "SOL-DEVNET") return "Solana Devnet";
  if (value === "SOL") return "Solana";
  return value ?? "Solana Devnet";
}

export default async function OnboardingTreasuryPage() {
  const ws = await getWorkspaceState();
  if (ws?.onboarding_completed) redirect("/dashboard");

  let balance = "0";
  try {
    const overview = await apiGet<Overview>("/workspaces/current/overview");
    balance = overview.treasury_balance_usdc ?? "0";
  } catch {
    // best-effort; default to 0
  }

  const address = ws?.treasury_address ?? null;
  const network = prettyNetwork(ws?.treasury_blockchain);

  return (
    <>
      <OnboardingStepper current={3} />
      <div className="rounded-[16px] border border-border bg-surface p-6">
        <h1 className="text-[18px] font-semibold tracking-tight text-foreground">
          Your settlement treasury
        </h1>
        <p className="mt-1.5 text-[13px] leading-relaxed text-secondary">
          An isolated Circle-powered USDC wallet, provisioned for this workspace.
          You never hold keys — Brewing manages settlement underneath.
        </p>

        {/* Provisioned wallet */}
        <div className="mt-5 flex items-center gap-3 rounded-xl border border-border bg-background p-3.5">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-border-strong bg-elevated text-accent">
            <Wallet size={15} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[12.5px] font-semibold text-foreground">
              Circle wallet · {network}
            </div>
            <div className="mt-0.5 break-all font-operational text-[11px] text-secondary">
              {address ?? "Provisioning…"}
            </div>
          </div>
          {address ? (
            <StatusPill tone="success">provisioned</StatusPill>
          ) : (
            <StatusPill tone="pending">pending</StatusPill>
          )}
        </div>

        {/* Balance */}
        <div className="mt-3 rounded-xl border border-border bg-background p-5 text-center">
          <div className="font-operational text-[32px] leading-none text-foreground">
            {balance}
          </div>
          <div className="mt-1.5 font-operational text-[10px] uppercase tracking-wider text-muted">
            USDC · available balance
          </div>
        </div>

        {/* Funding paths */}
        <p className="mt-5 text-[11px] font-semibold text-secondary">
          Fund your treasury
        </p>
        <div className="mt-2 space-y-2.5">
          <div className="flex items-start gap-3 rounded-xl border border-border bg-background p-3.5">
            <div className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-border-strong bg-elevated text-accent">
              <ShieldCheck size={14} />
            </div>
            <div>
              <div className="flex items-center gap-2 text-[12.5px] font-semibold text-foreground">
                Transfer USDC from a wallet
                <span className="rounded bg-accent/15 px-1.5 py-0.5 font-operational text-[9px] uppercase tracking-wide text-accent">
                  recommended
                </span>
              </div>
              <p className="mt-1 text-[11.5px] leading-relaxed text-muted">
                Send devnet USDC from Phantom / Backpack and sign one funding
                transaction. Funds land in your Brewing treasury.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-xl border border-border bg-background p-3.5">
            <div className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-border-strong bg-elevated text-accent">
              <Coins size={14} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[12.5px] font-semibold text-foreground">
                Circle devnet faucet
                <span className="rounded bg-pending/15 px-1.5 py-0.5 font-operational text-[9px] uppercase tracking-wide text-pending">
                  testing
                </span>
              </div>
              <p className="mt-1 text-[11.5px] leading-relaxed text-muted">
                Paste your address into{" "}
                <a
                  href="https://faucet.circle.com"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-0.5 text-accent hover:underline"
                >
                  faucet.circle.com
                  <ArrowUpRight size={11} />
                </a>{" "}
                → Solana Devnet. Balance updates live.
              </p>
            </div>
          </div>
        </div>

        <div className="mt-5">
          <ActivateForm />
        </div>
        <p className="mt-2.5 text-center text-[11px] text-muted">
          You can fund later — activation just confirms your treasury is ready.
        </p>
      </div>
    </>
  );
}
