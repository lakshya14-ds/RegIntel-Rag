import React from 'react';

interface GroundedAnswerProps {
  answer: string;
  onSelectCitation: (sourceId: number) => void;
}

/**
 * Parses markdown text into formatted elements and converts bracketed citations like [1], [2], [1, 2]
 * into interactive clickable buttons without using unsafe dangerouslySetInnerHTML.
 */
export const GroundedAnswer: React.FC<GroundedAnswerProps> = ({
  answer,
  onSelectCitation,
}) => {
  if (!answer) return null;

  // Split into lines for paragraph/heading/bullet formatting
  const lines = answer.split('\n');

  const renderInlineFormattedText = (text: string) => {
    // Regex matching [1], [2], [1, 2], [1-3] etc.
    const parts = text.split(/(\[\d+(?:,\s*\d+)*\])/g);

    return parts.map((part, index) => {
      const citationMatch = part.match(/^\[(\d+(?:,\s*\d+)*)\]$/);
      if (citationMatch) {
        const ids = citationMatch[1].split(',').map((s) => parseInt(s.trim(), 10));
        return (
          <span key={index} style={{ display: 'inline-flex', gap: '2px', verticalAlign: 'baseline' }}>
            {ids.map((id) => (
              <button
                key={id}
                type="button"
                className="citation-tag"
                onClick={() => onSelectCitation(id)}
                title={`Click to view Evidence Source [${id}]`}
                aria-label={`Source citation ${id}`}
              >
                [{id}]
              </button>
            ))}
          </span>
        );
      }

      // Format bold text **text**
      const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
      return (
        <React.Fragment key={index}>
          {boldParts.map((bPart, bIndex) => {
            if (bPart.startsWith('**') && bPart.endsWith('**')) {
              return <strong key={bIndex}>{bPart.slice(2, -2)}</strong>;
            }
            return bPart;
          })}
        </React.Fragment>
      );
    });
  };

  return (
    <div className="grounded-answer-container" style={{ fontSize: '0.96rem', lineHeight: '1.7', color: 'var(--text-primary)' }}>
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} style={{ height: '0.75rem' }} />;
        }

        if (trimmed.startsWith('### ')) {
          return (
            <h3 key={idx} style={{ fontSize: '1.15rem', marginTop: '1.25rem', marginBottom: '0.5rem', color: '#1e3a8a' }}>
              {renderInlineFormattedText(trimmed.replace(/^###\s+/, ''))}
            </h3>
          );
        }

        if (trimmed.startsWith('## ')) {
          return (
            <h2 key={idx} style={{ fontSize: '1.3rem', marginTop: '1.5rem', marginBottom: '0.6rem', color: '#1e3a8a' }}>
              {renderInlineFormattedText(trimmed.replace(/^##\s+/, ''))}
            </h2>
          );
        }

        if (trimmed.startsWith('# ')) {
          return (
            <h1 key={idx} style={{ fontSize: '1.45rem', marginTop: '1.5rem', marginBottom: '0.75rem', color: '#1e3a8a' }}>
              {renderInlineFormattedText(trimmed.replace(/^#\s+/, ''))}
            </h1>
          );
        }

        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginLeft: '1rem', marginBottom: '0.35rem' }}>
              <span style={{ color: 'var(--primary-600)', fontWeight: 'bold' }}>•</span>
              <div>{renderInlineFormattedText(trimmed.replace(/^[-*]\s+/, ''))}</div>
            </div>
          );
        }

        const numberMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
        if (numberMatch) {
          return (
            <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginLeft: '1rem', marginBottom: '0.35rem' }}>
              <span style={{ color: 'var(--primary-600)', fontWeight: 600 }}>{numberMatch[1]}.</span>
              <div>{renderInlineFormattedText(numberMatch[2])}</div>
            </div>
          );
        }

        return (
          <p key={idx} style={{ marginBottom: '0.75rem' }}>
            {renderInlineFormattedText(line)}
          </p>
        );
      })}
    </div>
  );
};
