import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GroundedAnswer } from '../components/chat/GroundedAnswer';

describe('GroundedAnswer Component', () => {
  it('renders answer text and turns bracketed citation tokens [1], [2] into clickable buttons', () => {
    const handleSelectCitation = vi.fn();
    const answerText =
      'According to SEBI Circular [1], fee caps must not exceed 2.5% [2].';

    render(
      <GroundedAnswer
        answer={answerText}
        onSelectCitation={handleSelectCitation}
      />
    );

    // Verify text
    expect(screen.getByText(/fee caps must not exceed 2.5%/i)).toBeInTheDocument();

    // Verify citation tags [1] and [2]
    const btn1 = screen.getByRole('button', { name: /Source citation 1/i });
    const btn2 = screen.getByRole('button', { name: /Source citation 2/i });
    expect(btn1).toBeInTheDocument();
    expect(btn2).toBeInTheDocument();

    // Click [1]
    fireEvent.click(btn1);
    expect(handleSelectCitation).toHaveBeenCalledWith(1);

    // Click [2]
    fireEvent.click(btn2);
    expect(handleSelectCitation).toHaveBeenCalledWith(2);
  });
});
