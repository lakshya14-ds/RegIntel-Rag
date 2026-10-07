/**
 * TypeScript API Types for RegIntel RAG.
 * Strictly aligned with FastAPI Pydantic Request & Response Models.
 */

export type RetrievalMode = 'hybrid' | 'hybrid_reranked' | 'bm25' | 'vector';

export type ChangeType = 'ADDED' | 'REMOVED' | 'MODIFIED' | 'UNCHANGED';

export type DocumentStatus = 'current' | 'historical' | 'superseded' | 'unknown';

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';

// ==========================================
// Health
// ==========================================
export interface HealthResponse {
  status: 'ok' | 'degraded' | 'unavailable';
  mongodb: boolean;
  embedding_service: boolean;
  environment?: string;
  version?: string;
}

// ==========================================
// Q&A / Ask
// ==========================================
export interface AskRequest {
  question: string;
  top_k?: number;
  retrieval_mode?: RetrievalMode;
  category?: string | null;
  source?: string | null;
}

export interface SourceCitationResponse {
  source_id: number;
  chunk_id: string;
  document_id: string;
  source: string;
  title: string;
  section?: string | null;
  published_date?: string | null;
  effective_date?: string | null;
  url: string;
  score: number;
}

export interface QueryIntentResponse {
  query_type: string;
  time_intent: string;
  source?: string | null;
  category?: string | null;
  document_type?: string | null;
  circular_number?: string | null;
  is_comparison: boolean;
}

export interface AskResponse {
  answer: string;
  sources: SourceCitationResponse[];
  query_intent?: QueryIntentResponse | null;
  sufficient_evidence: boolean;
  disclaimer: string;
  debug_info?: {
    request_id?: string;
    retrieval_mode?: string;
    retrieved_count?: number;
    sufficient_evidence?: boolean;
    provider?: string;
    model?: string;
    fallback_used?: boolean;
  } | null;
}

// ==========================================
// Multi-Method Search
// ==========================================
export interface SearchRequest {
  query: string;
  top_k?: number;
  retrieval_mode?: RetrievalMode;
  category?: string | null;
  source?: string | null;
}

export interface SearchItemResponse {
  rank: number;
  chunk_id: string;
  document_id: string;
  title?: string | null;
  section?: string | null;
  source: string;
  category?: string | null;
  document_type?: string | null;
  published_date?: string | null;
  effective_date?: string | null;
  url: string;
  score: number;
  content_snippet: string;
}

export interface SearchResponse {
  query: string;
  retrieval_mode: string;
  total_results: number;
  results: SearchItemResponse[];
}

// ==========================================
// Documents & Metadata
// ==========================================
export interface DocumentMetadataResponse {
  document_id: string;
  title?: string | null;
  source: string;
  category?: string | null;
  document_type?: string | null;
  circular_number?: string | null;
  published_date?: string | null;
  effective_date?: string | null;
  status?: string | null;
  url: string;
  supersedes?: string | null;
  superseded_by?: string | null;
  document_version?: string | null;
  content_hash?: string | null;
  relationship_type?: string | null;
  relationship_confidence?: string | null;
}

export interface DocumentRelationshipResponse {
  source_document_id: string;
  target_document_id: string;
  relationship_type: string;
  confidence: string;
  evidence?: string | null;
  is_explicit?: boolean;
}

export interface TimelineNodeResponse {
  document_id: string;
  title?: string | null;
  published_date?: string | null;
  effective_date?: string | null;
  status: string;
  relationship: string;
  relationship_to_previous?: string | null;
  relationship_confidence?: string | null;
  evidence?: string | null;
  is_branch?: boolean;
  parent_document_id?: string | null;
  chronology_uncertain?: boolean;
  order?: number;
}

export interface DocumentVersionResponse {
  document_id: string;
  title?: string | null;
  status: string;
  document_version: string;
  supersedes?: string | null;
  superseded_by?: string | null;
  predecessor?: DocumentMetadataResponse | null;
  successor?: DocumentMetadataResponse | null;
  predecessor_candidates: string[];
  relationship_type?: string | null;
  relationship_confidence?: string | null;
  has_reliable_predecessor?: boolean;
  chronology_uncertain?: boolean;
  timeline: TimelineNodeResponse[];
  events?: TimelineNodeResponse[];
  relationships?: DocumentRelationshipResponse[];
}

