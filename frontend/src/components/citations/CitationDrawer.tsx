import React from 'react';
import { X, ExternalLink, Calendar } from 'lucide-react';
import { SourceCitationResponse } from '../../types/api';
import { formatDate } from '../../utils/dates';
import { formatScore } from '../../utils/formatting';
import { Badge } from '../common/Badge';

interface CitationDrawerProps {
  citation: SourceCitationResponse | null;
  onClose: () => void;
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({ citation, onClose }) => {
  if (!citation) return null;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        right: 0,
        top: 0,
        width: '420px',
        maxWidth: '90vw',
        backgroundColor: '#ffffff',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
        zIndex: 50,
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid var(--border-subtle)',
      }}
      role="dialog"
      aria-label="Evidence Source Details"
    >
      {/* Header */}
      <div
        style={{
          padding: '1.25rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#f8fafc',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="citation-tag" style={{ fontSize: '0.9rem', padding: '0.2rem 0.5rem' }}>
            [{citation.source_id}]
          </span>
          <span style={{ fontWeight: 700, fontSize: '1rem', color: '#1e3a8a' }}>
            Evidence Source Metadata
          </span>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#64748b',
            cursor: 'pointer',
            padding: '4px',
          }}
          aria-label="Close"
        >
          <X size={20} />
        </button>
      </div>

      {/* Content */}
      <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1 }}>
        <div style={{ marginBottom: '1rem' }}>
          <Badge variant="blue">{citation.source || 'SEBI'}</Badge>
          <h3 style={{ fontSize: '1.1rem', marginTop: '0.5rem', marginBottom: '0.25rem' }}>
            {citation.title}
          </h3>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
            <strong>Section:</strong> {citation.section || 'General'}
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '0.75rem',
            padding: '0.85rem',
            backgroundColor: '#f8fafc',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '1.25rem',
            fontSize: '0.85rem',
          }}
        >
          <div>
            <div style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Calendar size={13} /> Published
            </div>
            <div style={{ fontWeight: 600 }}>{formatDate(citation.published_date)}</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Calendar size={13} /> Effective
            </div>
            <div style={{ fontWeight: 600 }}>{formatDate(citation.effective_date)}</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-muted)' }}>Relevance Score</div>
            <div style={{ fontWeight: 600, color: 'var(--primary-700)' }}>{formatScore(citation.score)}</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-muted)' }}>Chunk ID</div>
            <div style={{ fontWeight: 600, fontSize: '0.78rem', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {citation.chunk_id.slice(0, 10)}...
            </div>
          </div>
        </div>

        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
            Document Reference
          </div>
          <code
            style={{
              display: 'block',
              padding: '0.5rem',
              backgroundColor: '#f1f5f9',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              wordBreak: 'break-all',
            }}
          >
            {citation.document_id}
          </code>
        </div>

        {citation.url ? (
          <a
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary"
            style={{ width: '100%', textDecoration: 'none' }}
          >
            <ExternalLink size={16} />
            Open Official {citation.source || 'SEBI'} Circular
          </a>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>
            Official source URL not available for this indexed item.
          </div>
        )}
      </div>
    </div>
  );
};
