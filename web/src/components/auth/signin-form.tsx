"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { ArrowRight, Loader2 } from "lucide-react";

export function SignInForm() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [pending, setPending] = useState<"google" | "email" | null>(null);

  const google = async () => {
    setPending("google");
    await signIn("google", { callbackUrl: "/dashboard" });
  };

  const emailSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.includes("@")) return;
    setPending("email");
    await signIn("dev-email", { email, name, callbackUrl: "/dashboard" });
  };

  return (
    <div className="space-y-4">
      <button
        onClick={google}
        disabled={pending !== null}
        className="flex w-full items-center justify-center gap-2 rounded-lg border border-border-strong bg-elevated px-4 py-2.5 text-[13px] font-medium text-foreground transition-colors hover:bg-elevated/70 disabled:opacity-60"
      >
        {pending === "google" ? (
          <Loader2 size={15} className="animate-spin" />
        ) : (
          <GoogleGlyph />
        )}
        Continue with Google
      </button>

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="font-operational text-[10px] uppercase tracking-wider text-muted">
          or
        </span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={emailSignIn} className="space-y-2.5">
        <input
          type="email"
          required
          placeholder="you@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
        <input
          type="text"
          placeholder="Name (optional)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-[13px] text-foreground placeholder:text-muted focus:border-border-strong focus:outline-none"
        />
        <button
          type="submit"
          disabled={pending !== null || !email.includes("@")}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-2.5 text-[13px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {pending === "email" ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <>
              Continue with email <ArrowRight size={15} />
            </>
          )}
        </button>
      </form>
    </div>
  );
}

function GoogleGlyph() {
  return (
    <svg width="15" height="15" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72A5.41 5.41 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.05l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.59C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}
