import React, { useState } from 'react';
import { User, Activity, Clock, ShieldCheck, Eye } from 'lucide-react';
import { RegulatoryObligation } from '../../types/api';
import { Badge } from '../common/Badge';

interface ObligationCardProps {
  obligation: RegulatoryObligation;
}

export const ObligationCard: React.FC<ObligationCardProps> = ({ obligation }) => {
  const [showEvidence, setShowEvidence] = useState(false);

  const typeVariant =
    obligation.obligation_type === 'MANDATORY' || obligation.obligation_type === 'CONDITIONAL_MANDATORY'
      ? 'blue'
      : obligation.obligation_type === 'PROHIBITION'
      ? 'red'
      : 'amber';

  const statusVariant =
    obligation.status === 'ACTIVE'
      ? 'green'
      : obligation.status === 'SUPERSEDED'
      ? 'amber'
      : 'gray';

  return (
    <div className="card" style={{ padding: '1.25rem', marginBottom: '1rem', borderLeft: `4px solid ${obligation.obligation_type === 'PROHIBITION' ? '#ef4444' : '#2563eb'}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          <Badge variant={typeVariant}>{obligation.obligation_type}</Badge>
          <Badge variant={statusVariant}>{obligation.status}</Badge>
          <Badge variant="gray">Confidence: {obligation.confidence}</Badge>
        </div>
        <button
          onClick={() => setShowEvidence(!showEvidence)}
          className="btn btn-secondary btn-sm"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem' }}
        >
          <Eye size={13} /> {showEvidence ? 'Hide Source' : 'View Source'}
        </button>
      </div>

      {/* WHO / WHAT / WHEN / EVIDENCE Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '0.75rem',
          backgroundColor: '#f8fafc',
          padding: '0.85rem',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.84rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b', fontWeight: 600 }}>
            <User size={14} /> WHO (Obligated Party)
          </div>
          <div style={{ fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
            {obligation.obligated_party || 'Regulated Entity'}
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b', fontWeight: 600 }}>
            <Activity size={14} /> WHAT (Required Action)
          </div>
          <div style={{ fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
            {obligation.obligation_action} {obligation.obligation_object && `(${obligation.obligation_object})`}
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b', fontWeight: 600 }}>
            <Clock size={14} /> WHEN (Timeline)
          </div>
          <div style={{ fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
            {obligation.deadline || obligation.frequency || 'Periodic / Continuous'}
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#64748b', fontWeight: 600 }}>
            <ShieldCheck size={14} /> WHAT EVIDENCE
          </div>
          <div style={{ fontWeight: 600, color: '#15803d', marginTop: '2px' }}>
            {obligation.required_evidence && obligation.required_evidence.length > 0
              ? obligation.required_evidence.join(', ')
              : 'Audit trail / Compliance record'}
          </div>
        </div>
      </div>

      {/* Conditions or Provisos */}
      {obligation.conditions && obligation.conditions.length > 0 && (
        <div style={{ marginTop: '0.6rem', fontSize: '0.8rem', color: '#475569' }}>
          <strong>Conditions: </strong>
          {obligation.conditions.join('; ')}
        </div>
      )}

      {/* Source Evidence Accordion */}
      {showEvidence && (
        <div
          style={{
            marginTop: '0.75rem',
            padding: '0.75rem',
            backgroundColor: '#eff6ff',
            border: '1px solid #dbeafe',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.82rem',
          }}
        >
          <div style={{ fontWeight: 700, color: '#1e40af', marginBottom: '0.25rem' }}>
            Source Provision Evidence:
          </div>
          <p style={{ fontStyle: 'italic', color: '#1e3a8a', margin: 0 }}>
            "{obligation.source_evidence}"
          </p>
          {obligation.source_locator && (
            <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: '#3b82f6' }}>
              {obligation.source_locator.heading && `Section: ${obligation.source_locator.heading}`}
              {obligation.source_locator.page_number && ` | Page: ${obligation.source_locator.page_number}`}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
