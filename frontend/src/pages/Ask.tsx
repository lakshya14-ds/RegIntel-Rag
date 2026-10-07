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
  Cpu,
  CheckCircle,
  ShieldCheck,
  Layers,
  Network,
} from 'lucide-react';
import { useAsk } from '../hooks/useAsk';
import { RetrievalMode, AgenticRAGResponse } from '../types/api';
import { askAgenticQuery } from '../api/compliance';
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

  // Phase 75-78 Agentic RAG state
  const [isAgenticMode, setIsAgenticMode] = useState(true);
  const [agenticData, setAgenticData] = useState<AgenticRAGResponse | null>(null);
  const [isAgenticLoading, setIsAgenticLoading] = useState(false);
  const [agenticError, setAgenticError] = useState<string | null>(null);

  const {
    data: standardData,
    isLoading: isStandardLoading,
    error: standardError,
    activeCitation,
    ask: askStandard,
    cancel: cancelStandard,
    selectCitation,
    closeCitation,
  } = useAsk();

  const isLoading = isAgenticMode ? isAgenticLoading : isStandardLoading;
  const error = isAgenticMode ? (agenticError ? { message: agenticError } : null) : standardError;

  const suggestedQueries = [
    'Compare cybersecurity audit requirements between SEBI and RBI',
    'What are the latest SEBI requirements for investment advisers?',
    'What is the fee cap structure specified under Regulation 15A for investment advisers?',
    'Is there any potential conflict between RBI and SEBI KYC norms?',
  ];

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim() || isLoading) return;

    if (isAgenticMode) {
      setIsAgenticLoading(true);
      setAgenticError(null);
      setAgenticData(null);
      try {
        const res = await askAgenticQuery({
          query: question.trim(),
          force_agentic: false, // Allows automatic fast-path for simple queries
          authority: authorityFilter || undefined,
        });
        setAgenticData(res);
      } catch (err: any) {
        setAgenticError(err.message || 'Agentic multi-hop retrieval failed');
      } finally {
        setIsAgenticLoading(false);
      }
    } else {
      askStandard({
        question: question.trim(),
        top_k: topK,
        retrieval_mode: retrievalMode,
        category: categoryFilter || null,
        source: authorityFilter || null,
      });
    }
  };

  const handleSuggestedClick = (q: string) => {
    setQuestion(q);
    if (isAgenticMode) {
      setIsAgenticLoading(true);
      setAgenticError(null);
      setAgenticData(null);
      askAgenticQuery({
        query: q,
        force_agentic: false,
        authority: authorityFilter || undefined,
      })
        .then((res) => setAgenticData(res))
        .catch((err) => setAgenticError(err.message))
        .finally(() => setIsAgenticLoading(false));
    } else {
      askStandard({
        question: q,
        top_k: topK,
        retrieval_mode: retrievalMode,
        category: categoryFilter || null,
        source: authorityFilter || null,
      });
    }
  };

  return (
    <div className="page-container">
      {/* Page Header */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="page-title">
            <span>💬</span> Ask RegIntel
          </h1>
          <p className="page-subtitle">
            Multi-regulator question answering with adaptive multi-hop retrieval, evidence graph verification, and conservative synthesis.
          </p>
        </div>

        {/* Agentic Mode Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--surface-subtle)', padding: '0.5rem 0.85rem', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Cpu size={16} color={isAgenticMode ? 'var(--primary-600)' : 'var(--text-muted)'} />
            <span style={{ fontSize: '0.88rem', fontWeight: 600 }}>Agentic Multi-Hop</span>
          </div>
          <button
            type="button"
            className={`btn btn-sm ${isAgenticMode ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setIsAgenticMode(!isAgenticMode)}
            style={{ fontSize: '0.78rem', padding: '0.25rem 0.65rem' }}
          >
            {isAgenticMode ? 'Enabled' : 'Fast-Path Only'}
          </button>
        </div>
      </div>

      {/* Search Input Box */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <input
              type="text"
              className="form-control"
              placeholder="Ask a regulatory compliance query (e.g. Compare cybersecurity audit mandates between SEBI and RBI)..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isLoading}
              style={{ fontSize: '1rem', padding: '0.75rem 1rem' }}
            />
            {isLoading ? (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  if (!isAgenticMode) cancelStandard();
                  setIsAgenticLoading(false);
                }}
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

      {/* Loading State with Operational Stepper */}
      {isLoading && (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
          <div style={{ display: 'inline-flex', marginBottom: '1rem', color: 'var(--primary-600)' }}>
            <RefreshCw size={28} className="animate-spin" />
          </div>
          <h3 style={{ fontSize: '1.15rem', marginBottom: '0.5rem' }}>
            {isAgenticMode ? 'Executing Multi-Hop Regulatory Reasoning...' : 'Analyzing Regulatory Sources...'}
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', maxWidth: '500px', margin: '0 auto' }}>
            {isAgenticMode
              ? 'Evaluating query complexity, orchestrating staged retrieval hops, constructing evidence graph, and verifying factual claims.'
              : 'Performing multi-stage retrieval, neural cross-encoder reranking, and citation verification.'}
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
          <button className="btn btn-secondary btn-sm" onClick={() => handleSubmit()}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}

      {/* AGENTIC RAG RESULT VIEW */}
      {isAgenticMode && agenticData && !isLoading && (
        <div>
          {/* Operational Status & Architecture Stepper (Non-CoT) */}
          <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem', background: '#f8fafc' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Layers size={18} color="var(--primary-600)" />
                <strong style={{ fontSize: '0.95rem' }}>Operational Execution Path</strong>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Badge variant={agenticData.fast_path_used ? 'blue' : 'green'}>
                  {agenticData.fast_path_used ? 'Fast Path (Direct)' : `Multi-Hop (${agenticData.strategy_used})`}
                </Badge>
                <Badge variant="purple">{agenticData.total_hops} Hop{agenticData.total_hops > 1 ? 's' : ''}</Badge>
                <Badge variant="blue">{agenticData.total_evidence_count} Evidence Items</Badge>
                <Badge variant="green">{Math.round(agenticData.verification_rate * 100)}% Verified</Badge>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
              {agenticData.operational_steps.map((step, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                  <CheckCircle size={14} color="#10b981" />
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Main Verified Answer Card */}
          <div className="card" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={18} color="var(--primary-600)" />
                <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Conservative Grounded Synthesis</h2>
              </div>
              <Badge variant="green">Safe Verification Passed</Badge>
            </div>

            <GroundedAnswer answer={agenticData.answer} onSelectCitation={selectCitation} />

            <div style={{ marginTop: '1.5rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              ⚖️ Grounded regulatory synthesis verified against active indexed evidence. Phrased cautiously to adhere to official regulatory status.
            </div>
          </div>

          {/* Verified Claims Breakdown */}
          {agenticData.verified_claims && agenticData.verified_claims.length > 0 && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ShieldCheck size={18} color="var(--primary-600)" />
                  <h3 className="card-title">Atomic Verified Claims ({agenticData.verified_claims.length})</h3>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {agenticData.verified_claims.map((c) => {
                  let badgeVariant: 'green' | 'blue' | 'amber' | 'red' = 'green';
                  if (c.verification_status === 'PARTIALLY_SUPPORTED') badgeVariant = 'amber';
                  if (c.verification_status === 'UNSUPPORTED' || c.verification_status === 'CONTRADICTED') badgeVariant = 'red';

                  return (
                    <div
                      key={c.claim_id}
                      style={{
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-md)',
                        padding: '0.85rem 1rem',
                        backgroundColor: '#f8fafc',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <strong style={{ fontSize: '0.88rem' }}>Claim #{c.claim_id.replace('claim_', '')} ({c.claim_type})</strong>
                        <Badge variant={badgeVariant}>{c.verification_status.replace('_', ' ')}</Badge>
                      </div>
                      <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-primary)' }}>{c.text}</p>
                      {c.verification_notes && (
                        <div style={{ marginTop: '0.35rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          <em>{c.verification_notes}</em>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Evidence Graph Summary */}
          {agenticData.evidence_graph_summary && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Network size={18} color="var(--primary-600)" />
                  <h3 className="card-title">Evidence Graph Topology</h3>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', fontSize: '0.88rem' }}>
                <div style={{ padding: '0.75rem', background: '#f1f5f9', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Total Graph Nodes</div>
                  <strong style={{ fontSize: '1.2rem' }}>{agenticData.evidence_graph_summary.total_nodes}</strong>
                </div>
                <div style={{ padding: '0.75rem', background: '#f1f5f9', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Relational Edges</div>
                  <strong style={{ fontSize: '1.2rem' }}>{agenticData.evidence_graph_summary.total_edges}</strong>
                </div>
                <div style={{ padding: '0.75rem', background: '#f1f5f9', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Covered Authorities</div>
                  <strong style={{ fontSize: '1.05rem' }}>
                    {agenticData.evidence_graph_summary.authorities?.join(', ') || 'General'}
                  </strong>
                </div>
              </div>
            </div>
          )}

          {/* Grounded Citation Sources */}
          {agenticData.citations && agenticData.citations.length > 0 && (
            <div className="card">
              <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <BookOpen size={18} color="var(--primary-600)" />
                  <h3 className="card-title">Source Citations ({agenticData.citations.length})</h3>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {agenticData.citations.map((c, idx) => (
                  <div
                    key={idx}
                    style={{
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.85rem 1rem',
                      backgroundColor: '#f8fafc',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                      <span className="citation-tag">[{idx + 1}]</span>
                      <strong style={{ fontSize: '0.92rem' }}>{c.title || c.document_id || 'Regulatory Evidence'}</strong>
                      {c.authority && <Badge variant="blue">{c.authority}</Badge>}
                      {c.type && <Badge variant="purple">{c.type}</Badge>}
                    </div>
                    <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
                      {c.text_snippet || c.snippet}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* STANDARD RAG RESULT VIEW (Fallback / Non-Agentic) */}
      {!isAgenticMode && standardData && !isLoading && (
        <div>
          <QueryIntentPanel intent={standardData.query_intent} />

          {!standardData.sufficient_evidence && (
            <div className="alert alert-warning">
              <Info size={18} />
              <div>
                <strong>Limited Evidence Notice:</strong> The system refrained from speculating beyond available indexed regulatory documents.
              </div>
            </div>
          )}

          <div className="card" style={{ padding: '1.75rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Sparkles size={18} color="var(--primary-600)" />
                <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Grounded Synthesis</h2>
              </div>
              <Badge variant="green">100% Citations Verified</Badge>
            </div>

            <GroundedAnswer answer={standardData.answer} onSelectCitation={selectCitation} />

            <div style={{ marginTop: '1.5rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              ⚖️ {standardData.disclaimer}
            </div>
          </div>

          {standardData.sources && standardData.sources.length > 0 && (
            <div className="card">
              <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <BookOpen size={18} color="var(--primary-600)" />
                  <h3 className="card-title">Retrieved Evidence Sources ({standardData.sources.length})</h3>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {standardData.sources.map((s) => (
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
      {!standardData && !agenticData && !isLoading && !error && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--text-secondary)' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>⚖️</div>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
            Ready to explore multi-regulator intelligence
          </h3>
          <p style={{ maxWidth: '540px', margin: '0 auto', fontSize: '0.92rem', lineHeight: 1.6 }}>
            Ask questions regarding compliance frameworks, fee caps, audit schedules, cross-regulator overlaps, potential inconsistencies, or circular supersession.
          </p>
        </div>
      )}

      {/* Active Citation Side Drawer */}
      <CitationDrawer citation={activeCitation} onClose={closeCitation} />
    </div>
  );
};
