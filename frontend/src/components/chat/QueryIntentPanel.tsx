import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { QueryIntentResponse } from '../../types/api';
import { Badge } from '../common/Badge';

interface QueryIntentPanelProps {
  intent?: QueryIntentResponse | null;
}

export const QueryIntentPanel: React.FC<QueryIntentPanelProps> = ({ intent }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!intent) return null;

  return (
    <div
      style={{
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        backgroundColor: '#f8fafc',
        marginBottom: '1rem',
        overflow: 'hidden',
      }}
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.65rem 1rem',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--text-secondary)',
          textAlign: 'left',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Sparkles size={15} color="var(--primary-600)" />
          How RegIntel interpreted your question
        </span>
        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {isExpanded && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderTop: '1px solid var(--border-subtle)',
            backgroundColor: '#ffffff',
            fontSize: '0.85rem',
          }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Badge variant="blue">Authority: {intent.source || 'SEBI'}</Badge>
            <Badge variant="purple">Category: {intent.category || 'General'}</Badge>
            <Badge variant="gray">Query Type: {intent.query_type}</Badge>
            <Badge variant="gray">Time Intent: {intent.time_intent}</Badge>
            {intent.is_comparison && <Badge variant="amber">Comparison Intent</Badge>}
          </div>

          {(intent.circular_number || intent.document_type) && (
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.4rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
              {intent.circular_number && (
                <div>
                  <strong>Target Circular:</strong> <code>{intent.circular_number}</code>
                </div>
              )}
              {intent.document_type && (
                <div>
                  <strong>Document Type:</strong> <code>{intent.document_type}</code>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
