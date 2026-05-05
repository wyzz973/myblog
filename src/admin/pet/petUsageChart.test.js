import { describe, it, expect } from 'vitest';
import {
  buildBars,
  buildPieSlices,
  groupByDay,
  groupByMode,
  legendFromData,
  modeColor,
  SOURCE_COLORS,
  SOURCE_LABELS,
} from './petUsageChart.js';

const ROWS = [
  { day: '2026-05-04', mode: 'greet', source: 'provider', calls: 5, estimated_total_tokens: 1000 },
  { day: '2026-05-04', mode: 'greet', source: 'cache_hit', calls: 3, estimated_total_tokens: 0 },
  { day: '2026-05-03', mode: 'summary', source: 'provider', calls: 2, estimated_total_tokens: 400 },
  { day: '2026-05-03', mode: 'summary', source: 'unknown_kind', calls: 1, estimated_total_tokens: 100 },
];

describe('groupByDay', () => {
  it('aggregates per-day per-source totals and sorts ascending', () => {
    const daily = groupByDay(ROWS);
    expect(daily.map((d) => d.day)).toEqual(['2026-05-03', '2026-05-04']);
    expect(daily[1].sources).toEqual({ provider: 5, cache_hit: 3 });
    // Unknown source bucketed as "other"
    expect(daily[0].sources.other).toBe(1);
    expect(daily[0].sources.provider).toBe(2);
  });

  it('handles empty / null inputs without crashing', () => {
    expect(groupByDay([])).toEqual([]);
    expect(groupByDay(null)).toEqual([]);
    expect(groupByDay([{ source: 'provider', calls: 0 }])).toEqual([]);
  });
});

describe('buildBars', () => {
  const daily = groupByDay(ROWS);
  const bars = buildBars(daily, { width: 400, height: 120, padX: 20, padY: 12 });

  it('produces one bar per day in chronological order', () => {
    expect(bars).toHaveLength(2);
    expect(bars[0].day).toBe('2026-05-03');
    expect(bars[1].day).toBe('2026-05-04');
  });

  it('segments stacked from bottom and total height fits inside chart area', () => {
    const bar = bars[1]; // 2026-05-04: 5 + 3 = 8 calls
    const innerH = 120 - 12 * 2;
    const totalH = bar.segments.reduce((a, s) => a + s.h, 0);
    expect(Math.abs(totalH - innerH)).toBeLessThan(0.001); // max day fills the chart
    // y-coordinate of each segment is bottom-up
    const ys = bar.segments.map((s) => s.y);
    for (let i = 1; i < ys.length; i++) {
      expect(ys[i]).toBeLessThanOrEqual(ys[i - 1]);
    }
  });

  it('returns total calls per bar', () => {
    expect(bars[0].total).toBe(3); // 2 + 1 on may-03
    expect(bars[1].total).toBe(8); // 5 + 3 on may-04
  });
});

describe('legendFromData', () => {
  it('lists only sources present in the data, in canonical order', () => {
    const daily = groupByDay(ROWS);
    const legend = legendFromData(daily);
    expect(legend.map((e) => e.source)).toEqual(['provider', 'cache_hit', 'other']);
    expect(legend[0].color).toBe(SOURCE_COLORS.provider);
    expect(legend[0].label).toBe(SOURCE_LABELS.provider);
  });

  it('returns empty when no rows', () => {
    expect(legendFromData([])).toEqual([]);
  });
});

describe('groupByMode', () => {
  it('aggregates calls by mode and sorts descending', () => {
    const modes = groupByMode(ROWS);
    // ROWS has greet (provider 5 + cache_hit 3 = 8) and summary (provider 2 + unknown 1 = 3)
    expect(modes.map((m) => m.mode)).toEqual(['greet', 'summary']);
    expect(modes[0].calls).toBe(8);
    expect(modes[1].calls).toBe(3);
  });

  it('attaches a deterministic color to each mode', () => {
    const a = groupByMode(ROWS);
    const b = groupByMode(ROWS);
    expect(a[0].color).toBe(b[0].color);
    // Different mode names yield colors from the palette
    expect(a[0].color).toMatch(/^var\(/);
  });

  it('skips modes with zero calls and handles null inputs', () => {
    expect(groupByMode([])).toEqual([]);
    expect(groupByMode(null)).toEqual([]);
    expect(groupByMode([{ mode: 'x', calls: 0 }])).toEqual([]);
  });
});

describe('modeColor', () => {
  it('is stable for the same input', () => {
    expect(modeColor('greet')).toBe(modeColor('greet'));
  });
  it('returns a CSS var token from the palette', () => {
    expect(modeColor('summary')).toMatch(/^var\(/);
  });
});

describe('buildPieSlices', () => {
  const modes = groupByMode(ROWS);
  const slices = buildPieSlices(modes, { cx: 80, cy: 80, r: 70, inner: 30 });

  it('produces one slice per mode whose frac sums to ~1', () => {
    expect(slices).toHaveLength(modes.length);
    const sum = slices.reduce((a, s) => a + s.frac, 0);
    expect(Math.abs(sum - 1)).toBeLessThan(0.0001);
  });

  it('every slice has a non-empty SVG path and a label inside the donut', () => {
    for (const s of slices) {
      expect(s.path).toMatch(/^M /);
      expect(typeof s.label.x).toBe('number');
      expect(typeof s.label.y).toBe('number');
    }
  });

  it('returns empty for empty/zero-total inputs', () => {
    expect(buildPieSlices([], { cx: 0, cy: 0, r: 10 })).toEqual([]);
    expect(buildPieSlices([{ mode: 'x', calls: 0 }], { cx: 0, cy: 0, r: 10 })).toEqual([]);
  });

  it('single-slice case still produces one renderable path', () => {
    const single = buildPieSlices([{ mode: 'only', calls: 5, color: 'red' }], { cx: 50, cy: 50, r: 40 });
    expect(single).toHaveLength(1);
    expect(single[0].frac).toBe(1);
    expect(single[0].path).toMatch(/^M /);
  });
});
