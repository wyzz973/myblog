// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { act } from 'react';
import AsciiPet, { IDLE_MONOLOGUE_MS } from './AsciiPet.jsx';

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
        enabled: true,
        assigned_species: 'cat',
        species: 'cat',
        hat: 'none',
        tint: '#7aa7ff',
        visitor_can_change: false,
      }),
    })));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('does not render when public config disables the pet', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        enabled: false,
        assigned_species: 'cat',
        species: 'cat',
        hat: 'none',
        tint: '#7aa7ff',
        visitor_can_change: false,
      }),
    });
    render(<AsciiPet />);

    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/pet/config'));
    expect(screen.queryByTitle('open settings')).not.toBeInTheDocument();
  });

  it('opens the pet profile on long press without summoning', async () => {
    render(<AsciiPet />);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/pet/config'));

    vi.useFakeTimers();
    const pet = document.querySelector('.clawd-pet');
    fireEvent.pointerDown(pet, { pointerId: 1, clientX: 120, clientY: 120 });
    act(() => vi.advanceTimersByTime(700));
    fireEvent.pointerUp(pet, { pointerId: 1, clientX: 120, clientY: 120 });

    expect(screen.getByRole('dialog', { name: /cat profile/i })).toBeInTheDocument();
    expect(screen.getByText('cat')).toBeInTheDocument();
    expect(screen.getByText('common')).toBeInTheDocument();
    expect(screen.getByText('debugging')).toBeInTheDocument();
    expect(screen.getByText('snark')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  it('closes the pet profile from outside, Escape, or tapping the pet without summoning', async () => {
    render(
      <>
        <button type="button">outside</button>
        <AsciiPet />
      </>,
    );
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/pet/config'));

    vi.useFakeTimers();
    const pet = document.querySelector('.clawd-pet');

    fireEvent.pointerDown(pet, { pointerId: 1, clientX: 120, clientY: 120 });
    act(() => vi.advanceTimersByTime(700));
    fireEvent.pointerUp(pet, { pointerId: 1, clientX: 120, clientY: 120 });
    expect(screen.getByRole('dialog', { name: /cat profile/i })).toBeInTheDocument();

    fireEvent.pointerDown(screen.getByRole('button', { name: 'outside' }));
    expect(screen.queryByRole('dialog', { name: /cat profile/i })).not.toBeInTheDocument();

    fireEvent.pointerDown(pet, { pointerId: 2, clientX: 120, clientY: 120 });
    act(() => vi.advanceTimersByTime(700));
    fireEvent.pointerUp(pet, { pointerId: 2, clientX: 120, clientY: 120 });
    expect(screen.getByRole('dialog', { name: /cat profile/i })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: /cat profile/i })).not.toBeInTheDocument();

    fireEvent.pointerDown(pet, { pointerId: 3, clientX: 120, clientY: 120 });
    act(() => vi.advanceTimersByTime(700));
    fireEvent.pointerUp(pet, { pointerId: 3, clientX: 120, clientY: 120 });
    expect(screen.getByRole('dialog', { name: /cat profile/i })).toBeInTheDocument();

    fireEvent.pointerDown(pet, { pointerId: 4, clientX: 120, clientY: 120 });
    fireEvent.pointerUp(pet, { pointerId: 4, clientX: 120, clientY: 120 });
    expect(screen.queryByRole('dialog', { name: /cat profile/i })).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(300));
    expect(fetch).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  it('auto-summons an idle monologue after a quiet window', async () => {
    vi.useFakeTimers();
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        enabled: true,
        assigned_species: 'cat',
        species: 'cat',
        hat: 'none',
        tint: '#7aa7ff',
        visitor_can_change: false,
      }),
    });
    fetch.mockResolvedValueOnce({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn()
            .mockResolvedValueOnce({
              value: new TextEncoder().encode('data: {"type":"fallback","text":"idle meow","source":"fallback"}\n\n'),
              done: false,
            })
            .mockResolvedValueOnce({ value: undefined, done: true }),
        }),
      },
    });

    render(<AsciiPet />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(fetch).toHaveBeenCalledWith('/api/pet/config');

    await act(async () => {
      vi.advanceTimersByTime(IDLE_MONOLOGUE_MS + 1200);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetch).toHaveBeenCalledTimes(2);
    const summonCall = fetch.mock.calls[1];
    expect(summonCall[0]).toBe('/api/pet/summon/stream');
    expect(JSON.parse(summonCall[1].body)).toEqual({ mode: 'idle_monologue' });
    expect(screen.getByText('idle meow')).toBeInTheDocument();
  });
});
