import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Scale, RefreshCw, AlertCircle, Download, ExternalLink, Sparkles } from 'lucide-react';
import { useComparison } from '../hooks/useComparison';
import { useLatestDocuments } from '../hooks/useDocuments';
import { formatDate } from '../utils/dates';
import { Badge } from '../components/common/Badge';
import { MetricsRow } from '../components/comparison/MetricsRow';
import { SectionDeltaCard } from '../components/comparison/SectionDeltaCard';

export const Compare: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialDocA = searchParams.get('docA') || '';
  const initialDocB = searchParams.get('docB') || '';

  const [docAId, setDocAId] = useState(initialDocA);
  const [docBId, setDocBId] = useState(initialDocB);
  const [activeFilter, setActiveFilter] = useState<string>('ALL');

  const { data: availableDocs } = useLatestDocuments({ limit: 40 });
  const { data, isLoading, error, compare } = useComparison();

  // Trigger comparison if docA & docB are in URL on load
  useEffect(() => {
    if (initialDocA && initialDocB && !data && !isLoading) {
      compare({
        document_a_id: initialDocA,
        document_b_id: initialDocB,
      });
    }
  }, [initialDocA, initialDocB, compare, data, isLoading]);

  const handleRunComparison = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!docAId.trim() || !docBId.trim() || isLoading) return;

    setSearchParams({ docA: docAId.trim(), docB: docBId.trim() });
    compare({
      document_a_id: docAId.trim(),
      document_b_id: docBId.trim(),
    });
  };

  const handleLoadSamplePair = () => {
    const a = 'af3f1df2c9ef7ec51afee6cbde3331b18925c8c801b1c3c6a17924d7ee5df8ab';
    const b = '69098d6a5fdbacf31ac64366818f3a28d50aca4beb5cd46ad2b4d0f5b224b5c8';
    setDocAId(a);
    setDocBId(b);
    setSearchParams({ docA: a, docB: b });
    compare({
      document_a_id: a,
      document_b_id: b,
    });
  };

  const handleDownloadJson = () => {
    if (!data) return;
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `comparison_${(data.older_document?.document_id || 'A').slice(0, 8)}_${(data.newer_document?.document_id || 'B').slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredChanges = data?.changes
    ? activeFilter === 'ALL'
      ? data.changes
      : data.changes.filter((c) => (c.change_type || '').toUpperCase() === activeFilter)
    : [];

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">
          <span>⚖️</span> Compare Regulatory Documents
        </h1>
        <p className="page-subtitle">
          4-Tier clause alignment engine classifying regulatory deltas (Added, Modified, Removed, Unchanged) with side-by-side textual diffs and synthesized compliance impact.
        </p>
      </div>

      {/* Document Selectors Box */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h3 className="card-title">Select Circular Versions</h3>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={handleLoadSamplePair}
            style={{ fontSize: '0.8rem' }}
          >
            ⚡ Load Sample IA Pair (2020 vs 2024)
          </button>
        </div>

        <form onSubmit={handleRunComparison}>
          <div className="grid-2" style={{ marginBottom: '1rem' }}>
            {/* Doc A */}
            <div>
              <label className="form-label">Document A (Baseline / Prior Version)</label>
              <select
                className="form-select"
                value={docAId}
                onChange={(e) => setDocAId(e.target.value)}
                style={{ marginBottom: '0.5rem' }}
              >
                <option value="">-- Select Document A from Corpus --</option>
                {availableDocs.map((d) => (
                  <option key={d.document_id} value={d.document_id}>
                    {d.title || 'Untitled'} ({formatDate(d.published_date)}) [{d.document_id.slice(0, 8)}...]
                  </option>
                ))}
              </select>
              <input
                type="text"
                className="form-control"
                placeholder="Or paste Document A ID / hash..."
                value={docAId}
                onChange={(e) => setDocAId(e.target.value)}
                style={{ fontSize: '0.85rem' }}
              />
            </div>

            {/* Doc B */}
            <div>
              <label className="form-label">Document B (Revised / Current Version)</label>
              <select
                className="form-select"
                value={docBId}
                onChange={(e) => setDocBId(e.target.value)}
                style={{ marginBottom: '0.5rem' }}
              >
                <option value="">-- Select Document B from Corpus --</option>
                {availableDocs.map((d) => (
                  <option key={d.document_id} value={d.document_id}>
                    {d.title || 'Untitled'} ({formatDate(d.published_date)}) [{d.document_id.slice(0, 8)}...]
                  </option>
                ))}
              </select>
              <input
                type="text"
                className="form-control"
                placeholder="Or paste Document B ID / hash..."
                value={docBId}
                onChange={(e) => setDocBId(e.target.value)}
                style={{ fontSize: '0.85rem' }}
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={!docAId.trim() || !docBId.trim() || isLoading}
            style={{ width: '100%', padding: '0.75rem', fontSize: '1rem', fontWeight: 600 }}
          >
            <Scale size={18} /> Compare Documents
          </button>
        </form>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <RefreshCw size={32} className="animate-spin" style={{ color: 'var(--primary-600)', marginBottom: '1rem' }} />
          <h3 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>Aligning Regulatory Clauses...</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Performing 4-tier structural matching, delta classification, and synthesizing operational compliance impacts.
          </p>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="alert alert-danger" style={{ marginBottom: '1.5rem' }}>
          <AlertCircle size={20} />
          <div>
            <strong>Comparison Error:</strong> {error.message}
          </div>
        </div>
      )}

      {/* Results */}
      {data && !isLoading && (
        <div>
          {/* Comparative Context Cards */}
          <div className="grid-2" style={{ marginBottom: '1rem' }}>
            {/* Older */}
            <div className="card" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#991b1b', marginBottom: '0.25rem' }}>
                OLDER DOCUMENT (Baseline)
              </div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                {data.older_document?.title || data.document_a.title || 'Baseline Circular'}
              </h3>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                📅 Published: <code>{formatDate(data.older_document?.published_date || data.document_a.published_date)}</code> | Status: <Badge variant="amber">HISTORICAL</Badge>
              </div>
              {data.older_document?.url && (
                <a href={data.older_document.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
                  <ExternalLink size={13} /> Open Circular Link
                </a>
              )}
            </div>

            {/* Newer */}
            <div className="card" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#166534', marginBottom: '0.25rem' }}>
                NEWER DOCUMENT (Revised)
              </div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                {data.newer_document?.title || data.document_b.title || 'Revised Circular'}
              </h3>
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                📅 Published: <code>{formatDate(data.newer_document?.published_date || data.document_b.published_date)}</code> | Status: <Badge variant="green">CURRENT</Badge>
              </div>
              {data.newer_document?.url && (
                <a href={data.newer_document.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
                  <ExternalLink size={13} /> Open Circular Link
                </a>
              )}
            </div>
          </div>

          {/* Relationship & Confidence Badges */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
            <Badge variant="blue">Relationship: {data.version_relationship}</Badge>
            <Badge variant={data.relationship_confidence?.toUpperCase() === 'HIGH' ? 'green' : 'amber'}>
              Confidence: {data.relationship_confidence}
            </Badge>
            <Badge variant="gray">Chronology Confidence: {data.document_order_confidence}</Badge>
            {data.cached && <Badge variant="purple">⚡ CACHE HIT</Badge>}
          </div>

          {/* Uncertainty Warnings */}
          {data.relationship_confidence?.toUpperCase() === 'LOW' && (
            <div className="alert alert-warning" style={{ marginBottom: '1rem' }}>
              <AlertCircle size={18} />
              <div>
                <strong>Notice:</strong> The relationship between these documents was determined with lower confidence. Verify authoritative gazette numbers.
              </div>
            </div>
          )}

          {/* Executive Summary */}
          <div className="card" style={{ padding: '1.5rem', marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <Sparkles size={18} color="var(--primary-600)" />
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Executive Change Summary</h3>
            </div>
            <p style={{ fontSize: '0.94rem', lineHeight: 1.6, color: 'var(--text-primary)', marginBottom: '1rem' }}>
              {data.executive_summary || data.summary || 'Comparison analysis completed successfully.'}
            </p>

            {data.key_changes && data.key_changes.length > 0 && (
              <div>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.4rem', color: 'var(--text-secondary)' }}>
                  📌 Key Substantive Changes:
                </h4>
                <ul style={{ paddingLeft: '1.25rem', fontSize: '0.88rem', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {data.key_changes.map((k, i) => (
                    <li key={i}>{k}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Metrics Row */}
          <MetricsRow
            total={data.total_changes || data.changes.length}
            added={data.added_count}
            removed={data.removed_count}
            modified={data.modified_count}
            unchanged={data.unchanged_count}
          />

          {/* Delta Filter Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {['ALL', 'MODIFIED', 'ADDED', 'REMOVED', 'UNCHANGED'].map((filter) => (
                <button
                  key={filter}
                  className={`btn btn-sm ${activeFilter === filter ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setActiveFilter(filter)}
                >
                  {filter}
                </button>
              ))}
            </div>

            <button className="btn btn-secondary btn-sm" onClick={handleDownloadJson}>
              <Download size={14} /> Export Report (JSON)
            </button>
          </div>

          {/* Section Delta Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {filteredChanges.map((change, idx) => (
              <SectionDeltaCard key={idx} change={change} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
