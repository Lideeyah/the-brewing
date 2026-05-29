"use client";

import { useState } from "react";
import { signOut } from "next-auth/react";
import { ChevronDown, LogOut } from "lucide-react";

export function UserMenu({
  name,
  email,
}: {
  name?: string | null;
  email?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const initial = (name || email || "B").trim().charAt(0).toUpperCase();

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[13px] text-secondary hover:text-foreground"
      >
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent/20 font-operational text-[10px] text-accent">
          {initial}
        </span>
        <ChevronDown size={14} className="text-muted" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-1.5 w-56 rounded-lg border border-border bg-elevated p-1 shadow-xl">
            <div className="px-3 py-2">
              <div className="truncate text-[13px] text-foreground">
                {name || "Operator"}
              </div>
              <div className="truncate font-operational text-[11px] text-muted">
                {email}
              </div>
            </div>
            <div className="my-1 h-px bg-border" />
            <button
              onClick={() => signOut({ callbackUrl: "/signin" })}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-[13px] text-secondary hover:bg-surface hover:text-foreground"
            >
              <LogOut size={14} />
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
