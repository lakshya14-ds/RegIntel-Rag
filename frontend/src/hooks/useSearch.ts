/**
 * Hook for executing candidate document/clause search.
 */

import { useState, useCallback, useRef } from 'react';
import { SearchRequest, SearchResponse } from '../types/api';
import { apiClient } from '../api/client';
import { AppError } from '../utils/errors';

export function useSearch() {
  const [data, setData] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<AppError | null>(null);
  const [lastRequest, setLastRequest] = useState<SearchRequest | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const search = useCallback(async (req: SearchRequest) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);
    setLastRequest(req);

    try {
      const response = await apiClient.searchDocuments(req, controller.signal);
      setData(response);
      return response;
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return null;
      }
      const appErr = err instanceof AppError ? err : new AppError(String(err));
      setError(appErr);
      return null;
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, []);

  const retry = useCallback(() => {
    if (lastRequest) {
      search(lastRequest);
    }
  }, [lastRequest, search]);

  return {
    data,
    isLoading,
    error,
    search,
    retry,
    lastRequest,
  };
}
