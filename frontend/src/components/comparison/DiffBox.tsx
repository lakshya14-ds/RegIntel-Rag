import React from 'react';

interface DiffBoxProps {
  previousText?: string | null;
  currentText?: string | null;
  changeType: string;
}

export const DiffBox: React.FC<DiffBoxProps> = ({
  previousText,
  currentText,
  changeType,
}) => {
  const isModified = changeType === 'MODIFIED';
  const isAdded = changeType === 'ADDED';
  const isRemoved = changeType === 'REMOVED';

  if (isModified) {
    return (
      <div style={{ marginTop: '0.75rem' }}>
        <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
          Side-by-Side Clause Text Comparison:
        </div>
        <div className="grid-2">
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#dc2626', marginBottom: '0.25rem' }}>
              OLD TEXT (Baseline / Prior Version)
            </div>
            <div className="diff-box-old">
              {previousText || 'No prior text recorded for this section.'}
            </div>
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#16a34a', marginBottom: '0.25rem' }}>
              NEW TEXT (Revised / Current Version)
            </div>
            <div className="diff-box-new">
              {currentText || 'No revised text recorded for this section.'}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (isAdded && currentText) {
    return (
      <div style={{ marginTop: '0.75rem' }}>
        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#16a34a', marginBottom: '0.25rem' }}>
          ➕ NEWLY INTRODUCED TEXT
        </div>
        <div className="diff-box-new">{currentText}</div>
      </div>
    );
  }

  if (isRemoved && previousText) {
    return (
      <div style={{ marginTop: '0.75rem' }}>
        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#dc2626', marginBottom: '0.25rem' }}>
          ➖ REPEALED / OMITTED TEXT
        </div>
        <div className="diff-box-old">{previousText}</div>
      </div>
    );
  }

  return null;
};
