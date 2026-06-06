import Link from "next/link";
import { Plus } from "lucide-react";

import { auth } from "@/auth";
import { UserMenu } from "@/components/app/user-menu";
import { FeedbackButton } from "@/components/app/feedback-button";

export async function Topbar({
  title,
  breadcrumb,
}: {
  title: string;
  breadcrumb?: string;
}) {
  const session = await auth();
  const network = session?.workspace?.treasury_blockchain ?? "Solana Devnet";

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

      <div className="flex items-center gap-3">
        <span
          className="hidden items-center gap-1.5 rounded-full border border-border px-2 py-0.5 sm:inline-flex"
          title={`Settlement network: ${prettyNetwork(network)}`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
            {prettyNetwork(network)}
          </span>
        </span>

        <Link
          href="/coordinate"
          className="flex items-center gap-2 rounded-lg bg-foreground px-3 py-1.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90"
        >
          <Plus size={15} />
          New Objective
        </Link>

        <FeedbackButton />

        <UserMenu name={session?.user?.name} email={session?.user?.email} />
      </div>
    </header>
  );
}

function prettyNetwork(value: string): string {
  if (value === "SOL-DEVNET") return "Solana Devnet";
  if (value === "SOL") return "Solana";
  return value;
}
