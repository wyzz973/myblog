// Pet species catalogue (Task 21e).
//
// Static rarity tables and helpers stay here; the actual catalogue is fetched
// from /api/pet/species at app boot (see src/main.jsx) and cached for the
// lifetime of the SPA. The owner edits the catalogue from /admin/pet?tab=species.
//
// SPECIES and SPECIES_BEHAVIOR are intentionally exported as live mutable
// objects so existing imports keep working — loadSpecies() fills them in
// place. Components that need to react to load completion should call the
// useSpecies() hook instead of reading the bare objects (which are empty
// until the fetch resolves).

import { useEffect, useState } from 'react';

export const RARITY_ORDER = ['common', 'uncommon', 'rare', 'epic', 'legendary'];

export const RARITY_COLOR = {
  common:    '#9aa6b3',
  uncommon:  '#7dbf8e',
  rare:      '#5c9ddc',
  epic:      '#b89cf0',
  legendary: '#f5b44c',
};

export const RARITY_STARS = {
  common: '★',
  uncommon: '★★',
  rare: '★★★',
  epic: '★★★★',
  legendary: '★★★★★',
};

export const STAT_KEYS = ['debugging', 'patience', 'chaos', 'wisdom', 'snark'];

// Mapping from pet state to {E} substitute character.
export const STATE_EYE = {
  idle:         '·',
  thinking:     '°',
  typing:       '·',
  building:     'o',
  juggling:     '^',
  conducting:   '^',
  error:        '×',
  happy:        '✦',
  notification: '>',
  sweeping:     '-',
  carrying:     'o',
  sleeping:     '-',
  yawning:      '>',
  startled:     '◉',
};

export function rarityStars(rarity) {
  return RARITY_STARS[rarity] || RARITY_STARS.common;
}

// Mutable catalogues — loadSpecies() mutates these in place. Importers get a
// live binding so they always see the populated state once the fetch lands.
export const SPECIES = {};
export const SPECIES_BEHAVIOR = {
  default: {
    proactiveLevel: 3,
    idleFrequency: 'normal',
    localLines: ['要我看看这里吗？', '我在这儿。'],
  },
};

export function byRarity() {
  const out = {};
  for (const r of RARITY_ORDER) out[r] = [];
  for (const [key, sp] of Object.entries(SPECIES)) {
    if (out[sp.rarity]) out[sp.rarity].push({ key, ...sp });
    else (out[sp.rarity] = [{ key, ...sp }]);
  }
  for (const r of RARITY_ORDER) {
    if (out[r] && out[r].length === 0) delete out[r];
  }
  return out;
}

let _loadPromise = null;
const _subscribers = new Set();

function _adaptRow(row) {
  // Frontend consumers historically used trait/personality/description
  // (no _zh suffix). The backend stores them as *_zh; map here so AsciiPet
  // / PetPersonas keep their existing field reads.
  return {
    ...row,
    trait: row.trait_zh ?? '',
    personality: row.personality_zh ?? '',
    description: row.description_zh ?? '',
  };
}

/**
 * Fetch /api/pet/species and populate SPECIES + SPECIES_BEHAVIOR in place.
 * Memoized: subsequent calls return the cached promise. Call this once at
 * app boot so the catalogue is ready by the time any pet UI mounts.
 */
export function loadSpecies(fetchImpl = globalThis.fetch) {
  if (_loadPromise) return _loadPromise;
  _loadPromise = (async () => {
    const resp = await fetchImpl('/api/pet/species');
    if (!resp.ok) {
      throw new Error(`/api/pet/species ${resp.status}`);
    }
    const rows = await resp.json();
    for (const row of rows) {
      SPECIES[row.id] = _adaptRow(row);
      // Behavior keys are camelCase from the API (matches the legacy hardcode
      // shape), so we can store as-is.
      SPECIES_BEHAVIOR[row.id] = row.behavior || {};
    }
    for (const fn of _subscribers) {
      try { fn(); } catch { /* subscriber errors don't block hydration */ }
    }
    return { species: SPECIES, behavior: SPECIES_BEHAVIOR };
  })();
  // If the fetch fails, allow a future caller to retry by clearing the cache.
  _loadPromise.catch(() => { _loadPromise = null; });
  return _loadPromise;
}

export function isSpeciesLoaded() {
  return Object.keys(SPECIES).length > 0;
}

/**
 * React hook: kicks off loadSpecies() on first mount and re-renders when the
 * catalogue lands. Returns `{ ready, species, behavior }`. Components that
 * cannot render without species should branch on `ready`.
 */
export function useSpecies() {
  const [ready, setReady] = useState(isSpeciesLoaded);
  useEffect(() => {
    if (isSpeciesLoaded()) {
      setReady(true);
      return undefined;
    }
    let alive = true;
    const onLoad = () => { if (alive) setReady(true); };
    _subscribers.add(onLoad);
    loadSpecies().catch(() => { /* surfaced by isSpeciesLoaded staying false */ });
    return () => { alive = false; _subscribers.delete(onLoad); };
  }, []);
  return { ready, species: SPECIES, behavior: SPECIES_BEHAVIOR };
}

// Test-only escape hatch: reset the loader memoization + catalogue so each
// test starts from the same state. Not exported to production code paths.
export function __resetSpeciesForTests() {
  for (const k of Object.keys(SPECIES)) delete SPECIES[k];
  for (const k of Object.keys(SPECIES_BEHAVIOR)) {
    if (k !== 'default') delete SPECIES_BEHAVIOR[k];
  }
  _loadPromise = null;
  _subscribers.clear();
}
