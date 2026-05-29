"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ClipboardCheck,
  Gauge,
  Landmark,
  ScrollText,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { cn } from "@/lib/cn";

const nav = [
  { href: "/dashboard", label: "Mission Control", icon: Gauge },
  { href: "/coordinate", label: "Coordinate", icon: Sparkles },
  { href: "/objectives", label: "Objectives", icon: Target },
  { href: "/governance", label: "Governance", icon: ShieldCheck },
  { href: "/auditor", label: "Auditor", icon: ClipboardCheck },
  { href: "/treasury", label: "Treasury", icon: Landmark },
  { href: "/activity", label: "Observability", icon: Activity },
];

const secondary = [
  { href: "/docs", label: "Architecture", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex h-14 items-center border-b border-border px-5">
        <Link href="/dashboard">
          <Logo size={24} />
        </Link>
      </div>

      <nav className="flex-1 space-y-0.5 px-3 py-4">
        <p className="px-2 pb-2 font-operational text-[10px] uppercase tracking-wider text-muted">
          Operations
        </p>
        {nav.map((item) => (
          <NavLink key={item.href} {...item} active={isActive(item.href)} />
        ))}
      </nav>

      <div className="space-y-0.5 border-t border-border px-3 py-4">
        {secondary.map((item) => (
          <NavLink key={item.href} {...item} active={isActive(item.href)} />
        ))}
      </div>
    </aside>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] transition-colors",
        active
          ? "bg-elevated text-foreground"
          : "text-secondary hover:bg-elevated/60 hover:text-foreground",
      )}
    >
      <Icon
        size={16}
        className={cn(
          "shrink-0 transition-colors",
          active ? "text-accent" : "text-muted group-hover:text-secondary",
        )}
      />
      {label}
    </Link>
  );
}
