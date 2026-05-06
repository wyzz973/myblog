import { describe, it, expect } from 'vitest';
import {
  buildBars,
  buildCostLine,
  buildPieSlices,
  formatUSD,
  groupByDay,
  groupByMode,
  groupCostByDay,
  legendFromData,
  modeColor,
  rowCostUSD,
  PROVIDER_RATES,
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

// --- Task 26c: cost line chart helpers ---

const COST_ROWS = [
  // anthropic provider call: 1k in + 500 out tokens
  { day: '2026-05-03', mode: 'greet', source: 'anthropic', calls: 1,
    estimated_total_tokens: 1500, estimated_input_tokens: 1000, estimated_output_tokens: 500 },
  // zhipu provider call same day, much cheaper
  { day: '2026-05-03', mode: 'greet', source: 'zhipu', calls: 1,
    estimated_total_tokens: 4000, estimated_input_tokens: 3000, estimated_output_tokens: 1000 },
  // cache hit on the next day — should cost zero regardless of tokens
  { day: '2026-05-04', mode: 'greet', source: 'cache_hit', calls: 5,
    estimated_total_tokens: 100000, estimated_input_tokens: 50000, estimated_output_tokens: 50000 },
  // fallback also zero
  { day: '2026-05-04', mode: 'greet', source: 'fallback', calls: 3,
    estimated_total_tokens: 0, estimated_input_tokens: 0, estimated_output_tokens: 0 },
  // unknown source → default rate (so a typo doesn't silently zero the bill)
  { day: '2026-05-05', mode: 'summary', source: 'mystery', calls: 1,
    estimated_total_tokens: 1000, estimated_input_tokens: 1000, estimated_output_tokens: 0 },
];

describe('rowCostUSD', () => {
  it('charges zero for cache_hit / fallback / rate_limited regardless of tokens', () => {
    expect(rowCostUSD(COST_ROWS[2])).toBe(0); // cache_hit
    expect(rowCostUSD(COST_ROWS[3])).toBe(0); // fallback
    expect(rowCostUSD({ source: 'rate_limited', estimated_input_tokens: 9999, estimated_output_tokens: 9999 })).toBe(0);
  });

  it('applies per-provider in/out rates with correct units (per 1M)', () => {
    // anthropic: 1000 * 3 / 1e6 + 500 * 15 / 1e6 = 0.003 + 0.0075 = 0.0105
    expect(rowCostUSD(COST_ROWS[0])).toBeCloseTo(0.0105, 6);
    // zhipu: 3000 * 0.08 / 1e6 + 1000 * 0.16 / 1e6 = 0.00024 + 0.00016 = 0.0004
    expect(rowCostUSD(COST_ROWS[1])).toBeCloseTo(0.0004, 6);
  });

  it('falls back to PROVIDER_RATES.default for unknown source names', () => {
    // mystery row: 1000 in @ default in_per_m
    const expected = 1000 * PROVIDER_RATES.default.in_per_m / 1e6;
    expect(rowCostUSD(COST_ROWS[4])).toBeCloseTo(expected, 6);
  });

  it('handles missing or null token fields gracefully', () => {
    expect(rowCostUSD({ source: 'anthropic' })).toBe(0);
    expect(rowCostUSD(null)).toBe(0);
    expect(rowCostUSD(undefined)).toBe(0);
  });

  // Task 36
  it('honors a custom rates map when provided', () => {
    const customRates = {
      anthropic: { in_per_m: 100, out_per_m: 200 },
      default: { in_per_m: 5, out_per_m: 10 },
    };
    // anthropic row: 1000 in × 100 / 1e6 + 500 out × 200 / 1e6 = 0.1 + 0.1 = 0.2
    expect(rowCostUSD(COST_ROWS[0], customRates)).toBeCloseTo(0.2, 6);
    // unknown source uses customRates.default not the bundled PROVIDER_RATES.default
    const unk = { source: 'mystery', estimated_input_tokens: 1000, estimated_output_tokens: 0 };
    expect(rowCostUSD(unk, customRates)).toBeCloseTo(0.005, 6);
  });

  it('groupCostByDay accepts the custom rates map', () => {
    const customRates = { anthropic: { in_per_m: 0, out_per_m: 0 }, default: { in_per_m: 0, out_per_m: 0 } };
    const daily = groupCostByDay(COST_ROWS, customRates);
    // Every paid row collapses to 0 under zero rates
    for (const d of daily) {
      expect(d.cost).toBe(0);
    }
  });
});

describe('groupCostByDay', () => {
  it('sums per-day cost in ascending date order', () => {
    const daily = groupCostByDay(COST_ROWS);
    expect(daily.map((d) => d.day)).toEqual(['2026-05-03', '2026-05-04', '2026-05-05']);
    // 2026-05-03 = anthropic + zhipu
    expect(daily[0].cost).toBeCloseTo(0.0105 + 0.0004, 6);
    expect(daily[1].cost).toBe(0); // 2026-05-04 = cache+fallback
    expect(daily[2].cost).toBeGreaterThan(0);
  });

  it('returns [] for empty input', () => {
    expect(groupCostByDay([])).toEqual([]);
    expect(groupCostByDay(null)).toEqual([]);
    expect(groupCostByDay(undefined)).toEqual([]);
  });
});

describe('buildCostLine', () => {
  const CHART = { width: 600, height: 100, padX: 20, padY: 10 };

  it('returns one dot per day, mapped onto the chart bounds', () => {
    const daily = groupCostByDay(COST_ROWS);
    const line = buildCostLine(daily, CHART);
    expect(line.dots).toHaveLength(3);
    // First dot at left padX, last dot at width - padX
    expect(line.dots[0].cx).toBe(CHART.padX);
    expect(line.dots[line.dots.length - 1].cx).toBe(CHART.width - CHART.padX);
    // Highest cost lands closest to the top (smallest cy)
    const sortedByCost = [...line.dots].sort((a, b) => b.cost - a.cost);
    const sortedByCy = [...line.dots].sort((a, b) => a.cy - b.cy);
    expect(sortedByCost[0].day).toBe(sortedByCy[0].day);
  });

  it('zero-cost days sit on the baseline', () => {
    const line = buildCostLine(groupCostByDay(COST_ROWS), CHART);
    const zeroDay = line.dots.find((d) => d.cost === 0);
    expect(zeroDay.cy).toBe(CHART.height - CHART.padY);
  });

  it('points string is space-separated x,y pairs', () => {
    const line = buildCostLine(groupCostByDay(COST_ROWS), CHART);
    expect(line.points.split(' ')).toHaveLength(3);
    for (const p of line.points.split(' ')) {
      expect(p).toMatch(/^\d+(\.\d+)?,\d+(\.\d+)?$/);
    }
  });

  it('single-day input still produces a renderable dot at padX', () => {
    const line = buildCostLine([{ day: '2026-05-03', cost: 0.5 }], CHART);
    expect(line.dots).toHaveLength(1);
    expect(line.dots[0].cx).toBe(CHART.padX);
  });
});

describe('formatUSD', () => {
  it('shows $0.00 for zero/non-finite', () => {
    expect(formatUSD(0)).toBe('$0.00');
    expect(formatUSD(NaN)).toBe('$0.00');
    expect(formatUSD(Infinity)).toBe('$0.00');
  });
  it('uses 4 decimals when below $0.01 (so micro-spend is not "rounded to free")', () => {
    expect(formatUSD(0.0042)).toBe('$0.0042');
  });
  it('uses 2 decimals at $0.01 and above', () => {
    expect(formatUSD(0.01)).toBe('$0.01');
    expect(formatUSD(12.345)).toBe('$12.35');
  });
});
