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

export type RiskCategory =
  | "evidence"
  | "financial"
  | "governance"
  | "execution"
  | "compliance";

export type RiskSeverity = "low" | "medium" | "high";

export interface GovernanceRisk {
  category: RiskCategory | string;
  severity: RiskSeverity | string;
  detail: string;
}

export type Recommendation =
  | "approved"
  | "approved_with_conditions"
  | "rejected";

export interface GovernanceEvaluation {
  id: string;
  role_id?: string | null;
  recommendation: Recommendation;
  reasoning: string;
  findings: GovernanceFinding[];
  risks: GovernanceRisk[];
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

export interface CriterionBasis {
  step_index?: number | null;
  step_title?: string | null;
  output_kind?: string | null;
  quality?: string | null;
  matched_terms: string[];
}

export interface CriterionResult {
  key: string;
  description: string;
  required_evidence_kind?: string | null;
  satisfied?: boolean | null; // true | false | null (indeterminate)
  confidence: number;
  rationale: string;
  basis: CriterionBasis[];
}

export interface SettlementAuthorization {
  id: string;
  objective_id: string;
  role_id?: string | null;
  evidence_hash: string;
  criteria_results: CriterionResult[];
  criteria_total: number;
  criteria_satisfied: number;
  criteria_failed: number;
  criteria_indeterminate: number;
  evidence_verdict: Recommendation;
  headline: string;
  governance_approved?: boolean | null;
  aligned_with_evidence?: boolean | null;
  authorized?: boolean | null;
  created_at: string;
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

export type SubTaskValidationStatus = "pending" | "passed" | "failed";
export type SubTaskSettlementStatus = "pending" | "settled" | "slashed";

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
  outcome?: string | null;
  // Coordination contract + per-sub-task state.
  depends_on: string[];
  success_criteria: (string | Record<string, unknown>)[];
  required_evidence_kinds: string[];
  required: boolean;
  validation_status: SubTaskValidationStatus;
  settlement_status: SubTaskSettlementStatus;
  authorization?: SettlementAuthorization | null;
  settlement?: Settlement | null;
  // Advisory Copilot evaluation scoped to this sub-task's own criteria.
  evaluation?: GovernanceEvaluation | null;
}

// ready: deps satisfied, not yet validated. blocked: a dep still pending.
// blocked_failed: a dep failed (can never pass). cycle: part of a dep cycle.
export type DependencyState = "ready" | "blocked" | "blocked_failed" | "cycle";

export interface CoordinationNode {
  role_id: string;
  role_key: string;
  title: string;
  order_index: number;
  wave?: number | null;
  depends_on: string[];
  required: boolean;
  allocation_usdc: string;
  assigned_agent_id?: string | null;
  validation_status: SubTaskValidationStatus;
  settlement_status: SubTaskSettlementStatus;
  dependency_state: DependencyState;
  ready: boolean;
}

export interface CoordinationEdge {
  from_role: string;
  to_role: string;
}

export interface CoordinationGraph {
  nodes: CoordinationNode[];
  edges: CoordinationEdge[];
  waves: string[][];
  has_cycle: boolean;
  cycle_role_ids: string[];
  required_total: number;
  required_passed: number;
  required_failed: number;
  parent_settleable: boolean;
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

export interface EvidenceTrailItem {
  step_index: number;
  step_title: string;
  status: string;
  output_kind: string;
  quality: string;
  has_errors: boolean;
  snippet: string;
  supports_criteria: string[];
  validation_flagged: boolean;
}

export interface EvidenceTrailStage {
  key: string; // output | evidence | validation | authorization | settlement
  label: string;
  complete: boolean;
  detail: string;
}

export interface EvidenceTrail {
  evidence_hash?: string | null;
  hash_consistent: boolean;
  items: EvidenceTrailItem[];
  stages: EvidenceTrailStage[];
  criteria_total: number;
  criteria_satisfied: number;
}

export interface WalletMovement {
  kind: string; // lock | release | slash
  label: string;
  amount_usdc: string;
  direction: string; // inbound | outbound
  from_label?: string | null;
  from_address?: string | null;
  to_label?: string | null;
  to_address?: string | null;
  to_explorer_url?: string | null;
  tx_hash?: string | null;
  tx_url?: string | null;
  tx_ref?: string | null;
  confirmed: boolean;
  role_id?: string | null;
  role_title?: string | null;
  occurred_at: string;
}

export interface OnChainLedger {
  blockchain?: string | null;
  treasury_address?: string | null;
  treasury_explorer_url?: string | null;
  escrow_address?: string | null;
  escrow_explorer_url?: string | null;
  movements: WalletMovement[];
  total_locked_usdc: string;
  total_released_usdc: string;
  total_slashed_usdc: string;
  total_fees_usdc: string;
  confirmed_count: number;
  pending_count: number;
}

export interface ObjectiveDetail extends Objective {
  governance_config: Record<string, unknown>;
  sla_config: Record<string, unknown>;
  definition_of_done?: string | null;
  deadline?: string | null;
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
  authorization?: SettlementAuthorization | null;
  settlement?: Settlement | null;
  assigned_agent?: AssignedAgent | null;
  workflow: WorkflowRole[];
  coordination?: CoordinationGraph | null;
  feasibility?: FeasibilityReport | null;
  evidence_trail?: EvidenceTrail | null;
  onchain_ledger?: OnChainLedger | null;
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
  // Payout destination (Escrow V1.5). Only a *verified* address is ever used as
  // a settlement destination; `payout_address_verified` reflects proof-of-control.
  payout_address?: string | null;
  payout_blockchain?: string | null;
  payout_address_verified: boolean;
  payout_address_verified_at?: string | null;
  created_at: string;
}

export interface PayoutAddressEvent {
  id: string;
  action: string; // challenge_issued | registered | changed | verification_failed | cleared
  old_address?: string | null;
  new_address?: string | null;
  verified: boolean;
  actor?: string | null;
  note?: string | null;
  created_at: string;
}

export interface PayoutChallenge {
  agent_id: string;
  address: string;
  challenge: string;
  expires_at: string;
}

export interface ReputationDimension {
  key: string;
  label: string;
  value?: number | null;
  sample_size: number;
  hint?: string | null;
}

export interface AgentDetail extends AgentIdentity {
  reputation_history: ReputationEvent[];
  trust_dimensions: ReputationDimension[];
  payout_history: PayoutAddressEvent[];
}

export interface FeedbackCommitment {
  id: string;
  agent_id: string;
  objective_id: string;
  objective_title?: string | null;
  commitment_hash: string;
  signature: string;
  revealed: boolean;
  outcome?: string | null; // "success" | "failure", set only at reveal
  created_at: string;
  revealed_at?: string | null;
}

export interface FeedbackObjectiveOption {
  id: string;
  title: string;
  status: string;
  committed: boolean;
}

export interface AgentFeedback {
  commitments: FeedbackCommitment[];
  objectives: FeedbackObjectiveOption[];
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
  trust_dimensions: ReputationDimension[];
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

export interface MeUser {
  id: string;
  email: string;
  name?: string | null;
  image?: string | null;
}

export interface MeWorkspace {
  id: string;
  name: string;
  org_name?: string | null;
  operational_type?: string | null;
  subscription_tier: string;
  onboarding_completed: boolean;
  governance_require_auditor: boolean;
  governance_human_authoritative: boolean;
  treasury_address?: string | null;
  treasury_blockchain?: string | null;
}

export interface Me {
  user: MeUser;
  workspace: MeWorkspace;
  role: string;
}
