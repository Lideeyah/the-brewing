import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { Logo } from "@/components/brand/logo";
import { SignInForm } from "@/components/auth/signin-form";

export default async function SignInPage() {
  const session = await auth();
  if (session?.brewingToken) redirect("/dashboard");

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo size={30} />
          <h1 className="mt-6 text-[17px] font-semibold tracking-tight text-foreground">
            Sign in to Brewing
          </h1>
          <p className="mt-1.5 text-[13px] leading-relaxed text-secondary">
            Governed coordination and settlement
            <br />
            infrastructure for autonomous systems.
          </p>
        </div>

        <div className="rounded-[16px] border border-border bg-surface p-6">
          <SignInForm />
        </div>

        <p className="mt-6 text-center font-operational text-[10px] uppercase tracking-wider text-muted">
          Intent → Governance → Escrow → Execution → Settlement
        </p>
      </div>
    </div>
  );
}
