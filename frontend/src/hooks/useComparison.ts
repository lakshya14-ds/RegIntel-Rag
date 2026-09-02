/**
 * Hook for executing regulatory document comparison.
 */

import { useState, useCallback, useRef } from 'react';
import { CompareRequest, CompareResponse } from '../types/api';
import { apiClient } from '../api/client';
import { AppError } from '../utils/errors';

export function useComparison() {
  const [data, setData] = useState<CompareResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<AppError | null>(null);
  const [lastRequest, setLastRequest] = useState<CompareRequest | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const compare = useCallback(async (req: CompareRequest) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);
    setLastRequest(req);

    try {
      const response = await apiClient.compareDocuments(req, 60000, controller.signal);
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
      compare(lastRequest);
    }
  }, [lastRequest, compare]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return {
    data,
    isLoading,
    error,
    compare,
    retry,
    reset,
    lastRequest,
  };
}
