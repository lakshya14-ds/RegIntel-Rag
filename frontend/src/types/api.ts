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

export interface TimelineNodeResponse {
  document_id: string;
  title?: string | null;
  published_date?: string | null;
  status: string;
  relationship: string;
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
  timeline: TimelineNodeResponse[];
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
