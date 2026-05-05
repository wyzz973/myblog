import { describe, it, expect, vi, beforeEach } from 'vitest';

// In-memory localStorage shim — jsdom's default is awkward in this env.
const _ls = new Map();
const memLocalStorage = {
  getItem: (k) => (_ls.has(k) ? _ls.get(k) : null),
  setItem: (k, v) => { _ls.set(k, String(v)); },
  removeItem: (k) => { _ls.delete(k); },
  clear: () => { _ls.clear(); },
};
Object.defineProperty(globalThis, 'localStorage', {
  value: memLocalStorage,
  configurable: true,
});

const { saveDraft, loadDraft, clearDraft, draftIsNewerThan } = await import('./draftStore.js');

beforeEach(() => {
  _ls.clear();
});

describe('draftStore', () => {
  it('saves + loads roundtrips with timestamp', () => {
    saveDraft('vps', '# hello', 1000);
    expect(loadDraft('vps')).toEqual({ markdown: '# hello', savedAt: 1000 });
  });

  it('returns null for unknown id', () => {
    expect(loadDraft('nope')).toBeNull();
  });

  it('clearDraft removes the entry', () => {
    saveDraft('a', 'x');
    expect(loadDraft('a')).not.toBeNull();
    clearDraft('a');
    expect(loadDraft('a')).toBeNull();
  });

  it('uses __new__ key when id is null/undefined', () => {
    saveDraft(null, 'fresh', 42);
    expect(loadDraft(null)?.markdown).toBe('fresh');
    expect(loadDraft(undefined)?.markdown).toBe('fresh');
  });

  it('survives garbage in storage by returning null', () => {
    _ls.set('bl.admin.draft.x', '{not valid json');
    expect(loadDraft('x')).toBeNull();
  });
});

describe('draftIsNewerThan', () => {
  it('true when no server timestamp', () => {
    expect(draftIsNewerThan({ savedAt: 100 }, null)).toBe(true);
    expect(draftIsNewerThan({ savedAt: 100 }, undefined)).toBe(true);
  });
  it('compares numeric ms timestamps', () => {
    expect(draftIsNewerThan({ savedAt: 200 }, 100)).toBe(true);
    expect(draftIsNewerThan({ savedAt: 50 }, 100)).toBe(false);
  });
  it('parses ISO server timestamps', () => {
    const iso = new Date(1000).toISOString();
    expect(draftIsNewerThan({ savedAt: 2000 }, iso)).toBe(true);
    expect(draftIsNewerThan({ savedAt: 500 }, iso)).toBe(false);
  });
  it('false when draft missing', () => {
    expect(draftIsNewerThan(null, 100)).toBe(false);
  });
});
