import "server-only";

import { apiGet } from "@/lib/api";
import type { MeWorkspace } from "@/lib/types";

/**
 * Fresh workspace state, straight from the API — the source of truth for
 * first-run routing. We deliberately do NOT trust the NextAuth JWT snapshot
 * here: it is captured at sign-in and goes stale the moment onboarding
 * completes, which would otherwise bounce a just-onboarded user in a loop.
 */
export async function getWorkspaceState(): Promise<MeWorkspace | null> {
  try {
    return await apiGet<MeWorkspace>("/workspaces/current");
  } catch {
    return null;
  }
}
