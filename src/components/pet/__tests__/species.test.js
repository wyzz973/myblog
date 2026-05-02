import { describe, it, expect } from 'vitest';
import { SPECIES, RARITY_ORDER, STAT_KEYS, byRarity, rarityStars } from '../species.js';

describe('SPECIES', () => {
  it('has 27 entries (18 from buddy-editor + 4 first-batch legendary + 4 cute round 2)', () => {
    expect(Object.keys(SPECIES).length).toBe(27);
  });

  it('each entry has color, rarity, frames (3 frames, 5 lines each, all 12 chars wide)', () => {
    for (const [key, sp] of Object.entries(SPECIES)) {
      expect(sp.color, key).toMatch(/^#[0-9a-f]{3,8}$/i);
      expect(RARITY_ORDER, key).toContain(sp.rarity);
      expect(sp.personality, key).toEqual(expect.any(String));
      expect(sp.trait, key).toEqual(expect.any(String));
      expect(sp.stats, key).toBeTruthy();
      for (const stat of STAT_KEYS) {
        expect(sp.stats[stat], `${key}: ${stat}`).toBeGreaterThanOrEqual(0);
        expect(sp.stats[stat], `${key}: ${stat}`).toBeLessThanOrEqual(100);
      }
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

  it('rarityStars mirrors the buddy editor five-star rarity scale', () => {
    expect(rarityStars('common')).toBe('★');
    expect(rarityStars('legendary')).toBe('★★★★★');
  });
});
