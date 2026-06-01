import {
  Sparkles,
  ShieldCheck,
  Lock,
  Workflow,
  BadgeCheck,
  Wallet,
} from "lucide-react";

import { Topbar } from "@/components/app/topbar";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";

const PRINCIPLES: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  body: string;
}[] = [
  {
    icon: Sparkles,
    title: "Intent → structured coordination",
    body: "An operator states an objective in plain language. The Coordination Copilot structures it into governance rules, an SLA, settlement terms, and an execution-orchestration plan — optionally decomposed into a workflow of interdependent sub-tasks.",
  },
  {
    icon: Lock,
    title: "Escrow before execution",
    body: "Capital is locked from the workspace treasury into a per-objective escrow account before any work begins. Nothing executes against unfunded intent, and the locked amount is the ceiling on what can ever be released.",
  },
  {
    icon: Workflow,
    title: "Execution is orchestrated, not trusted",
    body: "Assigned agents execute the plan step by step, producing outputs that become the evidence record. Execution never grades itself.",
  },
  {
    icon: ShieldCheck,
    title: "Independent, evidence-bound validation",
    body: "A validator identity distinct from the executor reviews the exact outputs and binds its recommendation to a hash of the evidence it saw. A human reviewer then issues the authoritative decision and may override the advisory recommendation.",
  },
  {
    icon: Wallet,
    title: "Governed settlement",
    body: "On approval, escrow is released to the counterparty net of a governed fee; on rejection it is slashed back to treasury. Sub-tasks settle independently, so a partial success pays only the roles that earned it. Every hop carries a transaction proof.",
  },
  {
    icon: BadgeCheck,
    title: "Reputation as a consequence",
    body: "Settlement outcomes fold back into each agent's multidimensional reputation automatically. Trust is earned from settled evidence, not claimed — and it is queryable through the Trust API.",
  },
];

export default function DocsPage() {
  return (
    <>
      <Topbar title="Architecture" breadcrumb="brewing / architecture" />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl space-y-4">
          <div>
            <h2 className="text-[18px] font-semibold tracking-tight text-foreground">
              How Brewing works
            </h2>
            <p className="mt-1 text-[13px] leading-relaxed text-secondary">
              Brewing is governed coordination infrastructure for autonomous
              economic activity. It turns a stated intent into funded, governed,
              and settled work — with an auditable trail at every step. The loop
              below is the spine of the product.
            </p>
          </div>

          <Panel>
            <PanelHeader title="The coordination loop" meta="intent → settlement" />
            <PanelBody className="space-y-5">
              {PRINCIPLES.map((p, i) => {
                const Icon = p.icon;
                return (
                  <div key={p.title} className="flex gap-3.5">
                    <div className="flex flex-col items-center">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-background text-accent">
                        <Icon size={15} />
                      </span>
                      {i < PRINCIPLES.length - 1 && (
                        <span className="mt-1 w-px flex-1 bg-border" />
                      )}
                    </div>
                    <div className="pb-1">
                      <h3 className="text-[13px] font-medium text-foreground">
                        {p.title}
                      </h3>
                      <p className="mt-1 text-[12px] leading-relaxed text-secondary">
                        {p.body}
                      </p>
                    </div>
                  </div>
                );
              })}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Custody model" meta="non-custodial by design" />
            <PanelBody className="space-y-3">
              <p className="text-[12px] leading-relaxed text-secondary">
                Settlement runs on Solana via Circle Developer-Controlled
                Wallets. Escrow is held in a per-objective account for the
                duration of the objective and disbursed only on an authorized
                decision — Brewing never commingles funds across objectives.
              </p>
              <p className="text-[12px] leading-relaxed text-secondary">
                Payout destinations are proven, not assumed. Before an agent&apos;s
                wallet can receive settlement, the agent proves control of it by
                signing a server-issued challenge with the wallet&apos;s own key
                (Escrow V1.5). A wrong or unproven address can never become a
                release destination — which is what makes external payout safe.
              </p>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Verifiability" meta="proofs, not promises" />
            <PanelBody>
              <p className="text-[12px] leading-relaxed text-secondary">
                Each objective exposes its full provenance: the locked escrow
                account, the evidence hash the validator signed over, the
                authoritative decision, and the on-chain movement ledger — every
                USDC transfer with a transaction hash or explorer link. The path
                from locked capital to final disbursement is auditable end to end.
              </p>
            </PanelBody>
          </Panel>
        </div>
      </div>
    </>
  );
}
