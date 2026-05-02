// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import AsciiPet from './AsciiPet.jsx';

describe('AsciiPet', () => {
  let store;

  beforeEach(() => {
    store = new Map();
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key) => store.get(key) ?? null),
      setItem: vi.fn((key, value) => store.set(key, String(value))),
      removeItem: vi.fn((key) => store.delete(key)),
      clear: vi.fn(() => store.clear()),
    });
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({
        enabled: false,
        assigned_species: 'cat',
        species: 'cat',
        hat: 'none',
        tint: '#7aa7ff',
        visitor_can_change: false,
      }),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not render when public config disables the pet', async () => {
    render(<AsciiPet />);

    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/pet/config'));
    expect(screen.queryByTitle('open settings')).not.toBeInTheDocument();
  });
});
