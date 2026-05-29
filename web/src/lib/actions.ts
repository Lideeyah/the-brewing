"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { ApiError, apiPost } from "@/lib/api";
import type { ObjectiveDetail } from "@/lib/types";

/** Coordinate: capture raw intent and draft an objective, then open it. */
export async function createObjective(formData: FormData) {
  const intent = (formData.get("intent") as string | null)?.trim();
  const title = (formData.get("title") as string | null)?.trim() || undefined;
  if (!intent) return;

  const objective = await apiPost<ObjectiveDetail>("/objectives", {
    intent,
    title,
  });
  revalidatePath("/objectives");
  revalidatePath("/dashboard");
  redirect(`/objectives/${objective.id}`);
}

/** Governance: run the Coordination Copilot to structure a drafted objective. */
export async function structureObjective(objectiveId: string) {
  await apiPost<ObjectiveDetail>(`/objectives/${objectiveId}/structure`);
  revalidatePath(`/objectives/${objectiveId}`);
  revalidatePath("/dashboard");
}

/** Shape returned to the lock-escrow client UI. */
export type LockEscrowResult =
  | { ok: true }
  | {
      ok: false;
      error?: string;
      message?: string;
      required_usdc?: string;
      balance_usdc?: string;
      treasury_address?: string;
    };

/**
 * Escrow: lock the recommended USDC budget from the workspace treasury into the
 * objective's escrow. Surfaces the API's structured 409 (e.g. insufficient
 * treasury balance) so the UI can guide the user to fund via the faucet.
 */
export async function lockEscrow(objectiveId: string): Promise<LockEscrowResult> {
  try {
    await apiPost<ObjectiveDetail>(`/objectives/${objectiveId}/escrow/lock`);
    revalidatePath(`/objectives/${objectiveId}`);
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) {
      const body = err.body as
        | {
            detail?:
              | string
              | {
                  error?: string;
                  message?: string;
                  required_usdc?: string;
                  balance_usdc?: string;
                  treasury_address?: string;
                };
          }
        | undefined;
      const detail = body?.detail;
      if (detail && typeof detail === "object") {
        return { ok: false, ...detail };
      }
      return {
        ok: false,
        message: typeof detail === "string" ? detail : "Failed to lock escrow.",
      };
    }
    return { ok: false, message: "Failed to lock escrow." };
  }
}
