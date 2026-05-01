import { describe, it, expect } from 'vitest';
import { SPECIES, RARITY_ORDER, byRarity } from '../species.js';

describe('SPECIES', () => {
  it('has at least 18 entries (18 from buddy-editor + 4 legendary in Task 14)', () => {
    expect(Object.keys(SPECIES).length).toBeGreaterThanOrEqual(18);
  });

  it('each entry has color, rarity, frames (3 frames, 5 lines each, all 12 chars wide)', () => {
    for (const [key, sp] of Object.entries(SPECIES)) {
      expect(sp.color, key).toMatch(/^#[0-9a-f]{3,8}$/i);
      expect(RARITY_ORDER, key).toContain(sp.rarity);
      expect(sp.frames, key).toHaveLength(3);
      for (const frame of sp.frames) {
        expect(frame, key).toHaveLength(5);
        for (const line of frame) {
          // Width including {E} placeholder normalized: substitute {E} with X for length check
          const w = line.replace(/\{E\}/g, 'X').length;
          expect(w, `${key}: line "${line}"`).toBe(12);
        }
      }
    }
  });

  it('byRarity groups species by rarity preserving RARITY_ORDER', () => {
    const groups = byRarity();
    const orderedKeys = Object.keys(groups);
    expect(orderedKeys).toEqual(RARITY_ORDER.filter((r) => groups[r].length > 0));
  });
});
