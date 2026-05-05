import { describe, it, expect } from 'vitest';
import { parseOklch, formatOklch, THEME_DEFAULTS } from './oklch.js';

describe('parseOklch', () => {
  it('reads L%, C, H', () => {
    expect(parseOklch('oklch(82% 0.17 152)')).toEqual({ l: 82, c: 0.17, h: 152 });
  });
  it('tolerates extra whitespace and the alpha slash', () => {
    expect(parseOklch('  oklch( 70%  0.2  25 / 0.5 )  '))
      .toEqual({ l: 70, c: 0.2, h: 25 });
  });
  it('returns null on non-oklch input', () => {
    expect(parseOklch('#ff0000')).toBeNull();
    expect(parseOklch('oklch( foo )')).toBeNull();
    expect(parseOklch(null)).toBeNull();
    expect(parseOklch(undefined)).toBeNull();
  });
  it('clamps absurd values', () => {
    expect(parseOklch('oklch(120% 0.9 400)')).toEqual({ l: 100, c: 0.4, h: 360 });
  });
});

describe('formatOklch', () => {
  it('emits canonical L% C H with rounded chroma', () => {
    expect(formatOklch({ l: 82, c: 0.17, h: 152 })).toBe('oklch(82% 0.17 152)');
  });
  it('rounds chroma to 3 decimals and hue to integer', () => {
    expect(formatOklch({ l: 82.55, c: 0.17345, h: 152.6 })).toBe('oklch(82.6% 0.173 153)');
  });
  it('round-trips through parse → format', () => {
    const parsed = parseOklch('oklch(72% 0.18 295)');
    expect(formatOklch(parsed)).toBe('oklch(72% 0.18 295)');
  });
});

describe('THEME_DEFAULTS', () => {
  it('matches what the public utils/accent.js seeds', () => {
    expect(THEME_DEFAULTS.accent_color).toBe('oklch(82% 0.17 152)');
    expect(THEME_DEFAULTS.accent2_color).toBe('oklch(80% 0.15 70)');
    expect(THEME_DEFAULTS.violet_color).toBe('oklch(72% 0.18 295)');
    expect(THEME_DEFAULTS.danger_color).toBe('oklch(70% 0.2 25)');
  });
});
