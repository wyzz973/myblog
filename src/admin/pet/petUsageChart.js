// Pure helpers for the PetUsage daily stacked bar chart.
// Aggregates per-day per-source totals from the flat /pet/usage rows
// and produces SVG-ready geometry.
//
// Sources we expect from the gateway: "provider" (real LLM call),
// "cache_hit" (memoized), "fallback" (degraded), "rate_limited"
// (refused). Anything else falls under "other". Each gets a deterministic
// color so the chart is stable across reloads.

const SOURCE_ORDER = ['provider', 'cache_hit', 'fallback', 'rate_limited', 'other'];

export const SOURCE_COLORS = {
  provider: 'var(--accent)',
  cache_hit: 'var(--accent2, #7dd3a4)',
  fallback: 'var(--violet, #a78bfa)',
  rate_limited: 'var(--danger, #c44)',
  other: 'var(--fg-4)',
};

export const SOURCE_LABELS = {
  provider: 'provider',
  cache_hit: '缓存命中',
  fallback: '降级',
  rate_limited: '被限流',
  other: '其他',
};

function bucket(source) {
  return SOURCE_ORDER.includes(source) ? source : 'other';
}

// Aggregate flat rows into { day → { source → calls } }.
export function groupByDay(rows) {
  const days = new Map();
  for (const r of rows || []) {
    const key = r.day;
    if (!key) continue;
    const slot = days.get(key) || {};
    const src = bucket(r.source || 'other');
    slot[src] = (slot[src] || 0) + (Number(r.calls) || 0);
    days.set(key, slot);
  }
  // Sort by day ascending so the chart reads left → right oldest → newest.
  return Array.from(days.entries())
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([day, sources]) => ({ day, sources }));
}

// Build per-bar geometry given chart bounds. Returns an array of
// { day, total, segments: [{source, calls, y, h}] } sorted ascending
// by day. `max` is the largest single-day total (used for y-scale).
export function buildBars(daily, { width, height, padX, padY }) {
  const innerW = Math.max(1, width - padX * 2);
  const innerH = Math.max(1, height - padY * 2);
  const max = Math.max(
    1,
    ...daily.map((d) => Object.values(d.sources).reduce((a, b) => a + b, 0)),
  );
  const gap = 2;
  const barW = Math.max(1, innerW / Math.max(1, daily.length) - gap);
  return daily.map((d, i) => {
    const total = Object.values(d.sources).reduce((a, b) => a + b, 0);
    const x = padX + i * (barW + gap);
    let yCursor = height - padY;
    const segments = [];
    for (const src of SOURCE_ORDER) {
      const calls = d.sources[src] || 0;
      if (!calls) continue;
      const h = (calls / max) * innerH;
      yCursor -= h;
      segments.push({ source: src, calls, x, y: yCursor, h, w: barW });
    }
    return { day: d.day, total, segments, x, w: barW };
  });
}

// Top legend entries — only the sources that actually appear in the
// data, in fixed display order.
export function legendFromData(daily) {
  const seen = new Set();
  for (const d of daily) {
    for (const k of Object.keys(d.sources)) {
      if (d.sources[k]) seen.add(k);
    }
  }
  return SOURCE_ORDER.filter((s) => seen.has(s)).map((s) => ({
    source: s,
    label: SOURCE_LABELS[s] || s,
    color: SOURCE_COLORS[s] || 'var(--fg-4)',
  }));
}
