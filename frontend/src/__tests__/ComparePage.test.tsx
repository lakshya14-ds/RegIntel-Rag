import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Compare } from '../pages/Compare';
import compareFixture from './fixtures/compare-success.json';
import latestFixture from './fixtures/latest-docs.json';

describe('Compare Page Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders compare selectors and executes comparison displaying delta metrics', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/latest')) {
        return Promise.resolve({
          ok: true,
          json: async () => latestFixture,
        } as Response);
      }
      if (url.includes('/compare')) {
        return Promise.resolve({
          ok: true,
          json: async () => compareFixture,
        } as Response);
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Compare />
      </BrowserRouter>
    );

    // Click sample pair button
    const sampleBtn = screen.getByText(/Load Sample IA Pair/i);
    fireEvent.click(sampleBtn);

    // Wait for comparison result
    await waitFor(() => {
      expect(screen.getByText(/Executive Change Summary/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/OLDER DOCUMENT \(Baseline\)/i)).toBeInTheDocument();
    expect(screen.getByText(/NEWER DOCUMENT \(Revised\)/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Fee Schedule and Limits/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Cybersecurity and Disaster Recovery/i)).toBeInTheDocument();
  });
});
