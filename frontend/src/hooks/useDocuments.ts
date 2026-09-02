/**
 * Hooks for fetching latest documents, single document metadata, and version graph.
 */

import { useState, useCallback, useEffect } from 'react';
import { DocumentMetadataResponse, DocumentVersionResponse } from '../types/api';
import { apiClient } from '../api/client';
import { AppError } from '../utils/errors';

export function useLatestDocuments(initialFilters?: { source?: string; category?: string; limit?: number }) {
  const [data, setData] = useState<DocumentMetadataResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<AppError | null>(null);

  const fetchLatest = useCallback(
    async (filters?: { source?: string; category?: string; limit?: number }) => {
      setIsLoading(true);
      setError(null);
      try {
        const docs = await apiClient.getLatestDocuments(filters);
        setData(docs);
        return docs;
      } catch (err) {
        const appErr = err instanceof AppError ? err : new AppError(String(err));
        setError(appErr);
        return [];
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const filterSource = initialFilters?.source;
  const filterCategory = initialFilters?.category;
  const filterLimit = initialFilters?.limit;

  useEffect(() => {
    fetchLatest({ source: filterSource, category: filterCategory, limit: filterLimit });
  }, [fetchLatest, filterSource, filterCategory, filterLimit]);

  return {
    data,
    isLoading,
    error,
    refetch: fetchLatest,
  };
}

export function useDocument(documentId?: string) {
  const [data, setData] = useState<DocumentMetadataResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<AppError | null>(null);

  const fetchDoc = useCallback(async (id: string) => {
    if (!id.trim()) return null;
    setIsLoading(true);
    setError(null);
    try {
      const doc = await apiClient.getDocument(id);
      setData(doc);
      return doc;
    } catch (err) {
      const appErr = err instanceof AppError ? err : new AppError(String(err));
      setError(appErr);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (documentId) {
      fetchDoc(documentId);
    }
  }, [documentId, fetchDoc]);

  return {
    data,
    isLoading,
    error,
    refetch: () => documentId && fetchDoc(documentId),
  };
}

export function useDocumentVersions(documentId?: string) {
  const [data, setData] = useState<DocumentVersionResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<AppError | null>(null);

  const fetchVersions = useCallback(async (id: string) => {
    if (!id.trim()) return null;
    setIsLoading(true);
    setError(null);
    try {
      const ver = await apiClient.getDocumentVersions(id);
      setData(ver);
      return ver;
    } catch (err) {
      const appErr = err instanceof AppError ? err : new AppError(String(err));
      setError(appErr);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (documentId) {
      fetchVersions(documentId);
    }
  }, [documentId, fetchVersions]);

  return {
    data,
    isLoading,
    error,
    refetch: () => documentId && fetchVersions(documentId),
  };
}
