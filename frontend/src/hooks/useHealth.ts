/**
 * Hook for checking and polling system health.
 */

import { useState, useEffect, useCallback } from 'react';
import { HealthResponse } from '../types/api';
import { apiClient } from '../api/client';

export function useHealth(autoPoll: boolean = false, pollIntervalMs: number = 30000) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.healthCheck();
      setHealth(res);
      return res;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Backend unavailable';
      setError(msg);
      setHealth({
        status: 'unavailable',
        mongodb: false,
        embedding_service: false,
      });
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    if (!autoPoll) return;

    const interval = setInterval(() => {
      checkHealth();
    }, pollIntervalMs);

    return () => clearInterval(interval);
  }, [checkHealth, autoPoll, pollIntervalMs]);

  return { health, isLoading, error, refetch: checkHealth };
}
