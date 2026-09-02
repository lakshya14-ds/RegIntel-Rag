import React from 'react';
import { Link } from 'react-router-dom';
import { MessageSquareText, Scale, FileText, Sparkles, Database, GitBranch, ArrowRight } from 'lucide-react';
import { useLatestDocuments } from '../hooks/useDocuments';
import { formatDate } from '../utils/dates';
import { Badge } from '../components/common/Badge';

export const Home: React.FC = () => {
  const { data: latestDocs, isLoading } = useLatestDocuments({ limit: 4 });

  return (
    <div className="page-container">
      {/* Hero Section */}
      <div
        style={{
          background: 'linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%)',
          color: '#ffffff',
          borderRadius: 'var(--radius-lg)',
          padding: '2.5rem 2rem',
          marginBottom: '2rem',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'rgba(255,255,255,0.1)', padding: '4px 12px', borderRadius: '9999px', fontSize: '0.82rem', fontWeight: 600, marginBottom: '1rem' }}>
          <Sparkles size={14} color="#60a5fa" />
          Autonomous Regulatory Intelligence Platform
        </div>
        <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: '#ffffff', marginBottom: '0.75rem', lineHeight: 1.2 }}>
          RegIntel RAG
        </h1>
        <p style={{ fontSize: '1.05rem', color: '#cbd5e1', maxWidth: '780px', marginBottom: '1.75rem', lineHeight: 1.6 }}>
          Retrieve, compare, and explain financial regulations issued by authorities like SEBI using multi-stage hybrid search, local neural cross-encoder reranking, strict citation validation, and automated clause delta detection.
        </p>

        {/* Primary Action Buttons */}
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <Link to="/ask" className="btn btn-primary btn-lg" style={{ backgroundColor: '#2563eb', color: '#ffffff' }}>
            <MessageSquareText size={18} />
            Ask Regulations
          </Link>
          <Link to="/compare" className="btn btn-secondary btn-lg" style={{ backgroundColor: '#ffffff', color: '#0f172a', border: 'none' }}>
            <Scale size={18} />
            Compare Circulars
          </Link>
          <Link to="/latest" className="btn btn-outline btn-lg" style={{ borderColor: 'rgba(255,255,255,0.4)', color: '#ffffff' }}>
            <FileText size={18} />
            Explore Catalog
          </Link>
        </div>
      </div>

      {/* Feature Capabilities Grid */}
      <h2 style={{ fontSize: '1.25rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>
        Core Regulatory Capabilities
      </h2>
      <div className="grid-4" style={{ marginBottom: '2.5rem' }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ color: 'var(--primary-600)', marginBottom: '0.5rem' }}>
            <MessageSquareText size={24} />
          </div>
          <h3 style={{ fontSize: '1.05rem', marginBottom: '0.35rem' }}>Grounded RAG</h3>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
            Grounded Q&A strictly constrained by authoritative regulatory chunks with 100% verified citations.
          </p>
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ color: '#059669', marginBottom: '0.5rem' }}>
            <Database size={24} />
          </div>
          <h3 style={{ fontSize: '1.05rem', marginBottom: '0.35rem' }}>Hybrid Retrieval</h3>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
            Dense Gemini embeddings (768d) combined with BM25 Plus sparse keyword matching via Reciprocal Rank Fusion (RRF).
          </p>
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ color: '#d97706', marginBottom: '0.5rem' }}>
            <Scale size={24} />
          </div>
          <h3 style={{ fontSize: '1.05rem', marginBottom: '0.35rem' }}>Change Detection</h3>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
            4-Tier clause alignment classifying requirements as Added, Modified, Removed, or Unchanged.
          </p>
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ color: '#7e22ce', marginBottom: '0.5rem' }}>
            <GitBranch size={24} />
          </div>
          <h3 style={{ fontSize: '1.05rem', marginBottom: '0.35rem' }}>Version Tracking</h3>
          <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
            Automated temporal lineage graph isolating superseded circulars from currently active mandates.
          </p>
        </div>
      </div>

      {/* Recent Documents Highlight */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.25rem', margin: 0 }}>Recently Indexed Regulations</h2>
        <Link to="/latest" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.9rem', fontWeight: 600 }}>
          View All <ArrowRight size={15} />
        </Link>
      </div>

      {isLoading ? (
        <div className="card skeleton" style={{ height: '120px' }} />
      ) : (
        <div className="grid-2">
          {latestDocs.map((doc) => {
            const status = (doc.status || 'unknown').toLowerCase();
            const badgeVariant = status === 'current' ? 'green' : status === 'historical' ? 'amber' : 'gray';
            return (
              <div key={doc.document_id} className="card" style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.4rem' }}>
                  <Badge variant={badgeVariant}>{doc.status?.toUpperCase() || 'UNKNOWN'}</Badge>
                  <Badge variant="blue">{doc.source || 'SEBI'}</Badge>
                  <Badge variant="gray">{doc.category || 'General'}</Badge>
                </div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  {doc.title || 'Regulatory Document'}
                </h3>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                  📅 Published: <code>{formatDate(doc.published_date)}</code> | Effective: <code>{formatDate(doc.effective_date)}</code>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <Link to={`/document/${doc.document_id}`} className="btn btn-outline btn-sm">
                    View Details
                  </Link>
                  <Link to={`/document/${doc.document_id}/timeline`} className="btn btn-secondary btn-sm">
                    Timeline
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
