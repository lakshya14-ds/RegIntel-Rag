import React, { useState } from 'react';
import { ChevronDown, ChevronUp, BookOpen } from 'lucide-react';
import { SectionChangeResponse } from '../../types/api';
import { Badge } from '../common/Badge';
import { DiffBox } from './DiffBox';

interface SectionDeltaCardProps {
  change: SectionChangeResponse;
}

export const SectionDeltaCard: React.FC<SectionDeltaCardProps> = ({ change }) => {
  const [isExpanded, setIsExpanded] = useState(change.change_type === 'MODIFIED');

  const ctype = (change.change_type || 'MODIFIED').toUpperCase();
  const variantMap: Record<string, 'green' | 'red' | 'amber' | 'gray'> = {
    ADDED: 'green',
    REMOVED: 'red',
    MODIFIED: 'amber',
    UNCHANGED: 'gray',
  };
  const badgeVariant = variantMap[ctype] || 'gray';

  return (
    <div
      style={{
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        backgroundColor: '#ffffff',
        marginBottom: '0.85rem',
        overflow: 'hidden',
      }}
    >
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          padding: '0.85rem 1rem',
          backgroundColor: isExpanded ? '#f8fafc' : '#ffffff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isExpanded ? '1px solid var(--border-subtle)' : 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
          <Badge variant={badgeVariant}>{ctype}</Badge>
          <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
            {change.section ? `Sec ${change.section}: ` : ''}
            {change.heading || 'Untitled Section'}
          </span>
          {change.substantive_change && (
            <Badge variant="purple">Substantive</Badge>
          )}
          {change.modification_category && (
            <Badge variant="gray">{change.modification_category}</Badge>
          )}
        </div>
        <div>{isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}</div>
      </div>

      {isExpanded && (
        <div style={{ padding: '1rem', fontSize: '0.9rem' }}>
          {change.summary && (
            <div style={{ marginBottom: '0.75rem' }}>
              <strong style={{ color: 'var(--text-secondary)' }}>WHAT CHANGED: </strong>
              <span>{change.summary}</span>
            </div>
          )}

          {(change.impact || change.compliance_impact) && (
            <div
              style={{
                marginBottom: '0.75rem',
                padding: '0.6rem 0.85rem',
                backgroundColor: '#eff6ff',
                borderLeft: '3px solid var(--primary-600)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.86rem',
                color: '#1e3a8a',
              }}
            >
              <strong>COMPLIANCE IMPACT: </strong>
              <span>{change.impact || change.compliance_impact}</span>
            </div>
          )}

          {/* Diff Box */}
          <DiffBox
            previousText={change.previous_text}
            currentText={change.current_text}
            changeType={ctype}
          />

          {/* Evidence Mapping */}
          {(change.old_source || change.new_source) && (
            <div style={{ marginTop: '0.85rem', paddingTop: '0.65rem', borderTop: '1px solid var(--border-subtle)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '3px' }}>
                <BookOpen size={13} /> Evidence Sources:
              </div>
              {change.old_source && (
                <div>• Older Source: <code>{change.old_source.document_id.slice(0, 12)}...</code> | Heading: {change.old_source.heading}</div>
              )}
              {change.new_source && (
                <div>• Newer Source: <code>{change.new_source.document_id.slice(0, 12)}...</code> | Heading: {change.new_source.heading}</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
