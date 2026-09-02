import { describe, it, expect, vi, beforeEach } from 'vitest';
import { RegIntelApiClient } from '../api/client';
import healthFixture from './fixtures/health.json';
import askFixture from './fixtures/ask-success.json';
import searchFixture from './fixtures/search-results.json';
import compareFixture from './fixtures/compare-success.json';

describe('RegIntelApiClient', () => {
  let client: RegIntelApiClient;

  beforeEach(() => {
    client = new RegIntelApiClient('http://localhost:8000', 5000);
    vi.restoreAllMocks();
  });

  it('healthCheck calls GET /health and returns health status', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => healthFixture,
    } as Response);

    const res = await client.healthCheck();
    expect(res.status).toBe('ok');
    expect(res.mongodb).toBe(true);
    expect(res.embedding_service).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/health',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('askQuestion sends POST /ask with formatted payload', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => askFixture,
    } as Response);

    const res = await client.askQuestion({
      question: 'What are the fee limits?',
      top_k: 5,
      retrieval_mode: 'hybrid',
    });

    expect(res.answer).toContain('SEBI Investment Advisers regulations');
    expect(res.sources).toHaveLength(2);
    expect(res.query_intent?.category).toBe('Investment Adviser');
    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:8000/ask',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          question: 'What are the fee limits?',
          top_k: 5,
          retrieval_mode: 'hybrid',
        }),
      })
    );
  });

  it('searchDocuments sends POST /search and parses candidates', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => searchFixture,
    } as Response);

    const res = await client.searchDocuments({
      query: 'investment adviser fee cap',
      top_k: 10,
      retrieval_mode: 'hybrid_reranked',
    });

    expect(res.total_results).toBe(2);
    expect(res.results[0].rank).toBe(1);
    expect(res.results[0].score).toBe(0.9542);
  });

  it('compareDocuments sends POST /compare with document IDs', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => compareFixture,
    } as Response);

    const res = await client.compareDocuments({
      document_a_id: 'sebi_ia_circular_2020',
      document_b_id: 'sebi_ia_master_circular_2024',
    });

    expect(res.status).toBe('SUCCESS');
    expect(res.added_count).toBe(1);
    expect(res.modified_count).toBe(1);
    expect(res.removed_count).toBe(1);
    expect(res.unchanged_count).toBe(1);
    expect(res.changes).toHaveLength(4);
  });

  it('handles non-2xx error responses properly by throwing AppError', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ detail: 'Regulatory document not found in corpus.' }),
    } as Response);

    await expect(client.getDocument('invalid_doc_id')).rejects.toThrow(
      'Regulatory document not found in corpus.'
    );
  });
});
