// Mirrors the Pydantic models in src/main/backend/models and the API
// response shapes in src/main/backend/api. Kept hand-written and minimal —
// only the fields screens actually render.

export type IncidentStatus =
  | "OPEN" | "INVESTIGATING" | "AWAITING_EVIDENCE" | "ACTION_PROPOSED"
  | "ACTION_PENDING" | "RESOLVED" | "CLOSED"

export type ReconciliationStatus =
  | "CONFIRMED" | "PENDING" | "STATUS_MISMATCH" | "MERCHANT_CONFIRMATION_MISSING"
  | "INSUFFICIENT_EVIDENCE" | "POSSIBLE_DUPLICATE" | "REVERSAL_UNVERIFIED" | "UNRESOLVED"

export type SourceMode = "SIMULATED" | "LIVE" | "UNAVAILABLE" | "AWAITING_AUTHORIZATION"

export interface Incident {
  incident_id: string
  created_at: string
  updated_at: string
  title: string
  complaint: string
  transaction_ref: string | null
  amount: string
  currency: string
  merchant_id: string
  payment_attempt_id: string | null
  incident_status: IncidentStatus
  reconciliation_status: ReconciliationStatus | null
  source_mode: SourceMode
  evidence_ids: string[]
}

export interface SourceEvent {
  event_id: string
  incident_id: string
  transaction_ref: string | null
  source_system: string
  event_type: string
  event_time: string
  ingested_at: string
  source_status: string
  normalized_status: string
  amount: string | null
  correlation_ids: string[]
  verification_status: "VERIFIED" | "UNVERIFIED" | "CONFLICTED" | "NOT_APPLICABLE"
  source_mode: SourceMode
}

export interface EvidenceRecord {
  evidence_id: string
  incident_id: string
  evidence_type: string
  source_system: string
  title: string
  content: string
  event_time: string | null
  ingested_at: string
  verification_status: "VERIFIED" | "UNVERIFIED" | "CONFLICTED" | "NOT_APPLICABLE"
  source_mode: SourceMode
  metadata: Record<string, unknown>
}

export interface Runbook {
  runbook_id: string
  title: string
  scenario_tags: string[]
  content: string
  sections: string[]
  source: string
  version: string
}

export interface ReconciliationResult {
  incident_id: string
  classification: ReconciliationStatus
  confirmed_facts: string[]
  conflicts: string[]
  missing_evidence: string[]
  unresolved_questions: string[]
  permitted_checks: string[]
  action_restrictions: string[]
  evidence_ids: string[]
  rules_applied: string[]
}

export interface InvestigationReport {
  incident_id: string
  summary: string
  confirmed_facts: string[]
  competing_hypotheses: string[]
  supporting_evidence: string[]
  contradicting_evidence: string[]
  missing_evidence: string[]
  recommended_checks: string[]
  recommended_next_action: string
  reasoning: string
  uncertainty_explanation: string
  citation_ids: string[]
  unresolved_status: boolean
  ai_used: boolean
  source_mode: SourceMode
  model_identifier: string
  unsupported_claims_removed: string[]
  policy_override_applied: boolean
}

export interface SimilarCase {
  incident_id: string
  title: string
  similarity_score: number
  shared_terms: string[]
  method: "lexical" | "semantic_rag"
}

export interface SampleIncidentSummary {
  incident_id: string
  title: string
  scenario_category: string
}

export interface ActionProposal {
  action_id: string
  incident_id: string
  action_type: string
  description: string
  rationale: string
  evidence_ids: string[]
  requires_human_approval: boolean
  proposed_at: string
  status: "PROPOSED" | "APPROVED" | "REJECTED" | "EXECUTED" | "FAILED"
}

export interface ExecuteActionResult {
  approved: boolean
  execution_id: string | null
  execution_status: string | null
  reason: string
}

export interface VerifyActionResult {
  result: "VERIFIED" | "NOT_VERIFIED" | "UNKNOWN"
  evidence_ids: string[]
}

export interface AuditRecord {
  audit_record_id: string
  incident_id: string
  actor_id: string
  event_type: string
  timestamp: string
  result: string
  execution_mode: "SIMULATED" | "LIVE"
  metadata: Record<string, unknown>
}
