"use client";

import { signOut } from "next-auth/react";
import { LogOut } from "lucide-react";

export function SignOutButton() {
  return (
    <button
      onClick={() => signOut({ callbackUrl: "/signin" })}
      className="flex items-center gap-2 rounded-lg border border-border bg-elevated px-3.5 py-2 text-[13px] font-medium text-foreground transition-colors hover:bg-elevated/70"
    >
      <LogOut size={15} />
      Sign out
    </button>
  );
}
