import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { RefreshCw, AlertCircle } from 'lucide-react';
import { useDocumentVersions, useLatestDocuments } from '../hooks/useDocuments';
import { formatDate } from '../utils/dates';
import { Badge } from '../components/common/Badge';
import { TimelineGraph } from '../components/timeline/TimelineGraph';

export const Timeline: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();

  const [selectedDocId, setSelectedDocId] = useState(documentId || '');
  const { data: availableDocs } = useLatestDocuments({ limit: 40 });
  const { data: versionInfo, isLoading, error } = useDocumentVersions(selectedDocId);

  useEffect(() => {
    if (documentId) {
      setSelectedDocId(documentId);
    }
  }, [documentId]);

  const handleSelectDoc = (id: string) => {
    setSelectedDocId(id);
    navigate(`/document/${id}/timeline`);
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title">
          <span>⏳</span> Document Timeline & Version Lineage
        </h1>
        <p className="page-subtitle">
          Inspect how financial regulations evolve over time, tracking predecessors, successors, and supersession chains.
        </p>
      </div>

      {/* Document Selector Bar */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <label className="form-label">Select Document to Trace Lineage</label>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <select
            className="form-select"
            value={selectedDocId}
            onChange={(e) => handleSelectDoc(e.target.value)}
            style={{ flex: 1, minWidth: '280px' }}
          >
            <option value="">-- Select a regulatory document from corpus --</option>
            {availableDocs.map((d) => (
              <option key={d.document_id} value={d.document_id}>
                {d.title || 'Untitled'} ({formatDate(d.published_date)}) [{d.document_id.slice(0, 8)}...]
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
          <RefreshCw size={32} className="animate-spin" style={{ color: 'var(--primary-600)', marginBottom: '1rem' }} />
          <h3>Loading version lineage graph...</h3>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="alert alert-danger">
          <AlertCircle size={20} />
          <div>
            <strong>Timeline Error:</strong> {error.message}
          </div>
        </div>
      )}

      {/* Version Info & Timeline Graph */}
      {versionInfo && !isLoading && (
        <div>
          {/* Target Document Summary */}
          <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
              <Badge variant={versionInfo.status?.toLowerCase() === 'current' ? 'green' : 'amber'}>
                {versionInfo.status?.toUpperCase()}
              </Badge>
              <Badge variant="purple">Version {versionInfo.document_version}</Badge>
              {versionInfo.relationship_type && (
                <Badge variant="blue">Type: {versionInfo.relationship_type}</Badge>
              )}
              {versionInfo.relationship_confidence && (
                <Badge variant={versionInfo.relationship_confidence?.toUpperCase() === 'HIGH' ? 'green' : 'amber'}>
                  Confidence: {versionInfo.relationship_confidence}
                </Badge>
              )}
            </div>

            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#1e3a8a', marginBottom: '0.5rem' }}>
              {versionInfo.title || 'Target Regulatory Document'}
            </h2>

            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Document ID: <code>{selectedDocId}</code>
            </div>

            {versionInfo.relationship_confidence?.toUpperCase() === 'LOW' && (
              <div className="alert alert-warning" style={{ marginTop: '1rem', marginBottom: 0 }}>
                <AlertCircle size={18} />
                <div>
                  <strong>Notice:</strong> Possible predecessor — verify the original regulatory documents before relying on legal certainty.
                </div>
              </div>
            )}
          </div>

          {/* Timeline Graph */}
          <TimelineGraph versionInfo={versionInfo} selectedDocId={selectedDocId} />
        </div>
      )}

      {/* Empty State */}
      {!selectedDocId && !isLoading && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          Please select a regulatory document above to inspect its version graph and predecessor/successor timeline.
        </div>
      )}
    </div>
  );
};
