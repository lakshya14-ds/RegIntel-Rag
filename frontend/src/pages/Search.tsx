import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search as SearchIcon, RefreshCw, AlertCircle, ArrowRight } from 'lucide-react';
import { useSearch } from '../hooks/useSearch';
import { RetrievalMode } from '../types/api';
import { formatDate } from '../utils/dates';
import { formatScore } from '../utils/formatting';
import { Badge } from '../components/common/Badge';

export const Search: React.FC = () => {
  const [query, setQuery] = useState('');
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>('hybrid');
  const [topK, setTopK] = useState(10);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [authorityFilter, setAuthorityFilter] = useState('');

  const { data, isLoading, error, search, retry } = useSearch();

  const handleSearch = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim() || isLoading) return;

    search({
      query: query.trim(),
      top_k: topK,
      retrieval_mode: retrievalMode,
      category: categoryFilter || null,
      source: authorityFilter || null,
    });
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">
          <span>🔎</span> Search Documents & Evidence
        </h1>
        <p className="page-subtitle">
          Direct candidate clause retrieval across the indexed regulatory corpus using BM25 keyword matching, dense vector search, or neural cross-encoder reranking.
        </p>
      </div>

      {/* Search Filter Box */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <form onSubmit={handleSearch}>
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Enter compliance search terms (e.g. investment adviser client agreement fee limit)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isLoading}
              style={{ fontSize: '1rem', padding: '0.75rem 1rem' }}
            />
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!query.trim() || isLoading}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '0.75rem 1.25rem', whiteSpace: 'nowrap' }}
            >
              <SearchIcon size={16} /> Search
            </button>
          </div>

          <div className="grid-4">
            <div>
              <label className="form-label">Authority Filter</label>
              <select
                className="form-select"
                value={authorityFilter}
                onChange={(e) => setAuthorityFilter(e.target.value)}
              >
                <option value="">All Regulators</option>
                <option value="SEBI">SEBI (Securities)</option>
                <option value="RBI">RBI (Banking)</option>
                <option value="IRDAI">IRDAI (Insurance)</option>
                <option value="PFRDA">PFRDA (Pension)</option>
                <option value="IFSCA">IFSCA (IFSC / GIFT)</option>
              </select>
            </div>

            <div>
              <label className="form-label">Retrieval Algorithm</label>
              <select
                className="form-select"
                value={retrievalMode}
                onChange={(e) => setRetrievalMode(e.target.value as RetrievalMode)}
              >
                <option value="hybrid">Hybrid (Vector + BM25 Fusion)</option>
                <option value="hybrid_reranked">Hybrid + Neural BGE Reranker</option>
                <option value="bm25">BM25 Keyword Only</option>
                <option value="vector">Dense Vector Only</option>
              </select>
            </div>

            <div>
              <label className="form-label">Category Filter</label>
              <select
                className="form-select"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                <option value="">All Categories</option>
                <option value="Investment Adviser">Investment Adviser</option>
                <option value="Mutual Funds">Mutual Funds</option>
                <option value="Stock Brokers">Stock Brokers</option>
                <option value="Research Analysts">Research Analysts</option>
                <option value="Depositories">Depositories</option>
              </select>
            </div>

            <div>
              <label className="form-label">Candidate Limit: {topK}</label>
              <input
                type="range"
                min={1}
                max={25}
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                style={{ width: '100%', marginTop: '8px' }}
              />
            </div>
          </div>
        </form>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
          <RefreshCw size={28} className="animate-spin" style={{ color: 'var(--primary-600)', marginBottom: '1rem' }} />
          <h3 style={{ fontSize: '1.1rem' }}>Retrieving candidate regulatory clauses...</h3>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="alert alert-danger">
          <AlertCircle size={20} />
          <div style={{ flex: 1 }}>
            <strong>Search Failed:</strong> {error.message}
          </div>
          <button className="btn btn-secondary btn-sm" onClick={retry}>
            Retry
          </button>
        </div>
      )}

      {/* Results */}
      {data && !isLoading && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1.15rem' }}>
              Retrieved {data.total_results} Evidence Chunks
            </h2>
            <Badge variant="blue">Mode: {data.retrieval_mode}</Badge>
          </div>

          {data.results.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
              No regulatory chunks matched your query and filter criteria.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {data.results.map((item) => (
                <div key={item.chunk_id} className="card" style={{ marginBottom: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className="badge badge-purple">Rank #{item.rank}</span>
                      <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>{item.title || 'Regulatory Clause'}</h3>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Badge variant="blue">{item.source || 'SEBI'}</Badge>
                      <Badge variant="gray">Score: {formatScore(item.score)}</Badge>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                    <strong>Section:</strong> {item.section || 'General'} | 📅 Published: <code>{formatDate(item.published_date)}</code> | Effective: <code>{formatDate(item.effective_date)}</code>
                  </div>

                  <div
                    style={{
                      padding: '0.75rem',
                      backgroundColor: '#f8fafc',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.88rem',
                      lineHeight: 1.5,
                      color: 'var(--text-primary)',
                      marginBottom: '0.75rem',
                    }}
                  >
                    {item.content_snippet}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Doc ID: <code>{item.document_id}</code>
                    </span>
                    <Link
                      to={`/document/${item.document_id}`}
                      className="btn btn-outline btn-sm"
                    >
                      View Full Document <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
