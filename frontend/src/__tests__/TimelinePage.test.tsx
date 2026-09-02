import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { Timeline } from '../pages/Timeline';
import versionsFixture from './fixtures/document-versions.json';
import latestFixture from './fixtures/latest-docs.json';

describe('Timeline Page Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders timeline graph and predecessor / successor nodes with document param', async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/latest')) {
        return Promise.resolve({
          ok: true,
          json: async () => latestFixture,
        } as Response);
      }
      if (url.includes('/versions')) {
        return Promise.resolve({
          ok: true,
          json: async () => versionsFixture,
        } as Response);
      }
      return Promise.reject(new Error(`Unknown URL: ${url}`));
    });

    render(
      <MemoryRouter
        initialEntries={['/document/sebi_ia_master_circular_2024/timeline']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/document/:documentId/timeline" element={<Timeline />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Version Evolution Timeline/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Predecessor \(Supersedes\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Successor \(Superseded By\)/i)).toBeInTheDocument();
  });
});
