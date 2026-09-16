/**
 * Compliance and Requirement Intelligence API Client (Phases 61, 62, 63).
 */

import {
  RegulatoryRequirement,
  RegulatoryObligation,
  ComplianceChecklist,
  TraceabilityNode,
  RegulatoryDateEvent,
  TemporalStateEvaluation,
  RequirementTemporalState,
  ObligationTemporalState,
  ChecklistItemTemporalState,
  RegulatoryAlert,
  RegulatoryDeadline,
  Watchlist,
  AuthorityMetadata,
  RegulatorySourceInfo,
  ConnectorHealth,
  ConnectorRun,
  RegulatoryOverlap,
  RegulatoryConflict,
} from '../types/api';
import { apiClient } from './client';

export async function fetchRequirements(params?: {
  document_id?: string;
  section_id?: string;
  authority?: string;
  requirement_type?: string;
  confidence?: string;
  limit?: number;
}): Promise<RegulatoryRequirement[]> {
  const query = new URLSearchParams();
  if (params?.document_id) query.append('document_id', params.document_id);
  if (params?.section_id) query.append('section_id', params.section_id);
  if (params?.authority) query.append('authority', params.authority);
  if (params?.requirement_type) query.append('requirement_type', params.requirement_type);
  if (params?.confidence) query.append('confidence', params.confidence);
  if (params?.limit) query.append('limit', params.limit.toString());

  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/requirements?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch requirements');
  return res.json();
}

export async function fetchRequirement(id: string): Promise<RegulatoryRequirement> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/requirements/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to fetch requirement ${id}`);
  return res.json();
}

export async function fetchDocumentRequirements(documentId: string): Promise<RegulatoryRequirement[]> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/documents/${encodeURIComponent(documentId)}/requirements`);
  if (!res.ok) throw new Error(`Failed to fetch requirements for document ${documentId}`);
  return res.json();
}

export async function extractDocumentRequirements(
  documentId: string,
  useLlm: boolean = false,
  force: boolean = false
): Promise<RegulatoryRequirement[]> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(
    `${baseUrl}/documents/${encodeURIComponent(documentId)}/extract-requirements?use_llm=${useLlm}&force=${force}`,
    { method: 'POST' }
  );
  if (!res.ok) throw new Error(`Failed to extract requirements for document ${documentId}`);
  return res.json();
}

export async function fetchObligations(params?: {
  document_id?: string;
  requirement_id?: string;
  obligated_party?: string;
  obligation_type?: string;
  status?: string;
  limit?: number;
}): Promise<RegulatoryObligation[]> {
  const query = new URLSearchParams();
  if (params?.document_id) query.append('document_id', params.document_id);
  if (params?.requirement_id) query.append('requirement_id', params.requirement_id);
  if (params?.obligated_party) query.append('obligated_party', params.obligated_party);
  if (params?.obligation_type) query.append('obligation_type', params.obligation_type);
  if (params?.status) query.append('status', params.status);
  if (params?.limit) query.append('limit', params.limit.toString());

  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/obligations?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch obligations');
  return res.json();
}

export async function fetchObligation(id: string): Promise<RegulatoryObligation> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/obligations/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to fetch obligation ${id}`);
  return res.json();
}

export async function fetchChecklists(): Promise<ComplianceChecklist[]> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/compliance/checklists`);
  if (!res.ok) throw new Error('Failed to fetch compliance checklists');
  return res.json();
}

export async function fetchChecklist(id: string): Promise<ComplianceChecklist> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/compliance/checklists/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to fetch checklist ${id}`);
  return res.json();
}

export async function generateChecklist(payload: {
  title: string;
  document_ids?: string[];
  authority?: string;
  entity_filter?: string;
  description?: string;
}): Promise<ComplianceChecklist> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/compliance/checklists/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to generate compliance checklist');
  }
  return res.json();
}

export async function updateChecklistItem(
  checklistId: string,
  itemId: string,
  payload: { status?: string; notes?: string }
): Promise<ComplianceChecklist> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(
    `${baseUrl}/compliance/checklists/${encodeURIComponent(checklistId)}/items/${encodeURIComponent(itemId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) throw new Error('Failed to update checklist item');
  return res.json();
}

