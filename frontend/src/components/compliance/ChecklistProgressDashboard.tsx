import React from 'react';
import { Download, RefreshCw, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';
import { ComplianceChecklist } from '../../types/api';

interface ChecklistProgressDashboardProps {
  checklist: ComplianceChecklist;
  onExportMarkdown: () => void;
  onExportJson: () => void;
  onRegenerate: () => void;
  isRegenerating?: boolean;
}

export const ChecklistProgressDashboard: React.FC<ChecklistProgressDashboardProps> = ({
  checklist,
  onExportMarkdown,
  onExportJson,
  onRegenerate,
  isRegenerating = false,
}) => {
  const counts = checklist.summary_counts || {};
  const total = checklist.items.length;
  const rate = checklist.completion_rate || 0.0;

  return (
    <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem', backgroundColor: '#ffffff' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#1e3a8a', margin: 0 }}>
            {checklist.title}
          </h2>
          <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '4px' }}>
            Authority: <strong>{checklist.authority}</strong> | Scope: {checklist.regulatory_scope} | Items: {total}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="btn btn-secondary btn-sm"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            <RefreshCw size={14} className={isRegenerating ? 'animate-spin' : ''} />
            {isRegenerating ? 'Re-syncing...' : 'Re-sync with Regulations'}
          </button>
          <button
            onClick={onExportMarkdown}
            className="btn btn-outline btn-sm"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            <Download size={14} /> Export Markdown
          </button>
          <button
            onClick={onExportJson}
            className="btn btn-outline btn-sm"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
          >
            <Download size={14} /> Export JSON
          </button>
        </div>
      </div>

      {/* Completion Progress Bar */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px' }}>
          <span>Checklist Review Completion</span>
          <span style={{ color: '#2563eb' }}>{rate}% Reviewed</span>
        </div>
        <div style={{ width: '100%', height: '10px', backgroundColor: '#e2e8f0', borderRadius: '5px', overflow: 'hidden' }}>
          <div
            style={{
              width: `${rate}%`,
              height: '100%',
              backgroundColor: rate >= 100 ? '#10b981' : '#3b82f6',
              transition: 'width 0.4s ease',
            }}
          />
        </div>
      </div>

      {/* Metrics Breakdown */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '0.75rem',
          textAlign: 'center',
        }}
      >
        <div style={{ padding: '0.6rem', backgroundColor: '#ecfdf5', borderRadius: 'var(--radius-sm)', border: '1px solid #a7f3d0' }}>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px', color: '#047857', fontWeight: 700, fontSize: '0.78rem' }}>
            <CheckCircle size={13} /> Compliant
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#065f46' }}>
            {counts['COMPLIANT'] || 0}
          </div>
        </div>

        <div style={{ padding: '0.6rem', backgroundColor: '#fef2f2', borderRadius: 'var(--radius-sm)', border: '1px solid #fecaca' }}>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px', color: '#b91c1c', fontWeight: 700, fontSize: '0.78rem' }}>
            <XCircle size={13} /> Non-Compliant
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#991b1b' }}>
            {counts['NON_COMPLIANT'] || 0}
          </div>
        </div>

        <div style={{ padding: '0.6rem', backgroundColor: '#fffbeb', borderRadius: 'var(--radius-sm)', border: '1px solid #fde68a' }}>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px', color: '#b45309', fontWeight: 700, fontSize: '0.78rem' }}>
            <AlertTriangle size={13} /> Needs Review
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#92400e' }}>
            {counts['NEEDS_REVIEW'] || 0}
          </div>
        </div>

        <div style={{ padding: '0.6rem', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-sm)', border: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '4px', color: '#64748b', fontWeight: 700, fontSize: '0.78rem' }}>
            <Clock size={13} /> Not Reviewed
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#334155' }}>
            {counts['NOT_REVIEWED'] || 0}
          </div>
        </div>
      </div>

      {/* Regulatory Intelligence Notice */}
      <div style={{ marginTop: '1rem', fontSize: '0.76rem', color: '#64748b', backgroundColor: '#f8fafc', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)' }}>
        ⚖️ <strong>Regulatory Intelligence Aid:</strong> This checklist tracks verification progress against source requirements. Completion metrics indicate internal review progress and do not constitute legal certification of regulatory compliance.
      </div>
    </div>
  );
};
