import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// Unmount any rendered React tree after each test so multiple it() blocks
// in the same file don't pile up duplicates of the same DOM.
afterEach(() => {
  cleanup();
});
