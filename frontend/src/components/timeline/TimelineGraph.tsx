import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, AlertCircle, GitBranch, Scale, Eye, FileText, CheckCircle } from 'lucide-react';
import { DocumentVersionResponse, TimelineNodeResponse } from '../../types/api';
import { formatDate } from '../../utils/dates';
import { Badge } from '../common/Badge';

interface TimelineGraphProps {
  versionInfo: DocumentVersionResponse;
  selectedDocId: string;
}

export const TimelineGraph: React.FC<TimelineGraphProps> = ({
  versionInfo,
  selectedDocId,
}) => {
  const timeline = versionInfo.timeline || versionInfo.events || [];
  const relationships = versionInfo.relationships || [];
  const statusUpper = (versionInfo.status || 'UNKNOWN').toUpperCase();

  const getStatusBadgeVariant = (status: string): 'green' | 'amber' | 'blue' | 'gray' | 'red' => {
    switch (status.toUpperCase()) {
      case 'CURRENT':
        return 'green';
      case 'HISTORICAL':
      case 'SUPERSEDED':
        return 'amber';
      case 'NOT_YET_EFFECTIVE':
        return 'blue';
      default:
        return 'gray';
    }
  };

  const formatRelLabel = (rel?: string | null): string => {
    if (!rel) return 'RELATED TO';
    switch (rel.toUpperCase()) {
      case 'SUPERSEDES':
        return 'SUPERSEDES';
      case 'AMENDS':
        return 'AMENDED BY';
      case 'CORRIGENDUM_OF':
        return 'CORRIGENDUM';
      case 'REPLACES':
        return 'REPLACES';
      case 'CLARIFIES':
        return 'CLARIFIES';
      case 'REFERENCES':
        return 'REFERENCES';
      case 'TARGET':
        return 'TARGET DOCUMENT';
      default:
        return rel.replace('_', ' ');
    }
  };

  return (
    <div>
      {/* Current Document Regulatory Status Banner (58.14) */}
      <div
        style={{
          padding: '1rem 1.25rem',
          borderRadius: 'var(--radius-md)',
          marginBottom: '1.5rem',
          backgroundColor: statusUpper === 'CURRENT' ? '#ecfdf5' : statusUpper === 'NOT_YET_EFFECTIVE' ? '#eff6ff' : '#fef3c7',
          border: `1px solid ${statusUpper === 'CURRENT' ? '#10b981' : statusUpper === 'NOT_YET_EFFECTIVE' ? '#3b82f6' : '#f59e0b'}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem'
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.25rem' }}>
            {statusUpper === 'CURRENT' ? (
              <CheckCircle size={20} color="#059669" />
            ) : (
              <AlertCircle size={20} color="#d97706" />
            )}
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0 }}>
              {statusUpper === 'CURRENT' ? 'CURRENT REGULATION (CONFIRMED)' : statusUpper === 'NOT_YET_EFFECTIVE' ? 'NOT YET IN EFFECT' : statusUpper === 'SUPERSEDED' ? 'SUPERSEDED REGULATION' : 'CURRENT STATUS UNKNOWN'}
            </h3>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
            {statusUpper === 'CURRENT'
              ? 'This regulatory document is in effect with no subsequent superseding instruments found in corpus.'
              : statusUpper === 'NOT_YET_EFFECTIVE'
              ? 'This document has a future effective date and has not yet entered into binding legal force.'
              : statusUpper === 'SUPERSEDED'
              ? 'This document was replaced or superseded by a subsequent circular.'
              : 'Regulatory status cannot be conclusively established from available evidence. Always verify with official SEBI Gazette.'}
          </p>
        </div>

        {/* 58.15 Version Comparison Button if reliable predecessor exists */}
        {versionInfo.predecessor && (
          <Link
            to={`/compare?docA=${versionInfo.predecessor.document_id}&docB=${selectedDocId}`}
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <Scale size={16} /> Compare with Previous Version
          </Link>
        )}
      </div>

      {/* Predecessor & Successor Summary Cards */}
      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        {/* Predecessor */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '1.2rem' }}>⬅️</span>
            <h4 style={{ fontSize: '1rem' }}>Predecessor (Prior Version)</h4>
          </div>
          {versionInfo.predecessor ? (
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: '0.35rem' }}>
                {versionInfo.predecessor.title || 'Untitled Circular'}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                📅 Published: <code>{formatDate(versionInfo.predecessor.published_date)}</code> | Status: <Badge variant="amber">HISTORICAL</Badge>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <Link to={`/document/${versionInfo.predecessor.document_id}`} className="btn btn-outline btn-sm">
                  <Eye size={13} /> View Document
                </Link>
                <Link
                  to={`/compare?docA=${versionInfo.predecessor.document_id}&docB=${selectedDocId}`}
                  className="btn btn-primary btn-sm"
                >
                  <Scale size={13} /> Compare With Previous
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
              No prior predecessor recorded (Baseline / Standalone Instrument).
            </div>
          )}
        </div>

        {/* Successor */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '1.2rem' }}>➡️</span>
            <h4 style={{ fontSize: '1rem' }}>Successor (Later Version)</h4>
          </div>
          {versionInfo.successor ? (
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: '0.35rem' }}>
                {versionInfo.successor.title || 'Untitled Circular'}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                📅 Published: <code>{formatDate(versionInfo.successor.published_date)}</code> | Status: <Badge variant="green">CURRENT</Badge>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <Link to={`/document/${versionInfo.successor.document_id}`} className="btn btn-outline btn-sm">
                  <Eye size={13} /> View Document
                </Link>
                <Link
                  to={`/compare?docA=${selectedDocId}&docB=${versionInfo.successor.document_id}`}
                  className="btn btn-primary btn-sm"
                >
                  <Scale size={13} /> Compare With Successor
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ color: '#059669', fontWeight: 500, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle size={16} />
              No successor identified in regulatory corpus.
            </div>
          )}
        </div>
      </div>

      {/* Uncertainty Notice if Chronology or Confidence is Low */}
      {versionInfo.chronology_uncertain && (
        <div className="alert alert-warning" style={{ marginBottom: '1.5rem' }}>
          <AlertCircle size={18} />
          <div>
            <strong>Chronology Notice:</strong> One or more documents in this timeline have missing publication/effective dates. Timeline order reflects discovery sequence.
          </div>
        </div>
      )}

      {/* Chronological Vertical Timeline (58.8 Multi-Branch) */}
      <h3 style={{ fontSize: '1.15rem', marginBottom: '1rem' }}>
        📈 Regulatory Evolution Timeline ({timeline.length} events)
      </h3>

      {timeline.length === 0 ? (
        <div className="card" style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No timeline events mapped for this document.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {timeline.map((node: TimelineNodeResponse, idx: number) => {
            const isTarget = node.document_id === selectedDocId;
            const nodeStatus = (node.status || 'UNKNOWN').toUpperCase();
            const badgeVariant = getStatusBadgeVariant(nodeStatus);
            const isLowConf = (node.relationship_confidence || '').toUpperCase() === 'LOW';
            const prevNode = idx > 0 ? timeline[idx - 1] : null;

            return (
              <React.Fragment key={node.document_id || idx}>
                <div
                  style={{
                    backgroundColor: isTarget ? '#eff6ff' : '#ffffff',
                    border: `2px solid ${isTarget ? '#3b82f6' : 'var(--border-subtle)'}`,
                    borderRadius: 'var(--radius-md)',
                    padding: '1.15rem 1.25rem',
                    boxShadow: isTarget ? '0 0 0 2px rgba(59,130,246,0.1)' : 'var(--shadow-sm)',
                    marginLeft: node.is_branch ? '2rem' : 0,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {node.is_branch && <GitBranch size={16} color="#7c3aed" />}
                      <span style={{ fontWeight: 700, fontSize: '1.05rem' }}>
                        {idx + 1}. {node.title || 'Regulatory Document'}
                      </span>
                      {isTarget && <Badge variant="blue">📍 CURRENT DOCUMENT</Badge>}
                      <Badge variant={badgeVariant}>{nodeStatus}</Badge>
                      <Badge variant="purple">{formatRelLabel(node.relationship_to_previous || node.relationship)}</Badge>
                      {isLowConf ? (
                        <Badge variant="amber">⚠️ Possible relationship</Badge>
                      ) : (
                        <Badge variant="green">Verified</Badge>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <Link to={`/document/${node.document_id}`} className="btn btn-secondary btn-sm">
                        <Eye size={13} /> View
                      </Link>
                      {prevNode && prevNode.document_id !== node.document_id && (
                        <Link
                          to={`/compare?docA=${prevNode.document_id}&docB=${node.document_id}`}
                          className="btn btn-outline btn-sm"
                        >
                          <Scale size={13} /> Diff
                        </Link>
                      )}
                    </div>
                  </div>

                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', gap: '1.25rem', flexWrap: 'wrap', marginBottom: '0.35rem' }}>
                    <span>📅 <strong>Published:</strong> <code>{formatDate(node.published_date)}</code></span>
                    {node.effective_date && (
                      <span>⚡ <strong>Effective:</strong> <code>{formatDate(node.effective_date)}</code></span>
                    )}
                    <span><strong>ID:</strong> <code style={{ fontSize: '0.78rem' }}>{node.document_id.slice(0, 16)}...</code></span>
                  </div>

                  {node.evidence && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', borderTop: '1px dashed var(--border-subtle)', paddingTop: '0.35rem', marginTop: '0.35rem' }}>
                      Citation evidence: "{node.evidence}"
                    </div>
                  )}
                </div>

                {idx < timeline.length - 1 && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.5rem',
                      color: '#94a3b8',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      padding: '0.2rem 0',
                    }}
                  >
                    <ArrowDown size={18} />
                    <span>{formatRelLabel(timeline[idx + 1]?.relationship_to_previous || 'EVOLVED TO')}</span>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}

      {/* Relationships Table (58.11) */}
      {relationships.length > 0 && (
        <div className="card" style={{ marginTop: '2rem', padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <FileText size={18} color="var(--primary-600)" />
            <h4 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>Document Relationship Graph ({relationships.length})</h4>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: '0.85rem', textAlign: 'left', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.5rem' }}>Relationship</th>
                  <th style={{ padding: '0.5rem' }}>Target Document</th>
                  <th style={{ padding: '0.5rem' }}>Confidence</th>
                  <th style={{ padding: '0.5rem' }}>Evidence / Basis</th>
                </tr>
              </thead>
              <tbody>
                {relationships.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '0.5rem' }}>
                      <Badge variant="purple">{formatRelLabel(r.relationship_type)}</Badge>
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <Link to={`/document/${r.target_document_id}`} style={{ fontWeight: 600 }}>
                        {r.target_document_id.slice(0, 16)}...
                      </Link>
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <Badge variant={r.confidence.toUpperCase() === 'HIGH' ? 'green' : 'amber'}>
                        {r.confidence.toUpperCase() === 'LOW' ? 'Possible' : r.confidence}
                      </Badge>
                    </td>
                    <td style={{ padding: '0.5rem', color: 'var(--text-secondary)' }}>
                      {r.evidence || 'Taxonomy / Citation link'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
