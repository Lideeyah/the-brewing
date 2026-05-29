// Wire contracts mirrored from the FastAPI schemas. Kept minimal and explicit.

export type ObjectiveStatus =
  | "draft"
  | "copilot_structured"
  | "escrow_locked"
  | "executing"
  | "under_audit"
  | "governance_decision"
  | "settled"
  | "slashed"
  | "disputed";

export interface Objective {
  id: string;
  workspace_id: string;
  title: string;
  intent: string;
  status: ObjectiveStatus;
  summary?: string | null;
  escrow_amount_usdc: string;
  created_at: string;
  updated_at: string;
}

export interface GovernanceEvent {
  id: string;
  kind: string;
  message: string;
  actor?: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

export interface Escrow {
  id: string;
  status: string;
  amount_usdc: string;
  address?: string | null;
  provider_escrow_id?: string | null;
  lock_tx_ref?: string | null;
  explorer_url?: string | null;
}

export interface ExecutionStep {
  id: string;
  index: number;
  title: string;
  status: string;
  output?: string | null;
}

export interface ExecutionRun {
  id: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  steps: ExecutionStep[];
}

export interface AuditReview {
  id: string;
  status: string;
  notes?: string | null;
  created_at: string;
}

export interface Settlement {
  id: string;
  status: string;
  amount_usdc: string;
  fee_usdc: string;
  payout_address?: string | null;
  payout_tx_ref?: string | null;
  explorer_url?: string | null;
}

export interface ObjectiveDetail extends Objective {
  governance_config: Record<string, unknown>;
  sla_config: Record<string, unknown>;
  settlement_config: Record<string, unknown>;
  orchestration_plan: { steps?: { title: string; detail?: string }[] } & Record<
    string,
    unknown
  >;
  timeline: GovernanceEvent[];
  escrow?: Escrow | null;
  treasury_address?: string | null;
  execution?: ExecutionRun | null;
  audit?: AuditReview | null;
  settlement?: Settlement | null;
}

export interface OverviewMetric {
  label: string;
  value: string;
  hint?: string | null;
}

export interface Overview {
  metrics: OverviewMetric[];
  status_counts: Record<string, number>;
  treasury_balance_usdc: string;
  objectives: Objective[];
  recent_events: GovernanceEvent[];
}
