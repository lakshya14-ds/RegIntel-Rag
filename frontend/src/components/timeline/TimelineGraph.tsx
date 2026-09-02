import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, CheckCircle } from 'lucide-react';
import { DocumentVersionResponse } from '../../types/api';
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
  const timeline = versionInfo.timeline || [];

  return (
    <div>
      {/* Predecessor & Successor Summary Cards */}
      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        {/* Predecessor */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '1.2rem' }}>⬅️</span>
            <h4 style={{ fontSize: '1rem' }}>Predecessor (Supersedes)</h4>
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
                <Link
                  to={`/document/${versionInfo.predecessor.document_id}`}
                  className="btn btn-outline btn-sm"
                >
                  View Details
                </Link>
                <Link
                  to={`/compare?docA=${versionInfo.predecessor.document_id}&docB=${selectedDocId}`}
                  className="btn btn-primary btn-sm"
                >
                  Compare with Selected
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
              No prior predecessor recorded (Baseline Regulation).
            </div>
          )}
        </div>

        {/* Successor */}
        <div className="card" style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '1.2rem' }}>➡️</span>
            <h4 style={{ fontSize: '1rem' }}>Successor (Superseded By)</h4>
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
                <Link
                  to={`/document/${versionInfo.successor.document_id}`}
                  className="btn btn-outline btn-sm"
                >
                  View Details
                </Link>
                <Link
                  to={`/compare?docA=${selectedDocId}&docB=${versionInfo.successor.document_id}`}
                  className="btn btn-primary btn-sm"
                >
                  Compare with Selected
                </Link>
              </div>
            </div>
          ) : (
            <div style={{ color: '#059669', fontWeight: 500, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle size={16} />
              No successor identified — this regulation is actively <strong>CURRENT</strong>.
            </div>
          )}
        </div>
      </div>

      {/* Chronological Vertical Timeline */}
      <h3 style={{ fontSize: '1.15rem', marginBottom: '1rem' }}>
        📈 Version Evolution Timeline ({timeline.length} events)
      </h3>

      {timeline.length === 0 ? (
        <div className="card" style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No timeline events mapped for this document.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {timeline.map((node, idx) => {
            const isTarget = node.document_id === selectedDocId;
            const nodeStatus = (node.status || 'unknown').toLowerCase();
            const badgeVariant = nodeStatus === 'current' ? 'green' : nodeStatus === 'historical' ? 'amber' : 'gray';

            return (
              <React.Fragment key={node.document_id || idx}>
                <div
                  style={{
                    backgroundColor: isTarget ? '#eff6ff' : '#ffffff',
                    border: `2px solid ${isTarget ? '#3b82f6' : 'var(--border-subtle)'}`,
                    borderRadius: 'var(--radius-md)',
                    padding: '1rem 1.25rem',
                    boxShadow: isTarget ? '0 0 0 2px rgba(59,130,246,0.1)' : 'var(--shadow-sm)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontWeight: 700, fontSize: '1.05rem' }}>
                        {idx + 1}. {node.title || 'Regulatory Document'}
                      </span>
                      {isTarget && <Badge variant="blue">📍 SELECTED</Badge>}
                      <Badge variant={badgeVariant}>{node.status.toUpperCase()}</Badge>
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <Link to={`/document/${node.document_id}`} className="btn btn-secondary btn-sm">
                        Details
                      </Link>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <span>📅 <strong>Published:</strong> <code>{formatDate(node.published_date)}</code></span>
                    <span><strong>Relationship:</strong> {node.relationship}</span>
                    <span><code style={{ fontSize: '0.78rem' }}>{node.document_id}</code></span>
                  </div>
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
                    <span>superseded by</span>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
};
