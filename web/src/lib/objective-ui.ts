import type { ObjectiveStatus } from "@/lib/types";

type Tone = "success" | "pending" | "failure" | "neutral" | "active";

export const STATUS_META: Record<
  ObjectiveStatus,
  { label: string; tone: Tone }
> = {
  draft: { label: "Draft", tone: "neutral" },
  copilot_structured: { label: "Structured", tone: "active" },
  escrow_locked: { label: "Escrow Locked", tone: "active" },
  executing: { label: "Executing", tone: "active" },
  under_audit: { label: "Under Audit", tone: "pending" },
  governance_decision: { label: "Governance", tone: "pending" },
  settled: { label: "Settled", tone: "success" },
  slashed: { label: "Slashed", tone: "failure" },
  disputed: { label: "Disputed", tone: "failure" },
};

export function eventTone(kind: string): Tone {
  if (kind.includes("settle") || kind.includes("approved")) return "success";
  if (kind.includes("dispute") || kind.includes("slash") || kind.includes("fail"))
    return "failure";
  if (kind.includes("lock") || kind.includes("execut") || kind.includes("evaluat"))
    return "active";
  return "neutral";
}

export function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Short, monospace-friendly objective reference derived from the id. */
export function objRef(id: string): string {
  return `OBJ-${id.slice(0, 4).toUpperCase()}`;
}
