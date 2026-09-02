import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Search } from '../pages/Search';
import searchFixture from './fixtures/search-results.json';

describe('Search Page Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders search input and filters', () => {
    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Search />
      </BrowserRouter>
    );

    expect(
      screen.getByPlaceholderText(/Enter compliance search terms/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Retrieval Algorithm/i)).toBeInTheDocument();
  });

  it('executes search and displays candidate chunk cards', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => searchFixture,
    } as Response);

    render(
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Search />
      </BrowserRouter>
    );

    const input = screen.getByPlaceholderText(/Enter compliance search terms/i);
    const searchBtn = screen.getByRole('button', { name: /^Search$/i });

    fireEvent.change(input, { target: { value: 'investment adviser fee cap' } });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(screen.getByText(/Retrieved 2 Evidence Chunks/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Rank #1/i)).toBeInTheDocument();
    expect(
      screen.getByText(/The maximum fees that may be charged by an Investment Adviser/i)
    ).toBeInTheDocument();
  });
});
