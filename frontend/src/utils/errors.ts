/**
 * Error Normalization Utilities for RegIntel Frontend.
 */

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export class AppError extends Error {
  public statusCode?: number;
  public details?: unknown;
  public isTimeout?: boolean;
  public isNetwork?: boolean;

  constructor(message: string, options?: { statusCode?: number; details?: unknown; isTimeout?: boolean; isNetwork?: boolean }) {
    super(message);
    this.name = 'AppError';
    this.statusCode = options?.statusCode;
    this.details = options?.details;
    this.isTimeout = options?.isTimeout;
    this.isNetwork = options?.isNetwork;
  }
}

export function parseApiError(error: unknown): AppError {
  if (error instanceof AppError) {
    return error;
  }

  if (error instanceof DOMException && error.name === 'AbortError') {
    return new AppError('The request timed out. The server took too long to respond.', {
      isTimeout: true,
      statusCode: 408,
    });
  }

  if (error instanceof TypeError && error.message.includes('fetch')) {
    return new AppError('Unable to connect to RegIntel FastAPI backend. Please ensure the server is running on port 8000.', {
      isNetwork: true,
      statusCode: 503,
    });
  }

  if (error instanceof Error) {
    return new AppError(error.message);
  }

  return new AppError('An unexpected error occurred while communicating with the regulatory service.');
}
