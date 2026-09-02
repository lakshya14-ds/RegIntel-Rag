import React from 'react';

interface MetricsRowProps {
  total: number;
  added: number;
  removed: number;
  modified: number;
  unchanged: number;
}

export const MetricsRow: React.FC<MetricsRowProps> = ({
  total,
  added,
  removed,
  modified,
  unchanged,
}) => {
  const metrics = [
    { label: 'Total Sections', count: total, color: '#1e293b', bg: '#f1f5f9' },
    { label: '🟢 Added', count: added, color: '#16a34a', bg: '#ecfdf5' },
    { label: '🔴 Removed', count: removed, color: '#dc2626', bg: '#fff1f2' },
    { label: '🟡 Modified', count: modified, color: '#d97706', bg: '#fffbeb' },
    { label: '⚪ Unchanged', count: unchanged, color: '#64748b', bg: '#f8fafc' },
  ];

  return (
    <div className="grid-5" style={{ marginBottom: '1.25rem' }}>
      {metrics.map((m, i) => (
        <div
          key={i}
          style={{
            backgroundColor: m.bg,
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '0.85rem',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
            {m.label}
          </div>
          <div style={{ fontSize: '1.4rem', fontWeight: 800, color: m.color }}>
            {m.count}
          </div>
        </div>
      ))}
    </div>
  );
};
