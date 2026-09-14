import React, { useEffect, useState } from 'react';
import { X, RefreshCw } from 'lucide-react';
import { ChecklistItem, TraceabilityNode } from '../../types/api';
import { fetchItemTraceability } from '../../api/compliance';
import { Badge } from '../common/Badge';

interface EvidenceDrawerProps {
  checklistId: string;
  item: ChecklistItem | null;
  onClose: () => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  checklistId,
  item,
  onClose,
}) => {
  const [traceNode, setTraceNode] = useState<TraceabilityNode | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (checklistId && item) {
      setIsLoading(true);
      fetchItemTraceability(checklistId, item.item_id)
        .then((data) => setTraceNode(data))
        .catch((err) => console.error('Trace error:', err))
        .finally(() => setIsLoading(false));
    } else {
      setTraceNode(null);
    }
  }, [checklistId, item]);

  if (!item) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        zIndex: 50,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '560px',
          height: '100%',
          backgroundColor: '#ffffff',
          boxShadow: '-4px 0 20px rgba(0, 0, 0, 0.15)',
          overflowY: 'auto',
          padding: '1.75rem',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem' }}>
          <div>
            <div style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>
              BIDIRECTIONAL TRACEABILITY PROVENANCE
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f172a', margin: '2px 0 0 0' }}>
              Evidence & Audit Trail
            </h3>
          </div>
          <button onClick={onClose} className="btn btn-secondary btn-sm" style={{ padding: '6px' }}>
            <X size={18} />
          </button>
        </div>

        {/* Item Overview */}
        <div style={{ backgroundColor: '#f8fafc', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '1.25rem', border: '1px solid #e2e8f0' }}>
          <div style={{ fontSize: '0.76rem', color: '#64748b', fontWeight: 700 }}>CONTROL QUESTION</div>
          <div style={{ fontWeight: 700, color: '#1e293b', fontSize: '0.95rem', marginTop: '2px' }}>
            {item.control_question}
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
            <Badge variant="blue">Status: {item.status}</Badge>
            {item.obligated_party && <Badge variant="gray">{item.obligated_party}</Badge>}
            {item.deadline && <Badge variant="amber">{item.deadline}</Badge>}
          </div>
        </div>

        {/* Traceability Flow Diagram */}
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.5rem' }}>
            Traceability Chain:
          </div>

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '1.5rem', color: '#64748b' }}>
              <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto 0.5rem auto', color: '#2563eb' }} />
              Tracing regulatory provenance...
            </div>
          ) : (

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {/* 1. Checklist Item */}
            <div style={{ padding: '0.75rem', backgroundColor: '#eff6ff', borderRadius: 'var(--radius-sm)', border: '1px solid #bfdbfe' }}>
              <div style={{ fontSize: '0.72rem', color: '#2563eb', fontWeight: 700 }}>1. ACTIONABLE CONTROL ITEM</div>
              <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{item.compliance_action}</div>
            </div>

            <div style={{ textAlign: 'center', color: '#94a3b8' }}>↓</div>

            {/* 2. Regulatory Obligation */}
            <div style={{ padding: '0.75rem', backgroundColor: '#f0fdf4', borderRadius: 'var(--radius-sm)', border: '1px solid #bbf7d0' }}>
              <div style={{ fontSize: '0.72rem', color: '#16a34a', fontWeight: 700 }}>2. REGULATORY OBLIGATION</div>
              <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                {traceNode?.obligation_action || item.compliance_action}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#4b5563', marginTop: '2px' }}>
                Obligation ID: <code>{item.obligation_id}</code>
              </div>
            </div>

            <div style={{ textAlign: 'center', color: '#94a3b8' }}>↓</div>

            {/* 3. Requirement */}
            <div style={{ padding: '0.75rem', backgroundColor: '#fefce8', borderRadius: 'var(--radius-sm)', border: '1px solid #fef08a' }}>
              <div style={{ fontSize: '0.72rem', color: '#ca8a04', fontWeight: 700 }}>3. EXTRACTED REQUIREMENT</div>
              <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                {traceNode?.requirement_text || 'Loading requirement text...'}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#4b5563', marginTop: '2px' }}>
                Requirement ID: <code>{item.requirement_id}</code>
              </div>
            </div>

            <div style={{ textAlign: 'center', color: '#94a3b8' }}>↓</div>

            {/* 4. Verbatim Source Evidence */}
            <div style={{ padding: '0.85rem', backgroundColor: '#fdf4ff', borderRadius: 'var(--radius-sm)', border: '1px solid #f0abfc' }}>
              <div style={{ fontSize: '0.72rem', color: '#c026d3', fontWeight: 700 }}>4. OFFICIAL SOURCE EVIDENCE</div>
              <p style={{ fontStyle: 'italic', color: '#701a75', fontSize: '0.86rem', margin: '4px 0 0 0', lineHeight: 1.4 }}>
                "{traceNode?.source_evidence || item.source_reference?.evidence_snippet || 'Evidence citation attached.'}"
              </p>
              <div style={{ fontSize: '0.76rem', color: '#a21caf', marginTop: '6px' }}>
                Document: <code>{item.document_id}</code>
                {traceNode?.section_heading && ` | ${traceNode.section_heading}`}
                {traceNode?.page_number && ` | Page ${traceNode.page_number}`}
              </div>
            </div>
          </div>
          )}
        </div>

        {/* Required Evidence Proof */}
        {item.evidence_required && item.evidence_required.length > 0 && (
          <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.4rem' }}>
              📋 Evidentiary Artifacts Required for Audit:
            </div>
            <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.82rem', color: '#334155' }}>
              {item.evidence_required.map((ev, i) => (
                <li key={i} style={{ marginBottom: '2px' }}>
                  {ev}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
