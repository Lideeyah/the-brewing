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

export type CustodyModel = "custodial" | "non_custodial";

export interface Escrow {
  id: string;
  status: string;
  amount_usdc: string;
  custody_model: CustodyModel;
  controller_wallet?: string | null;
  address?: string | null;
  provider_escrow_id?: string | null;
  lock_tx_ref?: string | null;
  lock_tx_hash?: string | null;
  lock_tx_url?: string | null;
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

export interface GovernanceFinding {
  criterion: string;
  met: boolean;
  assessment?: string | null;
}

export type Recommendation =
  | "approved"
  | "approved_with_conditions"
  | "rejected";

export interface GovernanceEvaluation {
  id: string;
  recommendation: Recommendation;
  reasoning: string;
  findings: GovernanceFinding[];
  conditions: string[];
  source: string;
  created_at: string;
}

export interface AuditReview {
  id: string;
  status: string;
  notes?: string | null;
  recommendation?: string | null;
  overridden: boolean;
  created_at: string;
}

export interface Settlement {
  id: string;
  status: string;
  amount_usdc: string;
  fee_usdc: string;
  fee_basis?: string | null;
  payout_address?: string | null;
  payout_tx_ref?: string | null;
  payout_tx_hash?: string | null;
  payout_tx_url?: string | null;
  explorer_url?: string | null;
}

export interface Validator {
  id: string;
  validator_key: string;
  name: string;
  kind: string;
  description?: string | null;
  independent: boolean;
  active: boolean;
  validations_count: number;
  upheld_count: number;
  overturned_count: number;
  accuracy?: number | null;
  mean_confidence: number;
  created_at: string;
}

export interface ValidationFinding {
  step_index?: number | null;
  step_title?: string | null;
  output_kind?: string | null;
  quality?: string | null;
  errors: boolean;
}

export interface ValidationRecord {
  id: string;
  objective_id: string;
  recommendation: Recommendation;
  confidence: number;
  reasoning: string;
  findings: ValidationFinding[];
  evidence_hash: string;
  evidence_summary: Record<string, unknown>;
  executor_agent_id?: string | null;
  independent_of_executor: boolean;
  outcome?: string | null;
  upheld?: boolean | null;
  created_at: string;
  reconciled_at?: string | null;
  validator?: Validator | null;
}

export interface AssignedAgent {
  id: string;
  token_id: string;
  name: string;
  reputation_score: number;
  jobs_completed: number;
  jobs_failed: number;
  rated: boolean;
  success_rate?: number | null;
}

export type RoleStatus = "pending" | "assigned" | "completed" | "failed";

export interface WorkflowRole {
  id: string;
  order_index: number;
  role_key: string;
  title: string;
  description?: string | null;
  assigned_agent_id?: string | null;
  assigned_agent?: AssignedAgent | null;
  allocation_usdc: string;
  status: RoleStatus;
}

export interface FeasibilityRoleCheck {
  role_id: string;
  role_key: string;
  title: string;
  allocation_usdc: string;
  assigned_agent_id?: string | null;
  assigned_agent_name?: string | null;
  ok: boolean;
  issues: string[];
}

export interface FeasibilityReport {
  feasible: boolean;
  budget_usdc: string;
  required_usdc: string;
  shortfall_usdc: string;
  over_budget: boolean;
  blocking_roles: number;
  role_checks: FeasibilityRoleCheck[];
  recommendations: string[];
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
  evaluation?: GovernanceEvaluation | null;
  validation?: ValidationRecord | null;
  audit?: AuditReview | null;
  settlement?: Settlement | null;
  assigned_agent?: AssignedAgent | null;
  workflow: WorkflowRole[];
  feasibility?: FeasibilityReport | null;
}

export interface ServiceEndpoint {
  name: string;
  url: string;
  protocol?: string | null;
}

export interface ReputationEvent {
  id: string;
  objective_id?: string | null;
  kind: string;
  delta: number;
  score_after: number;
  note?: string | null;
  created_at: string;
}

export interface AgentIdentity {
  id: string;
  token_id: string;
  owner: string;
  name: string;
  description?: string | null;
  capabilities: string[];
  service_endpoints: ServiceEndpoint[];
  pricing?: string | null;
  discoverable: boolean;
  reputation_score: number;
  jobs_completed: number;
  jobs_failed: number;
  rated: boolean;
  success_rate?: number | null;
  pricing_model: string;
  min_objective_value_usdc?: string | null;
  min_role_compensation_usdc?: string | null;
  availability: string;
  max_concurrent: number;
  metadata_uri?: string | null;
  registry_chain?: string | null;
  registry_address?: string | null;
  signing_pubkey?: string | null;
  created_at: string;
}

export interface AgentDetail extends AgentIdentity {
  reputation_history: ReputationEvent[];
}

export interface TrustScore {
  token_id: string;
  name: string;
  owner: string;
  description?: string | null;
  pricing?: string | null;
  reputation_score: number;
  jobs_completed: number;
  jobs_failed: number;
  total_jobs: number;
  success_rate?: number | null;
  rated: boolean;
  capabilities: string[];
  service_endpoints: ServiceEndpoint[];
  registry_chain?: string | null;
  registry_address?: string | null;
  last_outcome_at?: string | null;
  recent_events: ReputationEvent[];
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

export interface KpiMetric {
  key: string;
  label: string;
  value: string;
  hint?: string | null;
  raw?: number | null;
}

export interface Kpis {
  generated_at: string;
  window: string;
  governed_transaction_volume_usdc: string;
  mean_time_to_settlement_seconds?: number | null;
  mean_time_to_settlement_human?: string | null;
  attestation_discrepancy_rate: number;
  active_escrow_accounts: number;
  take_rate_drag: number;
  settled_count: number;
  slashed_count: number;
  total_settlements: number;
  fees_collected_usdc: string;
  metrics: KpiMetric[];
}
