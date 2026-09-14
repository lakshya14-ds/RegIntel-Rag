import React, { useState } from 'react';
import { Eye } from 'lucide-react';
import { RegulatoryRequirement } from '../../types/api';
import { Badge } from '../common/Badge';

interface RequirementCardProps {
  requirement: RegulatoryRequirement;
}

export const RequirementCard: React.FC<RequirementCardProps> = ({ requirement }) => {
  const [showEvidence, setShowEvidence] = useState(false);

  const confVariant =
    requirement.confidence === 'HIGH'
      ? 'green'
      : requirement.confidence === 'MEDIUM'
      ? 'amber'
      : 'gray';

  return (
    <div className="card" style={{ padding: '1.25rem', marginBottom: '1rem', borderLeft: '4px solid #3b82f6' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <Badge variant="blue">{requirement.requirement_type}</Badge>
          <Badge variant={confVariant}>Confidence: {requirement.confidence}</Badge>
          {requirement.authority && <Badge variant="gray">{requirement.authority}</Badge>}
          {requirement.frequency && <Badge variant="purple">{requirement.frequency}</Badge>}
        </div>
        <button
          onClick={() => setShowEvidence(!showEvidence)}
          className="btn btn-secondary btn-sm"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem' }}
        >
          <Eye size={13} /> {showEvidence ? 'Hide Evidence' : 'View Evidence'}
        </button>
      </div>

      <p style={{ fontWeight: 600, fontSize: '0.98rem', color: '#1e293b', marginBottom: '0.75rem', lineHeight: 1.4 }}>
        {requirement.requirement_text}
      </p>

      {/* Structured Metadata Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '0.5rem',
          backgroundColor: '#f8fafc',
          padding: '0.75rem',
          borderRadius: 'var(--radius-sm)',
          fontSize: '0.82rem',
          marginBottom: '0.5rem',
        }}
      >
        {requirement.subject && (
          <div>
            <span style={{ color: '#64748b' }}>👤 Subject: </span>
            <strong>{requirement.subject}</strong>
          </div>
        )}
        {requirement.action && (
          <div>
            <span style={{ color: '#64748b' }}>⚡ Action: </span>
            <strong>{requirement.action}</strong>
          </div>
        )}
        {requirement.deadline && (
          <div>
            <span style={{ color: '#64748b' }}>⏳ Deadline: </span>
            <strong>{requirement.deadline}</strong>
          </div>
        )}
        {requirement.applicability && (
          <div>
            <span style={{ color: '#64748b' }}>🎯 Scope: </span>
            <strong>{requirement.applicability}</strong>
          </div>
        )}
      </div>

      {/* Threshold tags */}
      {requirement.thresholds && requirement.thresholds.length > 0 && (
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.4rem' }}>
          {requirement.thresholds.map((th, i) => (
            <span
              key={i}
              style={{
                backgroundColor: '#eff6ff',
                color: '#1d4ed8',
                border: '1px solid #bfdbfe',
                padding: '2px 8px',
                borderRadius: '12px',
                fontSize: '0.75rem',
                fontWeight: 600,
              }}
            >
              {th.parameter_type.toUpperCase()}: {th.raw_value}
            </span>
          ))}
        </div>
      )}

      {/* Evidence Drawer/Accordion */}
      {showEvidence && (
        <div
          style={{
            marginTop: '0.75rem',
            padding: '0.85rem',
            backgroundColor: '#fffbeb',
            border: '1px solid #fef3c7',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.82rem',
          }}
        >
          <div style={{ fontWeight: 700, color: '#92400e', marginBottom: '0.3rem' }}>
            📜 Verbatim Regulatory Evidence:
          </div>
          <p style={{ fontStyle: 'italic', color: '#78350f', margin: 0 }}>
            "{requirement.source_evidence}"
          </p>
          {requirement.source_locator && (
            <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', color: '#b45309' }}>
              {requirement.source_locator.heading && `Section: ${requirement.source_locator.heading}`}
              {requirement.source_locator.page_number && ` | Page: ${requirement.source_locator.page_number}`}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
