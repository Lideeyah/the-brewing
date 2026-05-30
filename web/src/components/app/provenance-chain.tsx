import {
  ExternalLink,
  Fingerprint,
  Landmark,
  Lock,
  Coins,
} from "lucide-react";

import { StatusPill } from "@/components/ui/status-pill";
import type {
  Escrow,
  Settlement,
  ValidationRecord,
} from "@/lib/types";

type Tone = "success" | "pending" | "failure" | "neutral" | "active";

/**
 * On-chain traceability — the custody chain a single unit of capital travels:
 * Treasury → Escrow lock → Independent validation → Settlement. Each hop that
 * has a verifiable artifact (a tx hash, an evidence hash, an explorer link)
 * surfaces it inline so the whole flow is auditable from one place rather than
 * scattered across panels. Hops with no on-chain artifact yet are still shown
 * so the gap in the chain is visible rather than hidden.
 */
export function ProvenanceChain({
  treasuryAddress,
  escrow,
  validation,
  settlement,
}: {
  treasuryAddress?: string | null;
  escrow?: Escrow | null;
  validation?: ValidationRecord | null;
  settlement?: Settlement | null;
}) {
  const nodes: ProvenanceNode[] = [];

  // 1. Treasury — capital origin.
  nodes.push({
    icon: <Landmark size={13} />,
    title: "Treasury",
    caption: "Capital origin",
    tone: treasuryAddress ? "active" : "neutral",
    pill: treasuryAddress
      ? { tone: "active", label: "source" }
      : { tone: "neutral", label: "unfunded" },
    rows: treasuryAddress
      ? [{ label: "Treasury account", mono: treasuryAddress }]
      : [],
  });

  // 2. Escrow — capital locked under custody.
  if (escrow) {
    nodes.push({
      icon: <Lock size={13} />,
      title: "Escrow lock",
      caption:
        escrow.custody_model === "non_custodial"
          ? "Non-custodial hold"
          : "Custodial hold",
      tone: "success",
      pill: { tone: "success", label: escrow.status },
      rows: [
        { label: "Locked", mono: `${escrow.amount_usdc} USDC` },
        ...(escrow.address
          ? [
              {
                label: "Escrow account",
                mono: escrow.address,
                href: escrow.explorer_url ?? undefined,
              },
            ]
          : []),
        ...(escrow.lock_tx_url || escrow.lock_tx_hash
          ? [
              {
                label: "Lock proof",
                mono: escrow.lock_tx_hash ?? "View transaction",
                href: escrow.lock_tx_url ?? undefined,
              },
            ]
          : []),
      ],
    });
  } else {
    nodes.push({
      icon: <Lock size={13} />,
      title: "Escrow lock",
      caption: "Not yet locked",
      tone: "neutral",
      pill: { tone: "neutral", label: "pending" },
      rows: [],
    });
  }

  // 3. Independent validation — evidence-bound integrity proof.
  if (validation) {
    nodes.push({
      icon: <Fingerprint size={13} />,
      title: "Validation",
      caption: validation.independent_of_executor
        ? "Independent of executor"
        : "Evidence-bound",
      tone: "active",
      pill:
        validation.outcome != null
          ? {
              tone: validation.upheld ? "success" : "failure",
              label: validation.upheld ? "upheld" : "overturned",
            }
          : { tone: "active", label: "recorded" },
      rows: [
        {
          label: "Evidence hash",
          mono: validation.evidence_hash,
        },
        {
          label: "Confidence",
          mono: `${Math.round(validation.confidence * 100)}%`,
        },
      ],
    });
  }

  // 4. Settlement — final disbursement.
  if (settlement) {
    const settled = settlement.status === "settled";
    nodes.push({
      icon: <Coins size={13} />,
      title: "Settlement",
      caption: settled ? "Released to counterparty" : "Returned to treasury",
      tone: settled ? "success" : "failure",
      pill: {
        tone: settled ? "success" : "failure",
        label: settlement.status,
      },
      rows: [
        { label: "Amount", mono: `${settlement.amount_usdc} USDC` },
        { label: "Governed fee", mono: `${settlement.fee_usdc} USDC` },
        ...(settlement.payout_address
          ? [
              {
                label: "Payout account",
                mono: settlement.payout_address,
                href: settlement.explorer_url ?? undefined,
              },
            ]
          : []),
        ...(settlement.payout_tx_url || settlement.payout_tx_hash
          ? [
              {
                label: "Payout proof",
                mono: settlement.payout_tx_hash ?? "View transaction",
                href: settlement.payout_tx_url ?? undefined,
              },
            ]
          : []),
      ],
    });
  } else {
    nodes.push({
      icon: <Coins size={13} />,
      title: "Settlement",
      caption: "Not yet settled",
      tone: "neutral",
      pill: { tone: "neutral", label: "pending" },
      rows: [],
    });
  }

  return (
    <div className="space-y-0">
      {nodes.map((n, i) => (
        <div key={n.title} className="flex gap-3.5">
          {/* Rail */}
          <div className="flex flex-col items-center">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${dotClass(
                n.tone,
              )}`}
            >
              {n.icon}
            </span>
            {i < nodes.length - 1 && (
              <span className="my-1 w-px flex-1 bg-border" />
            )}
          </div>

          {/* Body */}
          <div className={`min-w-0 flex-1 ${i < nodes.length - 1 ? "pb-5" : ""}`}>
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-medium text-foreground">
                {n.title}
              </span>
              <StatusPill tone={n.pill.tone}>{n.pill.label}</StatusPill>
            </div>
            <p className="mt-0.5 text-[11px] text-muted">{n.caption}</p>

            {n.rows.length > 0 && (
              <div className="mt-2 space-y-2">
                {n.rows.map((r) => (
                  <div key={r.label}>
                    <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
                      {r.label}
                    </p>
                    {r.href ? (
                      <a
                        href={r.href}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-0.5 inline-flex items-center gap-1 break-all font-operational text-[12px] text-accent hover:underline"
                      >
                        {r.mono}
                        <ExternalLink size={11} className="shrink-0" />
                      </a>
                    ) : (
                      <p className="mt-0.5 break-all font-operational text-[12px] text-foreground">
                        {r.mono}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

interface ProvenanceNode {
  icon: React.ReactNode;
  title: string;
  caption: string;
  tone: Tone;
  pill: { tone: Tone; label: string };
  rows: { label: string; mono: string; href?: string }[];
}

function dotClass(tone: Tone): string {
  switch (tone) {
    case "success":
      return "border-success/40 bg-success/10 text-success";
    case "failure":
      return "border-failure/40 bg-failure/10 text-failure";
    case "active":
      return "border-accent/40 bg-accent/10 text-accent";
    case "pending":
      return "border-pending/40 bg-pending/10 text-pending";
    default:
      return "border-border bg-elevated text-muted";
  }
}