export async function regenerateChecklist(checklistId: string): Promise<ComplianceChecklist> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(
    `${baseUrl}/compliance/checklists/${encodeURIComponent(checklistId)}/regenerate`,
    { method: 'POST' }
  );
  if (!res.ok) throw new Error('Failed to regenerate checklist');
  return res.json();
}

export async function exportChecklist(checklistId: string, format: 'markdown' | 'json' = 'markdown'): Promise<string> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(
    `${baseUrl}/compliance/checklists/${encodeURIComponent(checklistId)}/export?format=${format}`
  );
  if (!res.ok) throw new Error('Failed to export checklist');
  return res.text();
}

export async function fetchItemTraceability(checklistId: string, itemId: string): Promise<TraceabilityNode> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(
    `${baseUrl}/compliance/checklists/${encodeURIComponent(checklistId)}/traceability/${encodeURIComponent(itemId)}`
  );
  if (!res.ok) throw new Error('Failed to fetch item traceability');
  return res.json();
}

// =============================================================================
// PHASE 64: EFFECTIVE-DATE INTELLIGENCE (64.8, 64.9, 64.14, 64.15)
// =============================================================================

export async function fetchDocumentRegulatoryState(
  documentId: string,
  asOf?: string
): Promise<TemporalStateEvaluation> {
  const baseUrl = apiClient.getBaseUrl();
  const url = asOf
    ? `${baseUrl}/regulatory-state/${encodeURIComponent(documentId)}?as_of=${encodeURIComponent(asOf)}`
    : `${baseUrl}/regulatory-state/${encodeURIComponent(documentId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch document regulatory state');
  return res.json();
}

export async function fetchRequirementState(
  requirementId: string,
  asOf?: string
): Promise<RequirementTemporalState> {
  const baseUrl = apiClient.getBaseUrl();
  const url = asOf
    ? `${baseUrl}/requirements/${encodeURIComponent(requirementId)}/state?as_of=${encodeURIComponent(asOf)}`
    : `${baseUrl}/requirements/${encodeURIComponent(requirementId)}/state`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch requirement temporal state');
  return res.json();
}

export async function fetchObligationState(
  obligationId: string,
  asOf?: string
): Promise<ObligationTemporalState> {
  const baseUrl = apiClient.getBaseUrl();
  const url = asOf
    ? `${baseUrl}/obligations/${encodeURIComponent(obligationId)}/state?as_of=${encodeURIComponent(asOf)}`
    : `${baseUrl}/obligations/${encodeURIComponent(obligationId)}/state`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch obligation temporal state');
  return res.json();
}

export async function fetchChecklistTemporalState(
  checklistId: string,
  asOf?: string
): Promise<ChecklistItemTemporalState[]> {
  const baseUrl = apiClient.getBaseUrl();
  const url = asOf
    ? `${baseUrl}/compliance/checklists/${encodeURIComponent(checklistId)}/temporal-state?as_of=${encodeURIComponent(asOf)}`
    : `${baseUrl}/compliance/checklists/${encodeURIComponent(checklistId)}/temporal-state`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch checklist temporal state');
  return res.json();
}

export async function fetchDocumentDateEvents(documentId: string): Promise<RegulatoryDateEvent[]> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/documents/${encodeURIComponent(documentId)}/dates`);
  if (!res.ok) throw new Error('Failed to fetch document date events');
  return res.json();
}

export async function extractDocumentDates(documentId: string): Promise<RegulatoryDateEvent[]> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/documents/${encodeURIComponent(documentId)}/extract-dates`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to extract dates');
  return res.json();
}

export async function fetchRegulatoryCalendar(
  startDate?: string,
  endDate?: string,
  eventType?: string
): Promise<RegulatoryDateEvent[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (startDate) query.append('start_date', startDate);
  if (endDate) query.append('end_date', endDate);
  if (eventType) query.append('event_type', eventType);
  const res = await fetch(`${baseUrl}/regulatory-events/calendar?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch regulatory calendar');
  return res.json();
}

