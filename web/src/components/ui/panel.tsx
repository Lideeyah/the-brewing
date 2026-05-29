import { cn } from "@/lib/cn";

export function Panel({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        "rounded-[12px] border border-border bg-surface",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function PanelHeader({
  title,
  meta,
  action,
}: {
  title: string;
  meta?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
      <div className="flex items-baseline gap-3">
        <h2 className="text-[13px] font-medium tracking-tight text-foreground">
          {title}
        </h2>
        {meta && (
          <span className="font-operational text-[11px] text-muted">{meta}</span>
        )}
      </div>
      {action}
    </div>
  );
}

export function PanelBody({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={cn("p-5", className)}>{children}</div>;
}
