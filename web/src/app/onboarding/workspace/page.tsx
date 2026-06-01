import { redirect } from "next/navigation";

import { OnboardingStepper } from "@/components/onboarding/stepper";
import { WorkspaceForm } from "@/components/onboarding/workspace-form";
import { getWorkspaceState } from "@/lib/onboarding";

export default async function OnboardingWorkspacePage() {
  const ws = await getWorkspaceState();
  // Already onboarded operators don't re-run provisioning.
  if (ws?.onboarding_completed) redirect("/dashboard");

  // Prefill, but drop the auto-derived "X's Workspace" placeholder so the
  // operator names it deliberately.
  const autoNamed = /'s Workspace$/.test(ws?.name ?? "");
  const defaultName = autoNamed ? "" : (ws?.name ?? "");

  return (
    <>
      <OnboardingStepper current={2} />
      <div className="rounded-[16px] border border-border bg-surface p-6">
        <h1 className="text-[18px] font-semibold tracking-tight text-foreground">
          Set up your operational workspace
        </h1>
        <p className="mt-1.5 text-[13px] leading-relaxed text-secondary">
          This becomes your coordination environment — the container for
          objectives, governance, and treasury.
        </p>
        <div className="mt-5">
          <WorkspaceForm
            defaultName={defaultName}
            defaultOrg={ws?.org_name ?? ""}
            defaultType={ws?.operational_type ?? ""}
            requireAuditor={ws?.governance_require_auditor ?? true}
            humanAuthoritative={ws?.governance_human_authoritative ?? true}
          />
        </div>
      </div>
    </>
  );
}
