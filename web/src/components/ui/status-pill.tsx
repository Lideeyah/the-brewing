import { cn } from "@/lib/cn";

type Tone = "success" | "pending" | "failure" | "neutral" | "active";

const toneStyles: Record<Tone, string> = {
  success: "text-success border-success/30 bg-success/10",
  pending: "text-pending border-pending/30 bg-pending/10",
  failure: "text-failure border-failure/30 bg-failure/10",
  active: "text-accent border-accent/30 bg-accent/10",
  neutral: "text-secondary border-border-strong bg-elevated",
};

export function StatusPill({
  tone = "neutral",
  children,
  dot = true,
}: {
  tone?: Tone;
  children: React.ReactNode;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5",
        "font-operational text-[10px] uppercase tracking-wider",
        toneStyles[tone],
      )}
    >
      {dot && (
        <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      )}
      {children}
    </span>
  );
}
