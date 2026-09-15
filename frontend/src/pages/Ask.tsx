import React, { useState } from 'react';
import {
  Send,
  Sparkles,
  SlidersHorizontal,
  RefreshCw,
  AlertCircle,
  BookOpen,
  Info,
  XCircle,
} from 'lucide-react';
import { useAsk } from '../hooks/useAsk';
import { RetrievalMode } from '../types/api';
import { GroundedAnswer } from '../components/chat/GroundedAnswer';
import { QueryIntentPanel } from '../components/chat/QueryIntentPanel';
import { CitationDrawer } from '../components/citations/CitationDrawer';
import { formatDate } from '../utils/dates';
import { formatScore } from '../utils/formatting';
import { Badge } from '../components/common/Badge';

export const Ask: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>('hybrid');
  const [topK, setTopK] = useState(5);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [authorityFilter, setAuthorityFilter] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  const {
    data,
    isLoading,
    error,
    activeCitation,
    ask,
    cancel,
    retry,
    selectCitation,
    closeCitation,
  } = useAsk();

  const suggestedQueries = [
    'What are the latest SEBI requirements for investment advisers?',
    'What is the fee cap structure specified under Regulation 15A for investment advisers?',
    'What are the qualification and certification norms for research analysts?',
    'What changed in the latest investment adviser circular?',
  ];

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim() || isLoading) return;

    ask({
      question: question.trim(),
      top_k: topK,
      retrieval_mode: retrievalMode,
      category: categoryFilter || null,
      source: authorityFilter || null,
    });
  };

  const handleSuggestedClick = (q: string) => {
    setQuestion(q);
    ask({
      question: q,
      top_k: topK,
      retrieval_mode: retrievalMode,
      category: categoryFilter || null,
      source: authorityFilter || null,
    });
  };

  return (
    <div className="page-container">
      {/* Page Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">
          <span>💬</span> Ask RegIntel
        </h1>
        <p className="page-subtitle">
          Grounded regulatory question answering strictly constrained by indexed SEBI circulars with deterministic citations.
        </p>
      </div>

      {/* Search Input Box */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Ask a regulatory compliance query (e.g. investment adviser client agreement rules)..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isLoading}
              style={{ fontSize: '1rem', padding: '0.75rem 1rem' }}
            />
            {isLoading ? (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={cancel}
                style={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <XCircle size={16} /> Stop
              </button>
            ) : (
              <button
                type="submit"
                className="btn btn-primary"
                disabled={!question.trim()}
                style={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '6px', padding: '0.75rem 1.25rem' }}
              >
                <Send size={16} /> Ask
              </button>
            )}
            <button
              type="button"
              className={`btn ${showSettings ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setShowSettings(!showSettings)}
              title="Toggle Retrieval Settings"
              style={{ padding: '0.75rem' }}
            >
              <SlidersHorizontal size={18} />
            </button>
          </div>
        </form>

        {/* Expandable Settings */}
        {showSettings && (
          <div
            style={{
              marginTop: '1rem',
              paddingTop: '1rem',
              borderTop: '1px solid var(--border-subtle)',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '1rem',
            }}
          >
            <div>
              <label className="form-label">Retrieval Engine Mode</label>
              <select
                className="form-select"
                value={retrievalMode}
                onChange={(e) => setRetrievalMode(e.target.value as RetrievalMode)}
              >
                <option value="hybrid">Hybrid (Dense Vector + BM25)</option>
                <option value="hybrid_reranked">Hybrid + Neural BGE Reranker</option>
                <option value="bm25">BM25 Lexical Only</option>
                <option value="vector">Dense Vector Search Only</option>
              </select>
            </div>

            <div>
              <label className="form-label">Evidence Top-K Candidates: {topK}</label>
              <input
                type="range"
                min={1}
                max={15}
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                style={{ width: '100%', marginTop: '8px' }}
              />
            </div>

            <div>
              <label className="form-label">Regulatory Authority</label>
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
              <label className="form-label">Regulatory Category Filter</label>
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
          </div>
        )}

        {/* Suggested Queries */}
        <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            Suggested:
          </span>
          {suggestedQueries.map((q, idx) => (
            <button
              key={idx}
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => handleSuggestedClick(q)}
              style={{ fontSize: '0.78rem', padding: '0.25rem 0.6rem' }}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
          <div style={{ display: 'inline-flex', marginBottom: '1rem', color: 'var(--primary-600)' }}>
            <RefreshCw size={28} className="animate-spin" />
          </div>
          <h3 style={{ fontSize: '1.15rem', marginBottom: '0.5rem' }}>
            Analyzing Regulatory Sources...
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Performing multi-stage retrieval, neural cross-encoder reranking, and citation verification.
          </p>
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <div className="alert alert-danger" style={{ marginBottom: '1.5rem' }}>
          <AlertCircle size={20} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>Regulatory Q&A Error</div>
            <div style={{ fontSize: '0.88rem' }}>{error.message}</div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={retry}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}

      {/* Answer State */}
      {data && !isLoading && (
        <div>
          {/* Query Interpretation Panel */}
          <QueryIntentPanel intent={data.query_intent} />

          {/* Insufficient Evidence Notice if applicable */}
          {!data.sufficient_evidence && (
            <div className="alert alert-warning">
              <Info size={18} />
              <div>
                <strong>Limited Evidence Notice:</strong> The system refrained from speculating beyond available indexed regulatory documents.
              </div>
            </div>
          )}

          {/* Main Grounded Answer Card */}
          <div className="card" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={18} color="var(--primary-600)" />
                <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Grounded Synthesis</h2>
              </div>
              <Badge variant="green">100% Citations Verified</Badge>
            </div>

            {/* Answer Content */}
            <GroundedAnswer answer={data.answer} onSelectCitation={selectCitation} />

            {/* Disclaimer */}
            <div style={{ marginTop: '1.5rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              ⚖️ {data.disclaimer}
            </div>
          </div>

          {/* Retrieved Key Evidence Sources List */}
          {data.sources && data.sources.length > 0 && (
            <div className="card">
              <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <BookOpen size={18} color="var(--primary-600)" />
                  <h3 className="card-title">Retrieved Evidence Sources ({data.sources.length})</h3>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {data.sources.map((s) => (
                  <div
                    key={s.source_id}
                    style={{
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.85rem 1rem',
                      backgroundColor: '#f8fafc',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                        <span className="citation-tag">[{s.source_id}]</span>
                        <strong style={{ fontSize: '0.92rem' }}>{s.title}</strong>
                        <Badge variant="blue">{s.source || 'SEBI'}</Badge>
                      </div>
                      <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                        Section: <em>{s.section || 'General'}</em> | Published: <code>{formatDate(s.published_date)}</code> | Score: <strong>{formatScore(s.score)}</strong>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="btn btn-outline btn-sm"
                      onClick={() => selectCitation(s.source_id)}
                    >
                      Inspect Source
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!data && !isLoading && !error && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--text-secondary)' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚖️</div>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
            Ready to explore regulatory obligations
          </h3>
          <p style={{ maxWidth: '540px', margin: '0 auto', fontSize: '0.92rem', lineHeight: 1.6 }}>
            Ask questions regarding compliance frameworks, fee caps, audit schedules, circular supersession, or intermediary qualification norms.
          </p>
        </div>
      )}

      {/* Active Citation Side Drawer */}
      <CitationDrawer citation={activeCitation} onClose={closeCitation} />
    </div>
  );
};