export async function fetchUpcomingEvents(
  days: number = 30,
  asOf?: string,
  eventType?: string
): Promise<RegulatoryDateEvent[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams({ days: days.toString() });
  if (asOf) query.append('as_of', asOf);
  if (eventType) query.append('event_type', eventType);
  const res = await fetch(`${baseUrl}/regulatory-events/upcoming?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch upcoming regulatory events');
  return res.json();
}

// =============================================================================
// PHASE 65: REGULATORY ALERT & DEADLINE INTELLIGENCE (65.13, 65.14)
// =============================================================================

export async function fetchAlerts(params?: {
  severity?: string;
  alert_type?: string;
  status?: string;
  document_id?: string;
  limit?: number;
}): Promise<RegulatoryAlert[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (params?.severity) query.append('severity', params.severity);
  if (params?.alert_type) query.append('alert_type', params.alert_type);
  if (params?.status) query.append('status', params.status);
  if (params?.document_id) query.append('document_id', params.document_id);
  if (params?.limit) query.append('limit', params.limit.toString());
  const res = await fetch(`${baseUrl}/alerts?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function fetchAlert(alertId: string): Promise<RegulatoryAlert> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/alerts/${encodeURIComponent(alertId)}`);
  if (!res.ok) throw new Error('Failed to fetch alert details');
  return res.json();
}

export async function markAlertRead(alertId: string): Promise<RegulatoryAlert> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/alerts/${encodeURIComponent(alertId)}/read`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to mark alert as read');
  return res.json();
}

export async function dismissAlert(alertId: string): Promise<RegulatoryAlert> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/alerts/${encodeURIComponent(alertId)}/dismiss`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to dismiss alert');
  return res.json();
}

export async function fetchDeadlines(params?: {
  document_id?: string;
  obligation_id?: string;
  status?: string;
  limit?: number;
}): Promise<RegulatoryDeadline[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (params?.document_id) query.append('document_id', params.document_id);
  if (params?.obligation_id) query.append('obligation_id', params.obligation_id);
  if (params?.status) query.append('status', params.status);
  if (params?.limit) query.append('limit', params.limit.toString());
  const res = await fetch(`${baseUrl}/deadlines?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch deadlines');
  return res.json();
}

export async function fetchWatchlists(userId?: string): Promise<Watchlist[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (userId) query.append('user_id', userId);
  const res = await fetch(`${baseUrl}/watchlists?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch watchlists');
  return res.json();
}

export async function saveWatchlist(payload: Partial<Watchlist>): Promise<Watchlist> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/watchlists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to save watchlist');
  return res.json();
}

export async function triggerAlertEvaluation(asOf?: string): Promise<Record<string, any>> {
  const baseUrl = apiClient.getBaseUrl();
  const url = asOf
    ? `${baseUrl}/jobs/run-alert-evaluation?as_of=${encodeURIComponent(asOf)}`
    : `${baseUrl}/jobs/run-alert-evaluation`;
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to trigger alert evaluation');
  return res.json();
}

// ==========================================
// Multi-Regulator Connectors API (Phases 66–69)
// ==========================================

export async function fetchConnectors(): Promise<AuthorityMetadata[]> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/api/connectors`);
  if (!res.ok) throw new Error('Failed to fetch regulatory connectors');
  return res.json();
}

export async function fetchConnectorSources(authority?: string): Promise<RegulatorySourceInfo[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (authority && authority !== 'All') query.append('authority', authority);
  const res = await fetch(`${baseUrl}/api/connectors/sources?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch connector sources');
  return res.json();
}

export async function fetchConnectorHealth(): Promise<ConnectorHealth[]> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/api/connectors/health`);
  if (!res.ok) throw new Error('Failed to fetch connector health');
  return res.json();
}

