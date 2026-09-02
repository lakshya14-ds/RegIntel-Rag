import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FileText, ExternalLink, GitBranch, Scale, RefreshCw } from 'lucide-react';
import { useLatestDocuments } from '../hooks/useDocuments';
import { formatDate } from '../utils/dates';
import { Badge } from '../components/common/Badge';

export const Latest: React.FC = () => {
  const [sourceFilter, setSourceFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [docTypeFilter, setDocTypeFilter] = useState('All');
  const [limit, setLimit] = useState(20);

  const { data: docs, isLoading, refetch } = useLatestDocuments({
    source: sourceFilter !== 'All' ? sourceFilter : undefined,
    category: categoryFilter !== 'All' ? categoryFilter : undefined,
    limit,
  });

  const docsList = docs || [];
  const filteredDocs = docTypeFilter === 'All'
    ? docsList
    : docsList.filter((d) => (d.document_type || '').trim().toLowerCase() === docTypeFilter.trim().toLowerCase());

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">
          <span>📜</span> Regulatory Documents Catalog
        </h1>
        <p className="page-subtitle">
          Browse authoritative SEBI circulars, master directions, and regulatory gazettes indexed in the local intelligence corpus.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="grid-4">
          <div>
            <label className="form-label">Authority</label>
            <select
              className="form-select"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              <option value="All">All Authorities</option>
              <option value="SEBI">SEBI</option>
            </select>
          </div>

          <div>
            <label className="form-label">Category</label>
            <select
              className="form-select"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="All">All Categories</option>
              <option value="Investment Adviser">Investment Adviser</option>
              <option value="Mutual Funds">Mutual Funds</option>
              <option value="Stock Brokers">Stock Brokers</option>
              <option value="Research Analysts">Research Analysts</option>
              <option value="Depositories">Depositories</option>
            </select>
          </div>

          <div>
            <label className="form-label">Document Type</label>
            <select
              className="form-select"
              value={docTypeFilter}
              onChange={(e) => setDocTypeFilter(e.target.value)}
            >
              <option value="All">All Types</option>
              <option value="Circular">Circular</option>
              <option value="Master Circular">Master Circular</option>
              <option value="Notification">Notification</option>
              <option value="Order">Order</option>
              <option value="Advisory">Advisory</option>
            </select>
          </div>

          <div>
            <label className="form-label">Display Limit: {limit}</label>
            <input
              type="range"
              min={5}
              max={50}
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value, 10))}
              style={{ width: '100%', marginTop: '8px' }}
            />
          </div>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem' }}>
          <RefreshCw size={28} className="animate-spin" style={{ color: 'var(--primary-600)', marginBottom: '0.75rem' }} />
          <div>Loading regulatory catalog...</div>
        </div>
      )}

      {/* Content */}
      {!isLoading && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1.15rem' }}>
              Showing {filteredDocs.length} Regulatory Documents
            </h2>
            <button className="btn btn-secondary btn-sm" onClick={() => refetch()}>
              <RefreshCw size={14} /> Refresh Catalog
            </button>
          </div>

          {filteredDocs.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
              No regulatory documents found matching the specified filters.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {filteredDocs.map((doc) => {
                const status = (doc.status || 'unknown').toLowerCase();
                const badgeVariant = status === 'current' ? 'green' : status === 'historical' ? 'amber' : 'gray';

                return (
                  <div key={doc.document_id} className="card" style={{ marginBottom: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
                          <Badge variant={badgeVariant}>{doc.status?.toUpperCase() || 'UNKNOWN'}</Badge>
                          <Badge variant="blue">{doc.source || 'SEBI'}</Badge>
                          <Badge variant="gray">{doc.category || 'General'}</Badge>
                          <Badge variant="purple">{doc.document_type || 'Circular'}</Badge>
                        </div>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e3a8a', marginBottom: '0.25rem' }}>
                          {doc.title || 'Untitled Regulatory Circular'}
                        </h3>
                      </div>
                    </div>

                    <div className="grid-3" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                      <div>📅 <strong>Published:</strong> <code>{formatDate(doc.published_date)}</code></div>
                      <div>⚡ <strong>Effective:</strong> <code>{formatDate(doc.effective_date)}</code></div>
                      <div>🔢 <strong>Circular No:</strong> <code>{doc.circular_number || 'N/A'}</code></div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Doc ID: <code>{doc.document_id}</code>
                      </span>

                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <Link to={`/document/${doc.document_id}`} className="btn btn-outline btn-sm">
                          <FileText size={14} /> Details
                        </Link>
                        <Link to={`/document/${doc.document_id}/timeline`} className="btn btn-secondary btn-sm">
                          <GitBranch size={14} /> Timeline
                        </Link>
                        <Link to={`/compare?docA=${doc.document_id}`} className="btn btn-primary btn-sm">
                          <Scale size={14} /> Compare
                        </Link>
                        {doc.url && (
                          <a
                            href={doc.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-secondary btn-sm"
                            title="Open Official SEBI Circular"
                          >
                            <ExternalLink size={14} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
