import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { Logo } from "@/components/brand/logo";

/**
 * Onboarding shell — the Sign Up journey's provisioning sequence. Auth is
 * required; the per-step pages enforce the onboarding gate themselves (Workspace
 * and Treasury bounce already-onboarded operators to Mission Control, while
 * Orientation stays reachable as a one-time intro).
 */
export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.brewingToken) redirect("/signin");

  return (
    <div className="min-h-screen bg-background px-4 py-12">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-7 flex flex-col items-center text-center">
          <Logo size={26} />
        </div>
        {children}
      </div>
    </div>
  );
}