export async function fetchConnectorRuns(authority?: string, limit: number = 20): Promise<ConnectorRun[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (authority && authority !== 'All') query.append('authority', authority);
  query.append('limit', limit.toString());
  const res = await fetch(`${baseUrl}/api/connectors/runs?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch connector runs');
  return res.json();
}

export async function triggerConnectorRun(
  authority: string,
  limit: number = 10,
  dryRun: boolean = false,
  force: boolean = false
): Promise<{ message: string; run_id: string; status: string }> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/api/connectors/${encodeURIComponent(authority)}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ limit, dry_run: dryRun, force }),
  });
  if (!res.ok) throw new Error(`Failed to trigger connector run for ${authority}`);
  return res.json();
}

// ==========================================
// Phases 73 & 74: Overlaps & Conflicts API
// ==========================================

export async function fetchRegulatoryOverlaps(params?: {
  authority?: string;
  relationship_type?: string;
  topic?: string;
  status?: string;
  confidence?: string;
  requirement_id?: string;
  limit?: number;
}): Promise<RegulatoryOverlap[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (params?.authority && params.authority !== 'All') query.append('authority', params.authority);
  if (params?.relationship_type) query.append('relationship_type', params.relationship_type);
  if (params?.topic) query.append('topic', params.topic);
  if (params?.status) query.append('status', params.status);
  if (params?.confidence) query.append('confidence', params.confidence);
  if (params?.requirement_id) query.append('requirement_id', params.requirement_id);
  if (params?.limit) query.append('limit', params.limit.toString());

  const res = await fetch(`${baseUrl}/api/regulatory-overlaps?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch regulatory overlaps');
  return res.json();
}

export async function fetchRegulatoryOverlapDetail(id: string): Promise<RegulatoryOverlap> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/api/regulatory-overlaps/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to fetch overlap detail for ${id}`);
  return res.json();
}

export async function fetchRegulatoryConflicts(params?: {
  authority?: string;
  conflict_type?: string;
  severity?: string;
  confidence?: string;
  resolution_status?: string;
  requirement_id?: string;
  limit?: number;
}): Promise<RegulatoryConflict[]> {
  const baseUrl = apiClient.getBaseUrl();
  const query = new URLSearchParams();
  if (params?.authority && params.authority !== 'All') query.append('authority', params.authority);
  if (params?.conflict_type) query.append('conflict_type', params.conflict_type);
  if (params?.severity) query.append('severity', params.severity);
  if (params?.confidence) query.append('confidence', params.confidence);
  if (params?.resolution_status) query.append('resolution_status', params.resolution_status);
  if (params?.requirement_id) query.append('requirement_id', params.requirement_id);
  if (params?.limit) query.append('limit', params.limit.toString());

  const res = await fetch(`${baseUrl}/api/regulatory-conflicts?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch regulatory conflicts');
  return res.json();
}

export async function fetchRegulatoryConflictDetail(id: string): Promise<RegulatoryConflict> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/api/regulatory-conflicts/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to fetch conflict detail for ${id}`);
  return res.json();
}

export async function updateRegulatoryConflictStatus(
  id: string,
  newStatus: string,
  reviewerId: string = 'compliance_officer',
  notes?: string
): Promise<RegulatoryConflict> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/api/regulatory-conflicts/${encodeURIComponent(id)}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_status: newStatus, reviewer_id: reviewerId, notes }),
  });
  if (!res.ok) throw new Error(`Failed to update conflict status for ${id}`);
  return res.json();
}

export async function triggerOverlapAnalysis(requirementId?: string): Promise<any> {
  const baseUrl = apiClient.getBaseUrl();
  const res = await fetch(`${baseUrl}/api/regulatory-overlaps/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirement_id: requirementId, use_llm: false, max_candidates: 15 }),
  });
  if (!res.ok) throw new Error('Failed to trigger overlap analysis');
  return res.json();
}