// ==========================================
// Document Comparison & Change Detection
// ==========================================
export interface CompareRequest {
  document_a_id: string;
  document_b_id: string;
}

export interface EvidenceSourceResponse {
  document_id: string;
  section_id: string;
  heading: string;
  section_number?: string | null;
  url?: string | null;
  published_date?: string | null;
}

export interface SectionChangeResponse {
  section_index: number;
  section?: string | null;
  heading: string;
  change_type: ChangeType | string;
  substantive_change: boolean;
  category?: string | null;
  modification_category?: string | null;
  previous_text?: string | null;
  current_text?: string | null;
  summary: string;
  old_requirement?: string | null;
  new_requirement?: string | null;
  compliance_impact?: string | null;
  impact?: string | null;
  similarity_score?: number | null;
  is_moved?: boolean;
  old_section_number?: string | null;
  numerical_changes?: Array<{
    parameter: string;
    previous_value: string;
    new_value: string;
    context?: string | null;
  }>;
  evidence?: unknown;
  old_source?: EvidenceSourceResponse | null;
  new_source?: EvidenceSourceResponse | null;
}

export interface CompareResponse {
  status: string;
  message?: string | null;
  document_a: DocumentMetadataResponse;
  document_b: DocumentMetadataResponse;
  older_document?: DocumentMetadataResponse | null;
  newer_document?: DocumentMetadataResponse | null;
  document_order_confidence: string;
  version_relationship: string;
  relationship_confidence: string;
  summary: string;
  executive_summary: string;
  key_changes: string[];
  total_changes: number;
  added_count: number;
  removed_count: number;
  modified_count: number;
  unchanged_count: number;
  summary_counts: Record<string, number>;
  statistics: Record<string, number>;
  changes: SectionChangeResponse[];
  cached: boolean;
}

// ==========================================
// Compliance Intelligence (Phases 61, 62, 63)
// ==========================================
export type RequirementType =
  | 'REPORTING'
  | 'DISCLOSURE'
  | 'RECORD_KEEPING'
  | 'APPROVAL'
  | 'NOTIFICATION'
  | 'PROHIBITION'
  | 'PERMISSION'
  | 'CALCULATION'
  | 'COMPLIANCE'
  | 'GOVERNANCE'
  | 'DOCUMENTATION'
  | 'MONITORING'
  | 'AUDIT'
  | 'SUBMISSION'
  | 'MAINTENANCE'
  | 'PROCEDURAL'
  | 'OTHER';

export type ObligationType =
  | 'MANDATORY'
  | 'CONDITIONAL_MANDATORY'
  | 'PROHIBITION'
  | 'PERMITTED'
  | 'RECOMMENDED'
  | 'INFORMATIONAL'
  | 'UNKNOWN';

export type ObligationStatus =
  | 'ACTIVE'
  | 'PROPOSED'
  | 'NOT_YET_EFFECTIVE'
  | 'SUPERSEDED'
  | 'REPEALED'
  | 'UNKNOWN';

export type ChecklistStatus =
  | 'NOT_REVIEWED'
  | 'COMPLIANT'
  | 'NON_COMPLIANT'
  | 'PARTIALLY_COMPLIANT'
  | 'NOT_APPLICABLE'
  | 'NEEDS_REVIEW'
  | 'UNKNOWN';

export interface RequirementThreshold {
  parameter_type: string;
  raw_value: string;
  normalized_value?: number | null;
  unit?: string | null;
  operator?: string | null;
}

export interface RegulatoryRequirement {
  requirement_id: string;
  document_id: string;
  document_version_id?: string | null;
  section_id?: string | null;
  authority: string;
  document_type?: string | null;
  document_title?: string | null;
  requirement_text: string;
  normalized_requirement?: string | null;
  requirement_type: RequirementType;
  subject?: string | null;
  action?: string | null;
  object?: string | null;
  applicability?: string | null;
  conditions: string[];
  exceptions: string[];
  effective_date?: string | null;
  deadline?: string | null;
  frequency?: string | null;
  thresholds: RequirementThreshold[];
  source_evidence: string;
  source_locator: Record<string, any>;
  confidence: string;
  extraction_method: string;
}

