import { redirect } from "next/navigation";

// Bare /onboarding has no UI of its own — the journey always begins at
// workspace initialization. The (app) gate and per-step guards handle the
// completed-onboarding case.
export default function OnboardingIndex() {
  redirect("/onboarding/workspace");
}
