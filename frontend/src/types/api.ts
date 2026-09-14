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

