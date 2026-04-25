import { useEffect, useMemo, useRef, useState } from 'react';
import { POSTS } from '../data.js';
import { ACCENTS } from '../utils/accent.js';

const ICONS = { theme: '◐', accent: '◉', post: '✦' };

export default function Palette({ open, onClose, onOpenPost, setTheme, setAccent }) {
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const inputRef = useRef(null);

  const items = useMemo(() => {
    const cmds = [
      {
        type: 'cmd',
        ico: ICONS.theme,
        label: 'Toggle theme · dark/light',
        sub: 't',
        run: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
      },
      ...ACCENTS.map((a) => ({
        type: 'cmd',
        ico: ICONS.accent,
        label: `Accent · ${a}`,
        sub: 'theme',
        run: () => setAccent(a),
      })),
    ];
    const posts = POSTS.map((p) => ({
      type: 'post',
      ico: ICONS.post,
      label: p.title,
      sub: `#${p.n} · ${p.tag}`,
      run: () => onOpenPost(p),
    }));
    const all = [...cmds, ...posts];
    if (!q) return all;
    const qq = q.toLowerCase();
    return all.filter(
      (i) => i.label.toLowerCase().includes(qq) || (i.sub || '').toLowerCase().includes(qq),
    );
  }, [q, onOpenPost, setTheme, setAccent]);

  useEffect(() => {
    if (open) {
      setQ('');
      setSel(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  useEffect(() => { setSel(0); }, [q]);

  if (!open) return null;

  const run = (it) => {
    it.run();
    onClose();
  };

  return (
    <div className="palette-bg" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          placeholder="> search posts, run commands…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              setSel((s) => Math.min(items.length - 1, s + 1));
              e.preventDefault();
            }
            if (e.key === 'ArrowUp') {
              setSel((s) => Math.max(0, s - 1));
              e.preventDefault();
            }
            if (e.key === 'Enter' && items[sel]) run(items[sel]);
            if (e.key === 'Escape') onClose();
          }}
        />
        <div className="results">
          {items.length === 0 && (
            <div style={{ padding: 20, color: 'var(--fg-4)', fontSize: 13 }}>
              No matches. Try something else.
            </div>
          )}
          {items.map((it, i) => (
            <div
              key={i}
              className={`pitem ${i === sel ? 'sel' : ''}`}
              onClick={() => run(it)}
              onMouseEnter={() => setSel(i)}
            >
              <span className="ico">{it.ico}</span>
              <span>{it.label}</span>
              <span className="sub">{it.sub}</span>
            </div>
          ))}
        </div>
        <div className="phint">
          <span><kbd>↑↓</kbd> navigate</span>
          <span><kbd>↵</kbd> run</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
