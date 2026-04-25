const MAP = {
  green:  { a: 'oklch(82% 0.17 152)', l: 'oklch(55% 0.15 152)' },
  amber:  { a: 'oklch(80% 0.15 70)',  l: 'oklch(58% 0.15 60)'  },
  violet: { a: 'oklch(72% 0.18 295)', l: 'oklch(55% 0.17 295)' },
};

export function applyAccent(name) {
  const v = MAP[name] || MAP.green;
  const root = document.documentElement;
  const isLight = document.body.classList.contains('theme-light');
  root.style.setProperty('--accent', isLight ? v.l : v.a);
  root.style.setProperty('--accent-glow', `color-mix(in oklab, ${v.a} 40%, transparent)`);
}

export const ACCENTS = ['green', 'amber', 'violet'];
