import React from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ExternalLink, GitBranch, Scale, ArrowLeft, RefreshCw, AlertCircle } from 'lucide-react';
import { useDocument } from '../hooks/useDocuments';
import { formatDate } from '../utils/dates';
import { Badge } from '../components/common/Badge';

export const Document: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  const { data: doc, isLoading, error } = useDocument(documentId);

  if (isLoading) {
    return (
      <div className="page-container" style={{ textAlign: 'center', padding: '4rem 1rem' }}>
        <RefreshCw size={32} className="animate-spin" style={{ color: 'var(--primary-600)', marginBottom: '1rem' }} />
        <h3>Loading document metadata...</h3>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="page-container">
        <div className="alert alert-danger">
          <AlertCircle size={20} />
          <div>
            <strong>Document Not Found:</strong> {error?.message || `Could not find document with ID "${documentId}"`}
          </div>
        </div>
        <button className="btn btn-secondary" onClick={() => navigate(-1)}>
          <ArrowLeft size={16} /> Go Back
        </button>
      </div>
    );
  }

  const status = (doc.status || 'unknown').toLowerCase();
  const badgeVariant = status === 'current' ? 'green' : status === 'historical' ? 'amber' : 'gray';

  return (
    <div className="page-container">
      {/* Top Navigation */}
      <div style={{ marginBottom: '1rem' }}>
        <button
          onClick={() => navigate(-1)}
          className="btn btn-secondary btn-sm"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
        >
          <ArrowLeft size={14} /> Back
        </button>
      </div>

      {/* Main Document Details Card */}
      <div className="card" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
          <Badge variant={badgeVariant}>{doc.status?.toUpperCase() || 'UNKNOWN'}</Badge>
          <Badge variant="blue">{doc.source || 'SEBI'}</Badge>
          <Badge variant="gray">{doc.category || 'General'}</Badge>
          <Badge variant="purple">{doc.document_type || 'Circular'}</Badge>
          <Badge variant="gray">Version {doc.document_version || '1.0'}</Badge>
        </div>

        <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#1e3a8a', marginBottom: '0.75rem', lineHeight: 1.3 }}>
          {doc.title || 'Untitled Regulatory Document'}
        </h1>

        <div className="grid-3" style={{ padding: '1rem', backgroundColor: '#f8fafc', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', marginBottom: '1.5rem', fontSize: '0.88rem' }}>
          <div>
            <div style={{ color: 'var(--text-muted)' }}>📅 Published Date</div>
            <div style={{ fontWeight: 600 }}>{formatDate(doc.published_date)}</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-muted)' }}>⚡ Effective Date</div>
            <div style={{ fontWeight: 600 }}>{formatDate(doc.effective_date)}</div>
          </div>
          <div>
            <div style={{ color: 'var(--text-muted)' }}>🔢 Circular Number</div>
            <div style={{ fontWeight: 600 }}>{doc.circular_number || 'N/A'}</div>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          <Link to={`/document/${doc.document_id}/timeline`} className="btn btn-primary">
            <GitBranch size={16} /> View Version Timeline
          </Link>
          <Link to={`/compare?docA=${doc.document_id}`} className="btn btn-secondary">
            <Scale size={16} /> Compare with Another Document
          </Link>
          {doc.url && (
            <a href={doc.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline">
              <ExternalLink size={16} /> Open Official Source
            </a>
          )}
        </div>

        {/* Technical Metadata */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '1.25rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
            System & Storage Identifiers
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem' }}>
            <div>
              <strong>Document ID:</strong> <code>{doc.document_id}</code>
            </div>
            {doc.content_hash && (
              <div>
                <strong>Content SHA-256 Hash:</strong> <code>{doc.content_hash}</code>
              </div>
            )}
            {doc.supersedes && (
              <div>
                <strong>Predecessor Document ID:</strong> <code>{doc.supersedes}</code>
              </div>
            )}
            {doc.superseded_by && (
              <div>
                <strong>Successor Document ID:</strong> <code>{doc.superseded_by}</code>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
