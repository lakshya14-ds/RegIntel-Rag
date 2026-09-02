/**
 * RegIntel REST API Client.
 * Handles typed communication with the FastAPI backend with timeout and error handling.
 */

import {
  HealthResponse,
  AskRequest,
  AskResponse,
  SearchRequest,
  SearchResponse,
  DocumentMetadataResponse,
  DocumentVersionResponse,
  CompareRequest,
  CompareResponse,
} from '../types/api';
import { AppError, parseApiError } from '../utils/errors';

export const DEFAULT_API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';

export class RegIntelApiClient {
  private baseUrl: string;
  private defaultTimeoutMs: number;

  constructor(baseUrl?: string, defaultTimeoutMs: number = 45000) {
    this.baseUrl = (baseUrl || DEFAULT_API_BASE_URL).replace(/\/+$/, '');
    this.defaultTimeoutMs = defaultTimeoutMs;
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    customTimeoutMs?: number
  ): Promise<T> {
    const timeoutMs = customTimeoutMs ?? this.defaultTimeoutMs;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    // If caller provided an external signal, chain it
    if (options.signal) {
      options.signal.addEventListener('abort', () => controller.abort());
    }

    const cleanEndpoint = endpoint.replace(/^\/+/, '');
    const url = `${this.baseUrl}/${cleanEndpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          ...(options.headers || {}),
        },
      });

      if (!response.ok) {
        let errorData: Record<string, unknown> = {};
        try {
          errorData = await response.json();
        } catch {
          // Response body is not JSON
        }

        let message = `HTTP ${response.status}: ${response.statusText}`;
        if (typeof errorData.detail === 'string') {
          message = errorData.detail;
        } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
          message = errorData.detail
            .map((item: Record<string, unknown>) => (typeof item?.msg === 'string' ? item.msg : JSON.stringify(item)))
            .join('; ');
        } else if (typeof errorData.message === 'string') {
          message = errorData.message;
        } else if (typeof errorData.error === 'string') {
          message = errorData.error;
        }

        throw new AppError(message, {
          statusCode: response.status,
          details: errorData.details || errorData,
        });
      }

      return (await response.json()) as T;
    } catch (err) {
      throw parseApiError(err);
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * GET /health - Check system status (MongoDB + Gemini Embedding availability)
   */
  public async healthCheck(signal?: AbortSignal): Promise<HealthResponse> {
    return this.request<HealthResponse>('health', { method: 'GET', signal }, 10000);
  }

  /**
   * POST /ask - Execute grounded regulatory Q&A with citations
   */
  public async askQuestion(
    req: AskRequest,
    customTimeoutMs: number = 60000,
    signal?: AbortSignal
  ): Promise<AskResponse> {
    return this.request<AskResponse>(
      'ask',
      {
        method: 'POST',
        body: JSON.stringify({
          question: req.question.trim(),
          top_k: req.top_k ?? 5,
          retrieval_mode: req.retrieval_mode ?? 'hybrid',
          category: req.category || undefined,
          source: req.source || undefined,
        }),
        signal,
      },
      customTimeoutMs
    );
  }

  /**
   * POST /search - Direct multi-method candidate chunk search
   */
  public async searchDocuments(
    req: SearchRequest,
    signal?: AbortSignal
  ): Promise<SearchResponse> {
    return this.request<SearchResponse>(
      'search',
      {
        method: 'POST',
        body: JSON.stringify({
          query: req.query.trim(),
          top_k: req.top_k ?? 10,
          retrieval_mode: req.retrieval_mode ?? 'hybrid',
          category: req.category || undefined,
          source: req.source || undefined,
        }),
        signal,
      },
      30000
    );
  }

  /**
   * GET /latest - List latest regulatory circulars/documents
   */
  public async getLatestDocuments(
    params?: {
      source?: string | null;
      category?: string | null;
      limit?: number;
    },
    signal?: AbortSignal
  ): Promise<DocumentMetadataResponse[]> {
    const queryParams = new URLSearchParams();
    if (params?.source && params.source !== 'All') {
      queryParams.set('source', params.source);
    }
    if (params?.category && params.category !== 'All') {
      queryParams.set('category', params.category);
    }
    if (params?.limit) {
      queryParams.set('limit', String(params.limit));
    }

    const qs = queryParams.toString();
    const path = qs ? `latest?${qs}` : 'latest';
    return this.request<DocumentMetadataResponse[]>(path, { method: 'GET', signal }, 20000);
  }

  /**
   * GET /document/{document_id} - Retrieve detailed document metadata
   */
  public async getDocument(
    documentId: string,
    signal?: AbortSignal
  ): Promise<DocumentMetadataResponse> {
    return this.request<DocumentMetadataResponse>(
      `document/${encodeURIComponent(documentId.trim())}`,
      { method: 'GET', signal },
      20000
    );
  }

  /**
   * GET /document/{document_id}/versions - Retrieve document version graph & timeline
   */
  public async getDocumentVersions(
    documentId: string,
    signal?: AbortSignal
  ): Promise<DocumentVersionResponse> {
    return this.request<DocumentVersionResponse>(
      `document/${encodeURIComponent(documentId.trim())}/versions`,
      { method: 'GET', signal },
      20000
    );
  }

  /**
   * POST /compare - Compare two regulatory circulars
   */
  public async compareDocuments(
    req: CompareRequest,
    customTimeoutMs: number = 60000,
    signal?: AbortSignal
  ): Promise<CompareResponse> {
    return this.request<CompareResponse>(
      'compare',
      {
        method: 'POST',
        body: JSON.stringify({
          document_a_id: req.document_a_id.trim(),
          document_b_id: req.document_b_id.trim(),
        }),
        signal,
      },
      customTimeoutMs
    );
  }
}

// Global default singleton instance
export const apiClient = new RegIntelApiClient();
