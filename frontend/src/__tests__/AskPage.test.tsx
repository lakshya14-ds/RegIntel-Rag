import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Ask } from '../pages/Ask';
import askFixture from './fixtures/ask-success.json';

describe('Ask Page Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders input and suggested questions on empty state', () => {
    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Ask />
      </BrowserRouter>
    );

    expect(screen.getByPlaceholderText(/Ask a regulatory compliance query/i)).toBeInTheDocument();
    expect(screen.getByText(/Ready to explore regulatory obligations/i)).toBeInTheDocument();
    expect(screen.getByText(/What are the latest SEBI requirements for investment advisers\?/i)).toBeInTheDocument();
  });

  it('submits query and displays grounded answer and key evidence sources', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => askFixture,
    } as Response);

    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Ask />
      </BrowserRouter>
    );

    const input = screen.getByPlaceholderText(/Ask a regulatory compliance query/i);
    const submitBtn = screen.getByRole('button', { name: /^Ask$/i });

    fireEvent.change(input, { target: { value: 'What are the fee limits?' } });
    fireEvent.click(submitBtn);

    // Wait for synthesis card
    await waitFor(() => {
      expect(screen.getByText(/Grounded Synthesis/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/100% Citations Verified/i)).toBeInTheDocument();
    expect(screen.getByText(/Retrieved Evidence Sources \(2\)/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Master Circular for Investment Advisers/i).length).toBeGreaterThanOrEqual(1);
  });
});
