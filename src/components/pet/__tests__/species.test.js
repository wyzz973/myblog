// Tests the species catalogue loader (Task 21e).
//
// The catalogue used to live as a hardcoded JS object — these tests
// confirmed shape. Now the catalogue comes from /api/pet/species, so we
// mount a fetch mock and assert that loadSpecies hydrates SPECIES with the
// expected adapter shape (legacy trait/personality/description fields).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  RARITY_ORDER,
  STAT_KEYS,
  SPECIES,
  SPECIES_BEHAVIOR,
  byRarity,
  rarityStars,
  loadSpecies,
  isSpeciesLoaded,
  __resetSpeciesForTests,
} from '../species.js';

const SAMPLE_API_RESPONSE = [
  {
    id: 'duck', name: 'Duck', rarity: 'common', color: '#f5d44c',
    trait_zh: 'rubber debugger', personality_zh: 'cheerful', description_zh: 'a duck',
    frames: [['            ', '    __      ', '  <({E} )___  ', '   (  ._>   ', '    `--´    ']],
    behavior: { proactiveLevel: 3, idleFrequency: 'normal', localLines: ['quack'] },
    stats: { debugging: 42, patience: 78, chaos: 30, wisdom: 38, snark: 12 },
    visible: true, sort_order: 0,
    created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-01T00:00:00Z',
  },
  {
    id: 'dragon', name: 'Dragon', rarity: 'legendary', color: '#ff7a5c',
    trait_zh: 'prod firekeeper', personality_zh: 'proud', description_zh: 'breathes fire',
    frames: [['x']],
    behavior: { proactiveLevel: 4, idleFrequency: 'normal', localLines: [] },
    stats: { debugging: 96, patience: 40, chaos: 90, wisdom: 84, snark: 72 },
    visible: true, sort_order: 18,
    created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-01T00:00:00Z',
  },
];

beforeEach(() => {
  __resetSpeciesForTests();
});
afterEach(() => {
  __resetSpeciesForTests();
});

describe('loadSpecies', () => {
  it('hydrates SPECIES with adapter shape (no _zh suffix)', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => SAMPLE_API_RESPONSE }));
    expect(isSpeciesLoaded()).toBe(false);

    await loadSpecies(fetchMock);

    expect(isSpeciesLoaded()).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith('/api/pet/species');
    expect(SPECIES.duck.trait).toBe('rubber debugger');
    expect(SPECIES.duck.personality).toBe('cheerful');
    expect(SPECIES.duck.description).toBe('a duck');
    // Original API fields stay too — useful for the admin editor that wants
    // _zh fields explicitly (it loads via apiPetSpecies, but the adapter
    // shape is forward-compatible).
    expect(SPECIES.duck.trait_zh).toBe('rubber debugger');
    expect(SPECIES.duck.frames).toEqual([['            ', '    __      ', '  <({E} )___  ', '   (  ._>   ', '    `--´    ']]);
  });

  it('memoizes — second call doesn\'t re-fetch', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => SAMPLE_API_RESPONSE }));
    await loadSpecies(fetchMock);
    await loadSpecies(fetchMock);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('populates SPECIES_BEHAVIOR keyed by id, alongside the default fallback', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => SAMPLE_API_RESPONSE }));
    await loadSpecies(fetchMock);
    expect(SPECIES_BEHAVIOR.duck).toEqual({
      proactiveLevel: 3, idleFrequency: 'normal', localLines: ['quack'],
    });
    expect(SPECIES_BEHAVIOR.default).toBeTruthy();
    expect(SPECIES_BEHAVIOR.default.localLines.length).toBeGreaterThan(0);
  });

  it('throws on non-200; allows a future caller to retry', async () => {
    const failing = vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) }));
    await expect(loadSpecies(failing)).rejects.toThrow(/500/);

    // After failure the cache is cleared so the next call retries.
    const ok = vi.fn(async () => ({ ok: true, json: async () => SAMPLE_API_RESPONSE }));
    await loadSpecies(ok);
    expect(ok).toHaveBeenCalledTimes(1);
    expect(SPECIES.duck).toBeTruthy();
  });
});

describe('static exports', () => {
  it('RARITY_ORDER, STAT_KEYS, rarityStars are stable without a fetch', () => {
    expect(RARITY_ORDER).toEqual(['common', 'uncommon', 'rare', 'epic', 'legendary']);
    expect(STAT_KEYS).toEqual(['debugging', 'patience', 'chaos', 'wisdom', 'snark']);
    expect(rarityStars('common')).toBe('★');
    expect(rarityStars('legendary')).toBe('★★★★★');
  });

  it('byRarity returns empty for unloaded catalogue, populated buckets after load', async () => {
    expect(byRarity()).toEqual({});

    const fetchMock = vi.fn(async () => ({ ok: true, json: async () => SAMPLE_API_RESPONSE }));
    await loadSpecies(fetchMock);
    const groups = byRarity();
    expect(Object.keys(groups)).toEqual(['common', 'legendary']);
    expect(groups.common[0].key).toBe('duck');
    expect(groups.legendary[0].key).toBe('dragon');
  });
});
