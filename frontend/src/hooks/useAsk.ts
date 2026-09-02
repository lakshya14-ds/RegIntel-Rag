/**
 * Hook for executing grounded regulatory Q&A with cancellation and stage tracking.
 */

import { useState, useCallback, useRef } from 'react';
import { AskRequest, AskResponse, SourceCitationResponse } from '../types/api';
import { apiClient } from '../api/client';
import { AppError } from '../utils/errors';

export function useAsk() {
  const [data, setData] = useState<AskResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<AppError | null>(null);
  const [activeCitation, setActiveCitation] = useState<SourceCitationResponse | null>(null);
  const [lastRequest, setLastRequest] = useState<AskRequest | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const ask = useCallback(async (req: AskRequest) => {
    // Cancel previous request if still running
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);
    setActiveCitation(null);
    setLastRequest(req);

    try {
      const response = await apiClient.askQuestion(req, 60000, controller.signal);
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

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsLoading(false);
    }
  }, []);

  const retry = useCallback(() => {
    if (lastRequest) {
      ask(lastRequest);
    }
  }, [lastRequest, ask]);

  const selectCitation = useCallback(
    (sourceId: number) => {
      if (!data || !data.sources) return;
      const found = data.sources.find((s) => s.source_id === sourceId);
      if (found) {
        setActiveCitation(found);
      }
    },
    [data]
  );

  const closeCitation = useCallback(() => {
    setActiveCitation(null);
  }, []);

  return {
    data,
    isLoading,
    error,
    activeCitation,
    ask,
    cancel,
    retry,
    selectCitation,
    closeCitation,
    lastRequest,
  };
}
