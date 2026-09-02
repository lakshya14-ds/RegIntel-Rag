import React from 'react';
import { HealthResponse } from '../../types/api';

interface StatusPillProps {
  health: HealthResponse | null;
  isLoading?: boolean;
}

export const StatusPill: React.FC<StatusPillProps> = ({ health, isLoading }) => {
  if (isLoading) {
    return (
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: '#64748b' }}>
        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#94a3b8' }} />
        Checking...
      </div>
    );
  }

  const status = health?.status || 'unavailable';
  const isOk = status === 'ok';
  const isDegraded = status === 'degraded';

  const dotColor = isOk ? '#10b981' : isDegraded ? '#f59e0b' : '#ef4444';
  const label = isOk ? 'API Online' : isDegraded ? 'API Degraded' : 'API Offline';

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '3px 9px',
        borderRadius: '9999px',
        backgroundColor: isOk ? '#ecfdf5' : isDegraded ? '#fffbeb' : '#fff1f2',
        border: `1px solid ${isOk ? '#a7f3d0' : isDegraded ? '#fde68a' : '#fecdd3'}`,
        fontSize: '0.78rem',
        fontWeight: 600,
        color: isOk ? '#065f46' : isDegraded ? '#92400e' : '#9f1239',
      }}
      title={`MongoDB: ${health?.mongodb ? 'Connected' : 'Offline/Local'} | Embeddings: ${
        health?.embedding_service ? 'Active' : 'Inactive'
      }`}
    >
      <span
        style={{
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          backgroundColor: dotColor,
        }}
      />
      {label}
    </div>
  );
};
