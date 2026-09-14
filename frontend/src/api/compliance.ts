/**
 * Compliance and Requirement Intelligence API Client (Phases 61, 62, 63).
 */

import {
  RegulatoryRequirement,
  RegulatoryObligation,
  ComplianceChecklist,
  TraceabilityNode,
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
