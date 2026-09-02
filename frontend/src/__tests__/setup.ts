import '@testing-library/jest-dom';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Automatically unmount and cleanup DOM after every test
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
