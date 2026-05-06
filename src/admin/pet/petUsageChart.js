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

// --- per-mode pie chart helpers ---

// Color cycle for modes. Pet has many possible modes (greet / summary /
// summary_react / pet_care / code_assist / recommend_next / etc.) — we
// don't enumerate them since admin can introduce new ones via templates.
// Use a fixed-length palette with deterministic mapping by mode name.
const MODE_PALETTE = [
  'var(--accent)',
  'var(--accent2, #7dd3a4)',
  'var(--violet, #a78bfa)',
  'var(--danger, #c44)',
  'var(--fg-3)',
  'var(--fg-4)',
];

export function modeColor(mode) {
  let hash = 0;
  for (let i = 0; i < (mode || '').length; i++) {
    hash = (hash * 31 + mode.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % MODE_PALETTE.length;
  return MODE_PALETTE[idx];
}

export function groupByMode(rows) {
  const totals = new Map();
  for (const r of rows || []) {
    const k = r.mode || 'unknown';
    totals.set(k, (totals.get(k) || 0) + (Number(r.calls) || 0));
  }
  // Sort descending by calls so the pie reads largest-first.
  return Array.from(totals.entries())
    .filter(([, n]) => n > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([mode, calls]) => ({ mode, calls, color: modeColor(mode) }));
}

// Build pie/donut slice geometry. cx/cy/r/inner control the ring;
// each slice gets a `path` SVG-d string (arc) plus its label position.
export function buildPieSlices(modes, { cx, cy, r, inner = 0 }) {
  const total = modes.reduce((a, m) => a + m.calls, 0);
  if (total <= 0 || !modes.length) return [];
  // Single-slice case — one full circle (SVG arc with same start/end is
  // empty). Fall back to a path that traces a full circle in two arcs.
  if (modes.length === 1) {
    const m = modes[0];
    const path = inner > 0
      ? donutFullCircle(cx, cy, r, inner)
      : `M ${cx},${cy - r} A ${r},${r} 0 1,1 ${cx - 0.001},${cy - r} Z`;
    return [{
      ...m, frac: 1, path,
      label: { x: cx, y: cy - (r + inner) / 2 },
    }];
  }
  let cursor = -Math.PI / 2; // start at top (12 o'clock)
  const out = [];
  for (const m of modes) {
    const frac = m.calls / total;
    const sweep = frac * Math.PI * 2;
    const a0 = cursor;
    const a1 = cursor + sweep;
    cursor = a1;
    const large = sweep > Math.PI ? 1 : 0;
    const x0 = cx + Math.cos(a0) * r;
    const y0 = cy + Math.sin(a0) * r;
    const x1 = cx + Math.cos(a1) * r;
    const y1 = cy + Math.sin(a1) * r;
    let path;
    if (inner > 0) {
      const ix0 = cx + Math.cos(a0) * inner;
      const iy0 = cy + Math.sin(a0) * inner;
      const ix1 = cx + Math.cos(a1) * inner;
      const iy1 = cy + Math.sin(a1) * inner;
      path = `M ${x0},${y0} A ${r},${r} 0 ${large},1 ${x1},${y1}` +
        ` L ${ix1},${iy1} A ${inner},${inner} 0 ${large},0 ${ix0},${iy0} Z`;
    } else {
      path = `M ${cx},${cy} L ${x0},${y0} A ${r},${r} 0 ${large},1 ${x1},${y1} Z`;
    }
    const aMid = (a0 + a1) / 2;
    const labelR = (r + inner) / 2;
    out.push({
      ...m,
      frac,
      path,
      label: {
        x: cx + Math.cos(aMid) * labelR,
        y: cy + Math.sin(aMid) * labelR,
      },
    });
  }
  return out;
}

function donutFullCircle(cx, cy, r, inner) {
  // Outer circle clockwise + inner counter-clockwise (even-odd would
  // produce a hole, but we simply trace both as one path).
  return (
    `M ${cx},${cy - r} A ${r},${r} 0 1,1 ${cx - 0.001},${cy - r} Z ` +
    `M ${cx},${cy - inner} A ${inner},${inner} 0 1,0 ${cx - 0.001},${cy - inner} Z`
  );
}

// --- Task 26c: daily estimated cost line chart ---
//
// Per-provider USD rates, $/1M tokens. Approximate published rates as of
// 2026-05; owner can override later via Integrations settings (out of scope
// for 26c). Sources that are not paid LLM calls (cache_hit / fallback /
// rate_limited) cost zero. Unknown providers fall through to PROVIDER_RATES.default
// rather than going free, so a typo doesn't silently zero the bill.
//
// in_per_m / out_per_m read in dollars per 1,000,000 tokens.
export const PROVIDER_RATES = {
  anthropic: { in_per_m: 3.00, out_per_m: 15.00 },
  zhipu:     { in_per_m: 0.08, out_per_m: 0.16 },
  qwen:      { in_per_m: 0.10, out_per_m: 0.30 },
  doubao:    { in_per_m: 0.05, out_per_m: 0.15 },
  deepseek:  { in_per_m: 0.27, out_per_m: 1.10 },
  default:   { in_per_m: 0.50, out_per_m: 1.50 },
};

const ZERO_COST_SOURCES = new Set(['cache_hit', 'fallback', 'rate_limited']);

export function rowCostUSD(row, rates = PROVIDER_RATES) {
  if (!row) return 0;
  if (ZERO_COST_SOURCES.has(row.source)) return 0;
  const rate = (rates && rates[row.source]) || (rates && rates.default) || PROVIDER_RATES.default;
  const inTok = Number(row.estimated_input_tokens || 0);
  const outTok = Number(row.estimated_output_tokens || 0);
  return (inTok * rate.in_per_m + outTok * rate.out_per_m) / 1_000_000;
}

export function groupCostByDay(rows, rates = PROVIDER_RATES) {
  const days = new Map();
  for (const r of rows || []) {
    if (!r.day) continue;
    days.set(r.day, (days.get(r.day) || 0) + rowCostUSD(r, rates));
  }
  return Array.from(days.entries())
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([day, cost]) => ({ day, cost }));
}

// Build a polyline + circles geometry for a single-series line chart.
// Returns { points: "x1,y1 x2,y2 ...", dots: [{cx,cy,day,cost}], max }.
export function buildCostLine(daily, { width, height, padX, padY }) {
  const innerW = Math.max(1, width - padX * 2);
  const innerH = Math.max(1, height - padY * 2);
  const max = Math.max(0.0001, ...daily.map((d) => d.cost));
  const baseY = height - padY;
  const stepX = daily.length <= 1 ? 0 : innerW / (daily.length - 1);
  const dots = daily.map((d, i) => ({
    day: d.day,
    cost: d.cost,
    cx: padX + i * stepX,
    cy: baseY - (d.cost / max) * innerH,
  }));
  const points = dots.map((p) => `${p.cx.toFixed(1)},${p.cy.toFixed(1)}`).join(' ');
  return { points, dots, max };
}

export function formatUSD(n) {
  if (!isFinite(n)) return '$0.00';
  if (n === 0) return '$0.00';
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}
