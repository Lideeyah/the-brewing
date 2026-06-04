import Link from "next/link";
import { Landmark, Wallet, ArrowUpRight } from "lucide-react";

import { auth } from "@/auth";
import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import { apiGet } from "@/lib/api";
import type { MeWorkspace, Overview } from "@/lib/types";

function prettyNetwork(value?: string | null): string {
  if (value === "SOL-DEVNET") return "Solana Devnet";
  if (value === "SOL") return "Solana";
  return value ?? "Solana Devnet";
}

export default async function TreasuryPage() {
  const session = await auth();
  const workspace = session?.workspace;

  // Fetch both fresh from the API. The treasury address is read from the live
  // workspace record — NOT the session JWT, which is cached at sign-in and goes
  // stale the moment a wallet is provisioned after a user's first login.
  const [overviewResult, currentResult] = await Promise.allSettled([
    apiGet<Overview>("/workspaces/current/overview"),
    apiGet<MeWorkspace>("/workspaces/current"),
  ]);
  const overview =
    overviewResult.status === "fulfilled" ? overviewResult.value : null;
  const current =
    currentResult.status === "fulfilled" ? currentResult.value : null;

  const balance = overview?.treasury_balance_usdc ?? "0";
  const address =
    current?.treasury_address ?? workspace?.treasury_address ?? null;
  const network = prettyNetwork(
    current?.treasury_blockchain ?? workspace?.treasury_blockchain,
  );
  const metrics = overview?.metrics ?? [];

  return (
    <>
      <Topbar title="Treasury" breadcrumb="brewing / treasury" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
              Workspace Treasury
            </h2>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-secondary">
              The funding source for every objective. Escrow is locked from this
              treasury at coordination time and released to counterparties on
              settlement. The balance is read live from the settlement provider —
              it is never stored as truth.
            </p>
          </div>

          {/* Balance + account */}
          <Panel>
            <PanelHeader
              title="Treasury account"
              meta="live · settlement provider"
              action={<StatusPill tone="active">{network}</StatusPill>}
            />
            <PanelBody className="space-y-4">
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                    Available balance
                  </p>
                  <p className="mt-1 font-operational text-[32px] leading-none text-foreground">
                    {balance}{" "}
                    <span className="text-[16px] text-muted">USDC</span>
                  </p>
                </div>
                <Wallet size={22} className="text-accent" />
              </div>

              {address ? (
                <div className="border-t border-border pt-3">
                  <p className="font-operational text-[11px] uppercase tracking-wider text-muted">
                    Treasury address
                  </p>
                  <p className="mt-0.5 break-all font-operational text-[12px] text-foreground">
                    {address}
                  </p>
                </div>
              ) : (
                <div className="border-t border-border pt-3">
                  <p className="text-[12px] text-muted">
                    No treasury wallet provisioned yet. It is created
                    automatically with your workspace on first settlement setup.
                  </p>
                </div>
              )}

              {balance === "0" && (
                <div className="rounded-lg border border-border bg-background p-3.5">
                  <p className="text-[12px] leading-relaxed text-secondary">
                    Treasury is empty. On Solana devnet you can fund this account
                    from the{" "}
                    <a
                      href="https://faucet.circle.com"
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-0.5 text-accent hover:underline"
                    >
                      Circle faucet
                      <ArrowUpRight size={11} />
                    </a>{" "}
                    before locking escrow on an objective.
                  </p>
                </div>
              )}
            </PanelBody>
          </Panel>

          {/* Settlement economics — reuse the workspace overview metrics */}
          {metrics.length > 0 && (
            <Panel>
              <PanelHeader
                title="Settlement economics"
                meta="realized across objectives"
              />
              <PanelBody>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {metrics.map((m) => (
                    <div
                      key={m.label}
                      className="rounded-lg border border-border bg-background p-3"
                    >
                      <div className="font-operational text-[18px] leading-none text-foreground">
                        {m.value}
                      </div>
                      <div className="mt-1.5 text-[11px] font-medium text-secondary">
                        {m.label}
                      </div>
                      {m.hint && (
                        <div className="mt-0.5 text-[10px] text-muted">
                          {m.hint}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </PanelBody>
            </Panel>
          )}

          <Panel>
            <PanelBody className="flex items-center gap-3">
              <Landmark size={18} className="shrink-0 text-muted" />
              <p className="text-[12px] leading-relaxed text-muted">
                Capital flow is auditable end to end: treasury → escrow →
                validation → settlement. Per-objective movement, with transaction
                proofs, is shown on each{" "}
                <Link href="/objectives" className="text-accent hover:underline">
                  objective
                </Link>
                .
              </p>
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}
