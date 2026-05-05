// Tiny OKLCH parse/format helpers for the theme color picker.
// Backend stores the strings verbatim and the public site applies them via
// CSS custom properties; we just need to round-trip them losslessly.
//
// Accepts:   oklch(82% 0.17 152)
//            oklch(82% 0.17 152 / 0.5)
// Emits the canonical form `oklch(L% C H)` (no alpha).

const RE = /^\s*oklch\(\s*([\d.]+)%?\s+([\d.]+)\s+([\d.]+)\s*(?:\/\s*[\d.]+)?\s*\)\s*$/i;

export function parseOklch(s) {
  if (typeof s !== 'string') return null;
  const m = s.match(RE);
  if (!m) return null;
  const [, lRaw, cRaw, hRaw] = m;
  const l = clamp(Number(lRaw), 0, 100);
  const c = clamp(Number(cRaw), 0, 0.4);
  const h = clamp(Number(hRaw), 0, 360);
  if ([l, c, h].some(Number.isNaN)) return null;
  return { l, c, h };
}

export function formatOklch({ l, c, h }) {
  const ll = roundTo(clamp(l, 0, 100), 1);
  const cc = roundTo(clamp(c, 0, 0.4), 3);
  const hh = roundTo(clamp(h, 0, 360), 0);
  return `oklch(${ll}% ${cc} ${hh})`;
}

function clamp(n, lo, hi) {
  if (Number.isNaN(n)) return lo;
  return Math.min(hi, Math.max(lo, n));
}

function roundTo(n, decimals) {
  const f = 10 ** decimals;
  return Math.round(n * f) / f;
}

// Backend defaults — the public-site accent system seed values from
// utils/accent.js + the original SiteIn defaults.
export const THEME_DEFAULTS = {
  accent_color: 'oklch(82% 0.17 152)',
  accent2_color: 'oklch(80% 0.15 70)',
  violet_color: 'oklch(72% 0.18 295)',
  danger_color: 'oklch(70% 0.2 25)',
};
