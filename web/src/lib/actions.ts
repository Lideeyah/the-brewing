"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiPost } from "@/lib/api";
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