export interface RegulatoryObligation {
  obligation_id: string;
  requirement_id: string;
  document_id: string;
  document_version_id?: string | null;
  section_id?: string | null;
  obligated_party?: string | null;
  obligation_action?: string | null;
  obligation_object?: string | null;
  obligation_type: ObligationType;
  status: ObligationStatus;
  conditions: string[];
  exceptions: string[];
  trigger?: string | null;
  deadline?: string | null;
  frequency?: string | null;
  thresholds: RequirementThreshold[];
  required_evidence: string[];
  required_record?: string | null;
  required_submission?: string | null;
  applicability: Record<string, any>;
  effective_date?: string | null;
  confidence: string;
  source_evidence: string;
  source_locator: Record<string, any>;
}

export interface ChecklistItem {
  item_id: string;
  obligation_id: string;
  requirement_id: string;
  document_id: string;
  section_id?: string | null;
  control_question: string;
  compliance_action: string;
  obligated_party?: string | null;
  frequency?: string | null;
  deadline?: string | null;
  applicability?: string | null;
  evidence_required: string[];
  source_reference: Record<string, any>;
  status: ChecklistStatus;
  notes?: string | null;
  confidence: string;
  is_changed: boolean;
  change_summary?: string | null;
}

export interface ComplianceChecklist {
  checklist_id: string;
  title: string;
  description?: string | null;
  regulatory_scope: string;
  authority: string;
  document_ids: string[];
  items: ChecklistItem[];
  completion_rate: number;
  summary_counts: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface TraceabilityNode {
  item_id: string;
  control_question: string;
  status: string;
  obligation_id: string;
  obligated_party?: string | null;
  obligation_action?: string | null;
  obligation_type: string;
  requirement_id: string;
  requirement_type: string;
  requirement_text: string;
  document_id: string;
  section_id?: string | null;
  section_heading?: string | null;
  source_evidence: string;
  page_number?: number | null;
  is_valid: boolean;
  issues: string[];
}

// ==========================================
// Phase 64: Effective-Date Intelligence
// ==========================================
export interface RegulatoryDateEvent {
  event_id: string;
  document_id: string;
  document_version_id?: string | null;
  section_id?: string | null;
  event_type: string;
  date?: string | null;
  date_precision?: string;
  source_text: string;
  source_locator?: Record<string, any>;
  confidence: string;
  extraction_method: string;
  derivation_type: string;
  derivation_rule?: string | null;
  base_event_type?: string | null;
  offset_days?: number | null;
  created_at?: string;
}

export interface DateConflict {
  document_id: string;
  event_type: string;
  conflicting_values: Record<string, any>[];
  evidence: string;
  severity: 'WARNING' | 'ERROR' | 'UNKNOWN';
  resolution_status: string;
  notes?: string | null;
}

export interface TemporalStateEvaluation {
  document_id: string;
  document_version_id?: string | null;
  as_of_date: string;
  state: 'NOT_YET_EFFECTIVE' | 'EFFECTIVE' | 'EXPIRED' | 'SUPERSEDED' | 'REPEALED' | 'WITHDRAWN' | 'UNKNOWN';
  effective_date?: string | null;
  published_date?: string | null;
  expiry_date?: string | null;
  superseded_date?: string | null;
  derivation_type: string;
  reason: string;
  conflicts: DateConflict[];
  provenance: Record<string, any>;
}

export interface RequirementTemporalState {
  requirement_id: string;
  document_id: string;
  as_of_date: string;
  is_active: boolean;
  state: string;
  effective_date?: string | null;
  superseded_date?: string | null;
  reason: string;
}

export interface ObligationTemporalState {
  obligation_id: string;
  requirement_id: string;
  document_id: string;
  as_of_date: string;
  status: 'FUTURE' | 'ACTIVE' | 'HISTORICAL' | 'SUPERSEDED' | 'EXPIRED' | 'UNKNOWN';
  effective_date?: string | null;
  days_until_effective?: number | null;
  reason: string;
}

export interface ChecklistItemTemporalState {
  item_id: string;
  obligation_id: string;
  as_of_date: string;
  temporal_status: 'ACTIVE' | 'UPCOMING' | 'HISTORICAL' | 'NOT_YET_APPLICABLE' | 'SUPERSEDED' | 'UNKNOWN';
  effective_date?: string | null;
  days_until_effective?: number | null;
  is_actionable_now: boolean;
}

// ==========================================
// Phase 65: Regulatory Alerts & Deadlines
// ==========================================
export type AlertSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
export type AlertStatus = 'UNREAD' | 'READ' | 'DISMISSED';

export interface AlertExplanation {
  why_am_i_seeing_this: string;
  what_changed?: string | null;
  when_effective?: string | null;
  affected_requirement?: string | null;
  affected_obligation?: string | null;
  action_recommended?: string | null;
  source?: string | null;
}

export interface RegulatoryAlert {
  alert_id: string;
  dedup_hash: string;
  alert_type: string;
  severity: AlertSeverity;
  title: string;
  message: string;
  event_id?: string | null;
  document_id?: string | null;
  requirement_id?: string | null;
  obligation_id?: string | null;
  checklist_item_id?: string | null;
  trigger_date: string;
  effective_date?: string | null;
  deadline?: string | null;
  source_reference: Record<string, any>;
  explanation: AlertExplanation;
  status: AlertStatus;
  channel: string;
  created_at: string;
  read_at?: string | null;
  dismissed_at?: string | null;
}

export interface RegulatoryDeadline {
  deadline_id: string;
  obligation_id: string;
  requirement_id?: string | null;
  document_id: string;
  deadline_type: string;
  trigger_event?: string | null;
  deadline_expression: string;
  due_date?: string | null;
  due_date_derivation: string;
  frequency?: string | null;
  grace_period?: string | null;
  source_evidence: string;
  confidence: string;
  status: 'UPCOMING' | 'DUE_SOON' | 'DUE_TODAY' | 'OVERDUE' | 'COMPLETED' | 'NOT_APPLICABLE' | 'UNKNOWN';
  days_remaining?: number | null;
  recurrence_rule?: Record<string, any> | null;
  created_at?: string;
}

export interface Watchlist {
  watchlist_id: string;
  user_id: string;
  name: string;
  authorities: string[];
  document_ids: string[];
  topics: string[];
  requirement_types: string[];
  obligation_types: string[];
  event_types: string[];
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

// ==========================================
// Multi-Regulator Authority & Connectors (Phases 66–69)
// ==========================================
export type RegulatoryAuthority = 'SEBI' | 'RBI' | 'IRDAI' | 'PFRDA' | 'IFSCA';

export interface AuthorityMetadata {
  code: RegulatoryAuthority;
  name: string;
  short_name: string;
  country: string;
  domain: string;
  official_domain: string;
  description: string;
  enabled: boolean;
  default_document_types: string[];
}

export interface RegulatorySourceInfo {
  source_id: string;
  authority: RegulatoryAuthority;
  source_type: string;
  name: string;
  base_url: string;
  listing_url: string;
  enabled: boolean;
  crawl_frequency: string;
  document_types: string[];
  category?: string | null;
  priority: number;
}

export interface ConnectorRun {
  run_id: string;
  authority: RegulatoryAuthority;
  started_at: string;
  completed_at?: string | null;
  status: 'RUNNING' | 'SUCCESS' | 'PARTIAL_SUCCESS' | 'FAILED';
  discovered_count: number;
  downloaded_count: number;
  new_documents: number;
  changed_documents: number;
  skipped_documents: number;
  failed_documents: number;
  errors: any[];
  warnings: string[];
  duration_seconds?: number | null;
}

export interface ConnectorHealth {
  authority: RegulatoryAuthority;
  status: 'HEALTHY' | 'WARNING' | 'FAILED' | 'UNKNOWN';
  last_run_at?: string | null;
  last_run_status?: string | null;
  last_run_id?: string | null;
  total_discovered_last_run: number;
  consecutive_failures: number;
  error_summary?: string | null;
}

// ==========================================
// Phase 73: Cross-Regulator Overlaps
// ==========================================
export type OverlapType =
  | 'IDENTICAL'
  | 'NEAR_DUPLICATE'
  | 'OVERLAPPING'
  | 'COMPLEMENTARY'
  | 'RELATED'
  | 'DISTINCT'
  | 'UNKNOWN';

export type OverlapStatus =
  | 'ACTIVE'
  | 'HISTORICAL'
  | 'FUTURE'
  | 'UNKNOWN'
  | 'SUPERSEDED';

export interface RegulatoryOverlap {
  overlap_id: string;
  left_authority: string;
  left_document_id: string;
  left_document_version_id?: string | null;
  left_section_id?: string | null;
  left_requirement_id: string;
  left_obligation_id?: string | null;

