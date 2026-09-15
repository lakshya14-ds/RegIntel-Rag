import React, { useState, useEffect } from 'react';
import {
  Activity,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Play,
  RotateCw,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { ConnectorHealth, ConnectorRun, RegulatoryAuthority } from '../../types/api';
import { fetchConnectorHealth, fetchConnectorRuns, triggerConnectorRun } from '../../api/compliance';

export const ConnectorHealthDashboard: React.FC = () => {
  const [healthList, setHealthList] = useState<ConnectorHealth[]>([]);
  const [runs, setRuns] = useState<ConnectorRun[]>([]);
  const [selectedAuthority, setSelectedAuthority] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [runningAuthorities, setRunningAuthorities] = useState<Set<string>>(new Set());
  const [isExpanded, setIsExpanded] = useState(false);

  const loadHealth = () => {
    setIsLoading(true);
    fetchConnectorHealth()
      .then(setHealthList)
      .catch((err) => console.error('Failed to load connector health:', err))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadHealth();
  }, []);

  const handleTriggerRun = async (authority: RegulatoryAuthority) => {
    setRunningAuthorities((prev) => new Set(prev).add(authority));
    try {
      await triggerConnectorRun(authority, 10, false, false);
      setTimeout(() => {
        loadHealth();
        setRunningAuthorities((prev) => {
          const next = new Set(prev);
          next.delete(authority);
          return next;
        });
      }, 3000);
    } catch (err) {
      console.error(`Error triggering run for ${authority}:`, err);
      setRunningAuthorities((prev) => {
        const next = new Set(prev);
        next.delete(authority);
        return next;
      });
    }
  };

  const handleViewRuns = (authority: string) => {
    setSelectedAuthority(authority);
    fetchConnectorRuns(authority, 10)
      .then(setRuns)
      .catch((err) => console.error('Failed to load runs:', err));
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'HEALTHY':
        return (
          <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <CheckCircle size={12} /> Healthy
          </span>
        );
      case 'WARNING':
        return (
          <span className="badge badge-warning" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <AlertTriangle size={12} /> Warning
          </span>
        );
      case 'FAILED':
        return (
          <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <XCircle size={12} /> Failed
          </span>
        );
      default:
        return (
          <span className="badge badge-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={12} /> Idle / Ready
          </span>
        );
    }
  };

  return (
    <div className="card" style={{ marginBottom: '1.5rem', borderColor: 'var(--color-border)' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Activity size={20} color="#3b82f6" />
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>
            Multi-Regulator Connector Health
          </h3>
          <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
            ({healthList.length} authorities connected)
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            className="btn btn-sm btn-outline"
            onClick={(e) => {
              e.stopPropagation();
              loadHealth();
            }}
            disabled={isLoading}
            title="Refresh Connector Health"
          >
            <RotateCw size={13} className={isLoading ? 'spin' : ''} /> Refresh
          </button>
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </div>

      {/* Grid of Regulators */}
      {isExpanded && (
        <div style={{ marginTop: '1.25rem' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '1rem',
            }}
          >
            {healthList.map((h) => {
              const isRunning = runningAuthorities.has(h.authority);
              return (
                <div
                  key={h.authority}
                  style={{
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    padding: '0.85rem',
                    background: 'var(--color-surface-hover)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 700, fontSize: '1rem', color: '#1e40af' }}>
                      {h.authority}
                    </span>
                    {getStatusBadge(h.status)}
                  </div>

                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
                    Last crawl:{' '}
                    {h.last_run_at ? new Date(h.last_run_at).toLocaleString() : 'Never'}
                  </div>

                  {h.total_discovered_last_run > 0 && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
                      Docs in last crawl: <strong>{h.total_discovered_last_run}</strong>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '6px', marginTop: '10px' }}>
                    <button
                      className="btn btn-sm btn-primary"
                      style={{ flex: 1, padding: '4px 8px', fontSize: '0.75rem' }}
                      onClick={() => handleTriggerRun(h.authority)}
                      disabled={isRunning}
                    >
                      <Play size={11} /> {isRunning ? 'Syncing...' : 'Sync Now'}
                    </button>
                    <button
                      className="btn btn-sm btn-outline"
                      style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                      onClick={() => handleViewRuns(h.authority)}
                      title="View Run History"
                    >
                      <Clock size={11} /> History
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Run History Drawer/Table */}
          {selectedAuthority && runs.length > 0 && (
            <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 600 }}>
                  Recent Ingestion Runs: {selectedAuthority}
                </h4>
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={() => setSelectedAuthority(null)}
                  style={{ fontSize: '0.75rem' }}
                >
                  Close History
                </button>
              </div>

              <div className="table-responsive">
                <table className="table" style={{ fontSize: '0.8rem' }}>
                  <thead>
                    <tr>
                      <th>Run ID</th>
                      <th>Status</th>
                      <th>Started</th>
                      <th>Discovered</th>
                      <th>New</th>
                      <th>Changed</th>
                      <th>Skipped</th>
                      <th>Failed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.run_id}>
                        <td><code>{r.run_id}</code></td>
                        <td>{getStatusBadge(r.status)}</td>
                        <td>{new Date(r.started_at).toLocaleString()}</td>
                        <td>{r.discovered_count}</td>
                        <td>{r.new_documents}</td>
                        <td>{r.changed_documents}</td>
                        <td>{r.skipped_documents}</td>
                        <td>{r.failed_documents}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
