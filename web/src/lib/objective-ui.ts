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

/**
 * The canonical lifecycle, grouped into the six blueprint edges. Mission Control
 * renders objective counts across these phases so the whole Intent -> Settlement
 * loop is legible at a glance.
 */
export const LIFECYCLE_PHASES: {
  key: string;
  label: string;
  statuses: ObjectiveStatus[];
}[] = [
  { key: "intent", label: "Intent", statuses: ["draft"] },
  { key: "governance", label: "Governance", statuses: ["copilot_structured"] },
  { key: "escrow", label: "Escrow", statuses: ["escrow_locked"] },
  { key: "execution", label: "Execution", statuses: ["executing"] },
  {
    key: "validation",
    label: "Validation",
    statuses: ["under_audit", "governance_decision"],
  },
  {
    key: "settlement",
    label: "Settlement",
    statuses: ["settled", "slashed", "disputed"],
  },
];

export function phaseCount(
  counts: Record<string, number>,
  statuses: ObjectiveStatus[],
): number {
  return statuses.reduce((sum, s) => sum + (counts[s] ?? 0), 0);
}

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