  right_authority: string;
  right_document_id: string;
  right_document_version_id?: string | null;
  right_section_id?: string | null;
  right_requirement_id: string;
  right_obligation_id?: string | null;

  relationship_type: OverlapType;
  shared_topic?: string | null;
  shared_activity?: string | null;
  similarity_score: number;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  reasoning: string;

  evidence_left: string;
  evidence_right: string;

  effective_date_left?: string | null;
  effective_date_right?: string | null;
  status: OverlapStatus;
  applicability_match?: string | null;
  parameter_comparison?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

// ==========================================
// Phase 74: Cross-Regulator Conflicts
// ==========================================
export type RegulatoryConflictType =
  | 'PARAMETER_CONFLICT'
  | 'DEADLINE_CONFLICT'
  | 'FREQUENCY_CONFLICT'
  | 'ACTION_CONFLICT'
  | 'PROHIBITION_CONFLICT'
  | 'APPLICABILITY_CONFLICT'
  | 'DEFINITION_CONFLICT'
  | 'SEQUENCING_CONFLICT'
  | 'POTENTIAL_INCONSISTENCY'
  | 'NO_CONFLICT'
  | 'UNKNOWN';

export type ConflictSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'UNKNOWN';
export type ConflictResolutionStatus =
  | 'OPEN'
  | 'UNDER_REVIEW'
  | 'RESOLVED'
  | 'DISMISSED'
  | 'FALSE_POSITIVE'
  | 'UNKNOWN';

export interface ConflictReviewEvent {
  reviewer_id: string;
  timestamp: string;
  previous_status: string;
  new_status: string;
  notes?: string | null;
}

export interface RegulatoryConflict {
  conflict_id: string;
  overlap_id?: string | null;
  left_requirement_id: string;
  left_obligation_id?: string | null;
  left_authority: string;
  left_document_id?: string | null;
  left_section_id?: string | null;

