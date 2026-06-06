import { redirect } from "next/navigation";

import { auth } from "@/auth";
import { Sidebar } from "@/components/app/sidebar";
import { isAdminEmail } from "@/lib/admin";
import { getWorkspaceState } from "@/lib/onboarding";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.brewingToken) redirect("/signin");

  // First-run gate: Mission Control stays closed until the operator has been
  // through Workspace + Treasury initialization. Read fresh state (not the JWT
  // snapshot) so a just-onboarded user isn't bounced back.
  const workspace = await getWorkspaceState();
  if (workspace && !workspace.onboarding_completed) {
    redirect("/onboarding/workspace");
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar isAdmin={isAdminEmail(session.user?.email)} />
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
