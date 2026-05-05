import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { rangeToDays } from './analytics.js';

describe('rangeToDays', () => {
  beforeAll(() => {
    // Pin "today" to a stable UTC date so derived days are deterministic.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-06T12:00:00Z'));
  });
  afterAll(() => {
    vi.useRealTimers();
  });

  it('maps fixed presets to days', () => {
    expect(rangeToDays('7d')).toBe(7);
    expect(rangeToDays('30d')).toBe(30);
    expect(rangeToDays('90d')).toBe(90);
  });

  it('defaults to 30 for unknown / null', () => {
    expect(rangeToDays(null)).toBe(30);
    expect(rangeToDays('')).toBe(30);
    expect(rangeToDays('garbage')).toBe(30);
  });

  it('parses since:YYYY-MM-DD into days from that date through today inclusive', () => {
    // From 2026-05-01 → 2026-05-06 = 6 days inclusive
    expect(rangeToDays('since:2026-05-01')).toBe(6);
    // Same day → 1 day
    expect(rangeToDays('since:2026-05-06')).toBe(1);
  });

  it('clamps to 1..365', () => {
    expect(rangeToDays('since:2026-05-07')).toBe(1); // future date → clamp to 1
    expect(rangeToDays('since:2024-01-01')).toBe(365); // very old → clamp to 365
  });

  it('falls back to 30 for malformed since: tokens', () => {
    expect(rangeToDays('since:not-a-date')).toBe(30);
    expect(rangeToDays('since:')).toBe(30);
  });
});
