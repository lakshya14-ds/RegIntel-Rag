import React, { useState } from 'react';
import { ChevronDown, ChevronUp, BookOpen, MoveRight, Hash } from 'lucide-react';
import { SectionChangeResponse } from '../../types/api';
import { Badge } from '../common/Badge';
import { DiffBox } from './DiffBox';

interface SectionDeltaCardProps {
  change: SectionChangeResponse;
}

export const SectionDeltaCard: React.FC<SectionDeltaCardProps> = ({ change }) => {
  const [isExpanded, setIsExpanded] = useState(change.change_type === 'MODIFIED' || !!change.is_moved);

  const ctype = (change.is_moved ? 'MOVED' : change.change_type || 'MODIFIED').toUpperCase();
  const variantMap: Record<string, 'green' | 'red' | 'amber' | 'blue' | 'gray'> = {
    ADDED: 'green',
    REMOVED: 'red',
    MODIFIED: 'amber',
    MOVED: 'blue',
    UNCHANGED: 'gray',
  };
  const badgeVariant = variantMap[ctype] || 'gray';
  const numChanges = change.numerical_changes || [];

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
          {change.is_moved && change.old_section_number && (
            <Badge variant="blue">
              <MoveRight size={12} style={{ display: 'inline', marginRight: '3px' }} />
              Moved from Sec {change.old_section_number}
            </Badge>
          )}
          {change.substantive_change && (
            <Badge variant="purple">Substantive</Badge>
          )}
          {numChanges.length > 0 && (
            <Badge variant="amber">
              <Hash size={12} style={{ display: 'inline', marginRight: '2px' }} />
              {numChanges.length} Numerical Shift{numChanges.length > 1 ? 's' : ''}
            </Badge>
          )}
          {change.modification_category && (
            <Badge variant="gray">{change.modification_category}</Badge>
          )}
        </div>
        <div>{isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}</div>
      </div>

      {isExpanded && (
        <div style={{ padding: '1rem', fontSize: '0.9rem' }}>
          {/* Numerical & Threshold Shifts Highlight (60.11) */}
          {numChanges.length > 0 && (
            <div
              style={{
                marginBottom: '0.85rem',
                padding: '0.6rem 0.85rem',
                backgroundColor: '#fffbeb',
                borderLeft: '3px solid #f59e0b',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem',
              }}
            >
              <strong style={{ color: '#b45309' }}>⚡ NUMERICAL / THRESHOLD CHANGES:</strong>
              <ul style={{ margin: '0.35rem 0 0 1.2rem', padding: 0 }}>
                {numChanges.map((nc, idx) => (
                  <li key={idx}>
                    <strong>{nc.parameter}</strong>: <code>{nc.previous_value}</code> → <strong><code>{nc.new_value}</code></strong>
                  </li>
                ))}
              </ul>
            </div>
          )}

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

          {/* Side-by-Side Diff Box (60.17) */}
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
