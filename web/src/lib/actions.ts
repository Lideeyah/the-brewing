"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { ApiError, apiGet, apiPatch, apiPost } from "@/lib/api";
import type {
  AgentDetail,
  AgentIdentity,
  FeedbackCommitment,
  MeWorkspace,
  ObjectiveDetail,
  PayoutChallenge,
  TrustScore,
} from "@/lib/types";

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

/** Result shape for lifecycle actions that surface API errors to the UI. */
export type LifecycleResult = { ok: true } | { ok: false; message: string };

function apiErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { detail?: unknown } | undefined;
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message?: unknown }).message);
    }
  }
  return "Request failed.";
}

/** Execution: orchestrate the objective's plan, advancing it to validation. */
export async function executeObjective(
  objectiveId: string,
): Promise<LifecycleResult> {
  try {
    await apiPost<ObjectiveDetail>(`/objectives/${objectiveId}/execute`);
    revalidatePath(`/objectives/${objectiveId}`);
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/**
 * Validation (AI): run the Coordination Copilot's governance evaluation. This is
 * advisory — it produces a recommendation + reasoning and does not transition
 * the objective. A human still issues the binding decision via decideAudit.
 */
export async function evaluateGovernance(
  objectiveId: string,
): Promise<LifecycleResult> {
  try {
    await apiPost<ObjectiveDetail>(`/objectives/${objectiveId}/audit/evaluate`);
    revalidatePath(`/objectives/${objectiveId}`);
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/** Validation (human): authoritative approve/reject, may override the Copilot. */
export async function decideAudit(
  objectiveId: string,
  decision: "approve" | "reject",
): Promise<LifecycleResult> {
  try {
    await apiPost<ObjectiveDetail>(`/objectives/${objectiveId}/audit/decide`, {
      decision,
    });
    revalidatePath(`/objectives/${objectiveId}`);
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/** Settlement: release escrow to the counterparty, or slash it on rejection. */
export async function settleObjective(
  objectiveId: string,
): Promise<LifecycleResult> {
  try {
    await apiPost<ObjectiveDetail>(`/objectives/${objectiveId}/settle`);
    revalidatePath(`/objectives/${objectiveId}`);
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/**
 * Registry: assign a registered agent as an objective's executor. Once assigned,
 * settlement automatically folds the outcome back into the agent's reputation.
 */
export async function assignAgent(
  objectiveId: string,
  agentId: string,
): Promise<LifecycleResult> {
  try {
    await apiPost<ObjectiveDetail>(`/objectives/${objectiveId}/assign-agent`, {
      agent_id: agentId,
    });
    revalidatePath(`/objectives/${objectiveId}`);
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/** Result shape for binding an agent to a workflow role. */
export type AssignRoleResult =
  | { ok: true }
  | { ok: false; message: string; issues?: string[] };

/**
 * Workflow: bind a registered agent to one role in an objective's workflow.
 * The API enforces the agent's pricing/availability constraints, so a
 * constraint violation comes back as a list of human-readable issues the UI
 * can surface inline rather than a generic failure.
 */
export async function assignRole(
  objectiveId: string,
  roleId: string,
  agentId: string,
): Promise<AssignRoleResult> {
  try {
    await apiPost<ObjectiveDetail>(
      `/objectives/${objectiveId}/roles/${roleId}/assign`,
      { agent_id: agentId },
    );
    revalidatePath(`/objectives/${objectiveId}`);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) {
      const detail = (err.body as { detail?: unknown } | undefined)?.detail;
      if (detail && typeof detail === "object" && "issues" in detail) {
        const issues = (detail as { issues?: unknown }).issues;
        if (Array.isArray(issues)) {
          return {
            ok: false,
            message: "That agent can't take this role.",
            issues: issues.map(String),
          };
        }
      }
    }
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/**
 * Workflow: re-weight a role's settlement allocation. The Copilot proposes the
 * initial split; this lets a user adjust it before settlement. The API refuses
 * an edit that pushes total allocations over budget.
 */
export async function updateRoleAllocation(
  objectiveId: string,
  roleId: string,
  allocationUsdc: string,
): Promise<LifecycleResult> {
  try {
    await apiPatch<ObjectiveDetail>(
      `/objectives/${objectiveId}/roles/${roleId}/allocation`,
      { allocation_usdc: allocationUsdc },
    );
    revalidatePath(`/objectives/${objectiveId}`);
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/**
 * Coordination: validate one sub-task independently. Runs the same evidence
 * engine + authorization used at the objective level, scoped to the sub-task's
 * own success criteria. The API enforces the dependency DAG (prerequisite
 * sub-tasks must have passed), so an out-of-order call comes back as an error.
 */
export async function validateSubtask(
  objectiveId: string,
  roleId: string,
): Promise<LifecycleResult> {
  try {
    await apiPost<ObjectiveDetail>(
      `/objectives/${objectiveId}/roles/${roleId}/validate`,
    );
    revalidatePath(`/objectives/${objectiveId}`);
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/**
 * Coordination: settle one sub-task independently. A passed sub-task releases
 * its allocation (net of fee) to its agent; a failed one slashes it back to
 * treasury. The parent objective stays gated until all required sub-tasks pass.
 */
export async function settleSubtask(
  objectiveId: string,
  roleId: string,
): Promise<LifecycleResult> {
  try {
    await apiPost<ObjectiveDetail>(
      `/objectives/${objectiveId}/roles/${roleId}/settle`,
    );
    revalidatePath(`/objectives/${objectiveId}`);
    revalidatePath("/dashboard");
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/** Result shape for agent self-registration. */
export type RegisterAgentResult =
  | { ok: true; agent: AgentIdentity }
  | { ok: false; message: string };

/**
 * Registry: agent self-registration. A developer lists their agent on Brewing
 * by minting an on-chain-ready identity token. Once registered it appears in the
 * Agents marketplace as discoverable and hireable.
 */
export async function registerAgent(
  formData: FormData,
): Promise<RegisterAgentResult> {
  const name = (formData.get("name") as string | null)?.trim();
  const owner = (formData.get("owner") as string | null)?.trim();
  if (!name || !owner) {
    return { ok: false, message: "Agent name and wallet address are required." };
  }

  const description =
    (formData.get("description") as string | null)?.trim() || undefined;
  const pricing = (formData.get("pricing") as string | null)?.trim() || undefined;
  const endpointUrl = (formData.get("endpoint_url") as string | null)?.trim();
  const capabilities = ((formData.get("capabilities") as string | null) ?? "")
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);

  const service_endpoints = endpointUrl
    ? [
        {
          name: "primary",
          url: endpointUrl,
          protocol: endpointUrl.startsWith("http") ? "https" : undefined,
        },
      ]
    : [];

  const pricing_model =
    (formData.get("pricing_model") as string | null)?.trim() || "fixed";
  const availability =
    (formData.get("availability") as string | null)?.trim() || "available";
  const min_objective_value_usdc =
    (formData.get("min_objective_value_usdc") as string | null)?.trim() ||
    undefined;
  const min_role_compensation_usdc =
    (formData.get("min_role_compensation_usdc") as string | null)?.trim() ||
    undefined;
  const maxConcurrentRaw = (
    formData.get("max_concurrent") as string | null
  )?.trim();
  const max_concurrent = maxConcurrentRaw
    ? Number.parseInt(maxConcurrentRaw, 10)
    : undefined;

  try {
    const agent = await apiPost<AgentIdentity>("/agents", {
      name,
      owner,
      description,
      capabilities,
      service_endpoints,
      pricing,
      discoverable: true,
      pricing_model,
      availability,
      min_objective_value_usdc,
      min_role_compensation_usdc,
      ...(max_concurrent && Number.isFinite(max_concurrent)
        ? { max_concurrent }
        : {}),
    });
    revalidatePath("/agents");
    return { ok: true, agent };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/** Result shape for a Trust API lookup. */
export type TrustLookupResult =
  | { ok: true; trust: TrustScore }
  | { ok: false; message: string };

/** Trust API: query reputation for any registered agent by its identity token. */
export async function lookupTrust(tokenId: string): Promise<TrustLookupResult> {
  const id = tokenId.trim();
  if (!id) return { ok: false, message: "Enter an agent identity token." };
  try {
    const trust = await apiGet<TrustScore>(`/trust/${encodeURIComponent(id)}`);
    return { ok: true, trust };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return { ok: false, message: "No registered agent for that token." };
    }
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/** Result shape for issuing a payout proof-of-control challenge. */
export type PayoutChallengeResult =
  | { ok: true; challenge: PayoutChallenge }
  | { ok: false; message: string };

/**
 * Escrow V1.5: issue a proof-of-control challenge for a candidate payout
 * address. The agent's wallet must sign the returned `challenge` string with the
 * payout wallet's private key; the signature is then submitted to verifyPayout.
 * Until that succeeds the address is never used as a settlement destination.
 */
export async function requestPayoutChallenge(
  agentId: string,
  address: string,
  blockchain?: string,
): Promise<PayoutChallengeResult> {
  const addr = address.trim();
  if (!addr) return { ok: false, message: "Enter a payout wallet address." };
  try {
    const challenge = await apiPost<PayoutChallenge>(
      `/agents/${agentId}/payout/challenge`,
      { address: addr, blockchain: blockchain?.trim() || undefined },
    );
    return { ok: true, challenge };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/**
 * Escrow V1.5: verify the signed challenge and bind the proven payout address.
 * On success the address becomes the agent's verified settlement destination and
 * the change is recorded in the payout audit trail.
 */
export async function verifyPayoutAddress(
  agentId: string,
  signature: string,
): Promise<LifecycleResult> {
  const sig = signature.trim();
  if (!sig) return { ok: false, message: "Paste the wallet signature." };
  try {
    await apiPost<AgentDetail>(`/agents/${agentId}/payout/verify`, {
      signature: sig,
    });
    revalidatePath(`/agents/${agentId}`);
    revalidatePath("/agents");
    return { ok: true };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

export type FeedbackResult =
  | { ok: true; commitment: FeedbackCommitment }
  | { ok: false; message: string };

/**
 * Blind-signature feedback — commit: bind the agent to its evaluation feedback
 * for one objective *before* the outcome is revealed. The signature is captured
 * now, so the agent cannot decline once it sees a negative result.
 */
export async function commitFeedback(
  agentId: string,
  objectiveId: string,
): Promise<FeedbackResult> {
  if (!objectiveId) return { ok: false, message: "Select an objective." };
  try {
    const commitment = await apiPost<FeedbackCommitment>(
      `/agents/${agentId}/feedback/commit`,
      { objective_id: objectiveId },
    );
    revalidatePath(`/agents/${agentId}`);
    return { ok: true, commitment };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

/**
 * Blind-signature feedback — reveal: disclose the committed outcome and fold it
 * into the agent's reputation. The pre-reveal signature is re-verified, so the
 * feedback is provably the one bound at commit time.
 */
export async function revealFeedback(
  agentId: string,
  commitmentId: string,
  success: boolean,
  note?: string,
): Promise<FeedbackResult> {
  if (!commitmentId) return { ok: false, message: "Missing commitment." };
  try {
    const commitment = await apiPost<FeedbackCommitment>(
      `/agents/${agentId}/feedback/reveal`,
      { commitment_id: commitmentId, success, note: note?.trim() || undefined },
    );
    revalidatePath(`/agents/${agentId}`);
    return { ok: true, commitment };
  } catch (err) {
    return { ok: false, message: apiErrorMessage(err) };
  }
}

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

// --- Onboarding (first-run journey) ----------------------------------------

/** Onboarding Step 2 — name the workspace + set governance defaults, then
 *  advance to Treasury Initialization. */
export async function updateWorkspace(formData: FormData) {
  const name = (formData.get("name") as string | null)?.trim() || undefined;
  const org_name =
    (formData.get("org_name") as string | null)?.trim() || undefined;
  const operational_type =
    (formData.get("operational_type") as string | null)?.trim() || undefined;
  const governance_require_auditor =
    formData.get("governance_require_auditor") === "on";
  const governance_human_authoritative =
    formData.get("governance_human_authoritative") === "on";

  await apiPatch<MeWorkspace>("/workspaces/current", {
    name,
    org_name,
    operational_type,
    governance_require_auditor,
    governance_human_authoritative,
  });
  revalidatePath("/onboarding/treasury");
  redirect("/onboarding/treasury");
}

/** Onboarding Step 3 — activate the treasury (the gate that opens Mission
 *  Control), then continue to the one-time orientation. */
export async function activateOnboarding() {
  await apiPost<MeWorkspace>("/workspaces/current/activate");
  // The onboarding gate is now satisfied; refresh the guarded surfaces.
  revalidatePath("/dashboard");
  revalidatePath("/onboarding/orientation");
  redirect("/onboarding/orientation");
}
