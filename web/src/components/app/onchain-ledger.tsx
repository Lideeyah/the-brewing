import {
  ArrowDownToLine,
  ArrowUpFromLine,
  CircleDot,
  Coins,
  ExternalLink,
  Landmark,
  Lock,
  Undo2,
} from "lucide-react";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import type { OnChainLedger as OnChainLedgerType, WalletMovement } from "@/lib/types";

type Tone = "success" | "pending" | "failure" | "neutral" | "active";

const KIND_META: Record<
  string,
  { icon: React.ReactNode; tone: Tone; ring: string }
> = {
  lock: {
    icon: <Lock size={13} />,
    tone: "active",
    ring: "border-accent/40 bg-accent/10 text-accent",
  },
  release: {
    icon: <ArrowUpFromLine size={13} />,
    tone: "success",
    ring: "border-success/40 bg-success/10 text-success",
  },
  slash: {
    icon: <Undo2 size={13} />,
    tone: "failure",
    ring: "border-failure/40 bg-failure/10 text-failure",
  },
};

function AddressLink({
  label,
  address,
  href,
}: {
  label: string;
  address?: string | null;
  href?: string | null;
}) {
  if (!address) return null;
  return (
    <div className="min-w-0">
      <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
        {label}
      </p>
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noreferrer"
          className="mt-0.5 inline-flex items-center gap-1 break-all font-operational text-[11px] text-accent hover:underline"
        >
          {address}
          <ExternalLink size={10} className="shrink-0" />
        </a>
      ) : (
        <p className="mt-0.5 break-all font-operational text-[11px] text-foreground">
          {address}
        </p>
      )}
    </div>
  );
}

/**
 * On-chain movement ledger — every real USDC transfer an objective triggers,
 * in one place. The escrow lock funds capital into custody; each release pays a
 * verified agent (objective-level or per-sub-task); each slash returns capital
 * to the treasury. Each hop exposes its amount, named counterparties, and — once
 * the provider confirms a signature — an explorer-verifiable transaction proof.
 */
export function OnChainLedger({ ledger }: { ledger: OnChainLedgerType }) {
  if (!ledger || ledger.movements.length === 0) return null;

  return (
    <Panel className="mt-4">
      <PanelHeader
        title="On-chain movement ledger"
        meta={
          ledger.blockchain
            ? `${ledger.blockchain} · ${ledger.confirmed_count}/${ledger.movements.length} confirmed`
            : `${ledger.confirmed_count}/${ledger.movements.length} confirmed`
        }
      />
      <PanelBody className="space-y-4">
        <p className="flex items-start gap-1.5 text-[12px] leading-relaxed text-muted">
          <Coins size={13} className="mt-0.5 shrink-0 text-accent" />
          Every movement of capital this objective triggered — the escrow lock and
          each settlement release or slash — with named counterparties and
          explorer-verifiable proof for each confirmed transaction.
        </p>

        {/* Totals */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Locked" value={ledger.total_locked_usdc} icon={<Lock size={12} />} />
          <Stat
            label="Released"
            value={ledger.total_released_usdc}
            icon={<ArrowUpFromLine size={12} />}
            tone="success"
          />
          <Stat
            label="Slashed"
            value={ledger.total_slashed_usdc}
            icon={<Undo2 size={12} />}
            tone="failure"
          />
          <Stat
            label="Governed fees"
            value={ledger.total_fees_usdc}
            icon={<Landmark size={12} />}
          />
        </div>

        {/* Movement rail */}
        <div className="space-y-0">
          {ledger.movements.map((m, i) => (
            <MovementRow
              key={i}
              m={m}
              last={i === ledger.movements.length - 1}
            />
          ))}
        </div>
      </PanelBody>
    </Panel>
  );
}

function Stat({
  label,
  value,
  icon,
  tone = "neutral",
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  tone?: Tone;
}) {
  const valueCls =
    tone === "success"
      ? "text-success"
      : tone === "failure"
        ? "text-failure"
        : "text-foreground";
  return (
    <div className="rounded-lg border border-border bg-background p-2.5">
      <p className="flex items-center gap-1 font-operational text-[10px] uppercase tracking-wider text-muted">
        {icon}
        {label}
      </p>
      <p className={`mt-1 font-operational text-[14px] ${valueCls}`}>
        {value}
        <span className="ml-1 text-[10px] text-muted">USDC</span>
      </p>
    </div>
  );
}

function MovementRow({ m, last }: { m: WalletMovement; last: boolean }) {
  const meta = KIND_META[m.kind] ?? {
    icon: <CircleDot size={13} />,
    tone: "neutral" as Tone,
    ring: "border-border bg-elevated text-muted",
  };
  return (
    <div className="flex gap-3.5">
      <div className="flex flex-col items-center">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${meta.ring}`}
        >
          {meta.icon}
        </span>
        {!last && <span className="my-1 w-px flex-1 bg-border" />}
      </div>

      <div className={`min-w-0 flex-1 ${last ? "" : "pb-5"}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium text-foreground">
            {m.label}
          </span>
          <span className="font-operational text-[13px] text-foreground">
            {m.direction === "inbound" ? (
              <ArrowDownToLine size={11} className="mr-0.5 inline text-muted" />
            ) : (
              <ArrowUpFromLine size={11} className="mr-0.5 inline text-muted" />
            )}
            {m.amount_usdc} USDC
          </span>
          <StatusPill
            tone={m.confirmed ? meta.tone : "neutral"}
            dot={false}
          >
            {m.confirmed ? "confirmed" : "pending proof"}
          </StatusPill>
        </div>

        <p className="mt-0.5 flex flex-wrap items-center gap-1 text-[11px] text-muted">
          {m.from_label}
          <ArrowUpFromLine size={10} className="rotate-90 text-muted" />
          {m.to_label}
        </p>

        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <AddressLink
            label={m.from_label ?? "From"}
            address={m.from_address}
          />
          <AddressLink
            label={m.to_label ?? "To"}
            address={m.to_address}
            href={m.to_explorer_url}
          />
        </div>

        {(m.tx_url || m.tx_hash) && (
          <div className="mt-2">
            <p className="font-operational text-[10px] uppercase tracking-wider text-muted">
              Transaction proof
            </p>
            {m.tx_url ? (
              <a
                href={m.tx_url}
                target="_blank"
                rel="noreferrer"
                className="mt-0.5 inline-flex items-center gap-1 break-all font-operational text-[11px] text-accent hover:underline"
              >
                {m.tx_hash ?? "View transaction"}
                <ExternalLink size={10} className="shrink-0" />
              </a>
            ) : (
              <p className="mt-0.5 break-all font-operational text-[11px] text-foreground">
                {m.tx_hash}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