  right_requirement_id: string;
  right_obligation_id?: string | null;
  right_authority: string;
  right_document_id?: string | null;
  right_section_id?: string | null;

  conflict_type: RegulatoryConflictType;
  severity: ConflictSeverity;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN';
  conflicting_fields: string[];
  left_value: Record<string, any>;
  right_value: Record<string, any>;
  applicability_scope?: string | null;
  temporal_scope?: string | null;
  explanation: string;

  evidence_left: string;
  evidence_right: string;

  resolution_status: ConflictResolutionStatus;
  review_history: ConflictReviewEvent[];
  created_at: string;
  updated_at: string;
}

// ==========================================
// Agentic & Multi-Hop RAG (Phases 75-78)
// ==========================================
export interface SubQuestionItem {
  id: string;
  text: string;
  purpose?: string;
  authority_scope?: string;
  expected_evidence_type?: string;
  status: string;
  rewritten_query?: string;
  depends_on?: string[];
}

export interface QueryPlanResponse {
  plan_id: string;
  query_id: string;
  original_query: string;
  sub_questions: SubQuestionItem[];
  execution_order: string[][];
  planned_tools: string[];
}

export interface VerifiedClaimItem {
  claim_id: string;
  text: string;
  claim_type: string;
  supporting_evidence_ids: string[];
  confidence: number;
  verification_status: string;
  verification_notes?: string;
}

export interface AgenticRAGResponse {
  query_id: string;
  question: string;
  answer: string;
  is_agentic: boolean;
  fast_path_used: boolean;
  strategy_used: string;
  plan?: QueryPlanResponse | null;
  total_hops: number;
  total_evidence_count: number;
  verification_rate: number;
  verified_claims: VerifiedClaimItem[];
  citations: Array<{
    citation_number?: number;
    evidence_id?: string;
    type?: string;
    authority?: string;
    document_id?: string;
    section_id?: string;
    text_snippet?: string;
    snippet?: string;
    title?: string;
  }>;
  evidence_graph_summary: {
    total_nodes: number;
    total_edges: number;
    authorities: string[];
    node_types: Record<string, number>;
  };
  operational_steps: string[];
  execution_time_seconds: number;
}



