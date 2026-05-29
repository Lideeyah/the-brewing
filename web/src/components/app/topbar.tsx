import { ChevronDown, Plus } from "lucide-react";

import { StatusPill } from "@/components/ui/status-pill";

export function Topbar({
  title,
  breadcrumb,
}: {
  title: string;
  breadcrumb?: string;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur">
      <div className="flex items-center gap-3">
        <h1 className="text-[15px] font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        {breadcrumb && (
          <span className="font-operational text-[11px] text-muted">
            {breadcrumb}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        <StatusPill tone="active">Solana Devnet</StatusPill>

        <button className="flex items-center gap-2 rounded-lg bg-foreground px-3 py-1.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90">
          <Plus size={15} />
          New Objective
        </button>

        <button className="flex items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[13px] text-secondary hover:text-foreground">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent/20 font-operational text-[10px] text-accent">
            B
          </span>
          <ChevronDown size={14} className="text-muted" />
        </button>
      </div>
    </header>
  );
}
