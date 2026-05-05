// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { act } from 'react';
import AsciiPet, { IDLE_MONOLOGUE_MS } from './AsciiPet.jsx';
import { SPECIES, __resetSpeciesForTests } from './pet/species.js';

// In production the species catalogue is hydrated from /api/pet/species at
// app boot. The component-level test focuses on UI behavior, so we pre-fill
// SPECIES.cat with a stub that satisfies AsciiPet's render contract (frames
// + stats + rarity). Keeps the fetch-count assertions in the existing tests
// stable — only /api/pet/config is fetched.
const CAT_FIXTURE = {
  id: 'cat', name: 'Cat', rarity: 'common', color: '#e0a96d',
  trait: 'terminal familiar', personality: 'curious',
  description: 'a classic coding companion',
  frames: [
    ['            ', '   /\\__/\\   ', '  ( {E}  {E} )  ', '  (  ω   )  ', '  (")__(")  '],
    ['            ', '   /\\__/\\   ', '  ( {E}  {E} )  ', '  (  ω   )  ', '  (")__(")~ '],
    ['            ', '   /\\--/\\   ', '  ( {E}  {E} )  ', '  (  ω   )  ', '  (")__(")  '],
  ],
  behavior: {}, stats: { debugging: 62, patience: 64, chaos: 30, wisdom: 38, snark: 44 },
  visible: true, sort_order: 0,
};

describe('AsciiPet', () => {
  let store;

  beforeEach(() => {
    __resetSpeciesForTests();
    Object.assign(SPECIES, { cat: CAT_FIXTURE });
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
    __resetSpeciesForTests();
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
      vi.advanceTimersByTime(IDLE_MONOLOGUE_MS);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetch).toHaveBeenCalledTimes(2);
    const summonCall = fetch.mock.calls[1];
    expect(summonCall[0]).toBe('/api/pet/summon/stream');
    expect(JSON.parse(summonCall[1].body)).toEqual({ mode: 'idle_monologue' });
    expect(screen.getByText('idle meow')).toBeInTheDocument();
  });

  it('opens chat input, sends message with context, and closes on Escape', async () => {
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
              value: new TextEncoder().encode('data: {"type":"fallback","text":"chat ok","source":"fallback"}\n\n'),
              done: false,
            })
            .mockResolvedValueOnce({ value: undefined, done: true }),
        }),
      },
    });
    window.__petScene = () => ({ page_type: 'post', read_progress: 42 });

    render(<AsciiPet />);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/pet/config'));

    fireEvent.click(screen.getByTitle('chat with pet'));
    const input = screen.getByLabelText('message pet');
    fireEvent.change(input, { target: { value: '这段怎么理解？' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    const body = JSON.parse(fetch.mock.calls[1][1].body);
    expect(body.mode).toBe('free_chat');
    expect(body.message).toBe('这段怎么理解？');
    expect(body.client_context.read_progress).toBe(42);
    expect(screen.getByText('chat ok')).toBeInTheDocument();

    fireEvent.click(screen.getByTitle('chat with pet'));
    expect(screen.getByLabelText('message pet')).toBeInTheDocument();
    fireEvent.keyDown(screen.getByLabelText('message pet'), { key: 'Escape' });
    expect(screen.queryByLabelText('message pet')).not.toBeInTheDocument();
  });

  it('closes chat input from the x button without entering quiet mode', async () => {
    render(<AsciiPet />);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/pet/config'));

    fireEvent.click(screen.getByTitle('chat with pet'));
    const input = screen.getByLabelText('message pet');
    fireEvent.change(input, { target: { value: 'draft' } });
    fireEvent.click(screen.getByTitle('close chat'));

    expect(screen.queryByLabelText('message pet')).not.toBeInTheDocument();
    expect(screen.queryByText('安静 30 分钟。')).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('shows local proactive article-finished prompt and sends article_finished only after click', async () => {
    vi.useFakeTimers();
    window.__petScene = () => ({
      page_type: 'post',
      post_id: 'pet-test',
      read_progress: 99,
      recent_action: 'reached_end',
    });
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
              value: new TextEncoder().encode('data: {"type":"fallback","text":"done read","source":"fallback"}\n\n'),
              done: false,
            })
            .mockResolvedValueOnce({ value: undefined, done: true }),
        }),
      },
    });

    render(<AsciiPet />);
    await act(async () => { await Promise.resolve(); });
    await act(async () => {
      vi.advanceTimersByTime(1600);
      await Promise.resolve();
    });

    expect(screen.getByText('要我总结一下吗？')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    await act(async () => {
      fireEvent.click(screen.getByText('要我总结一下吗？'));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(JSON.parse(fetch.mock.calls[1][1].body).mode).toBe('article_finished');
    vi.useRealTimers();
  });
});
