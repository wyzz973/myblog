import { useEffect, useMemo, useRef, useState } from 'react';
import {
  buildPaletteItems,
  filterPaletteItems,
  groupBySection,
} from './commandPaletteItems.js';

const SECTION_LABEL = { nav: '导航', cmd: '命令', post: '文章' };

export default function CommandPalette({
  open,
  onClose,
  navGroups,
  currentPath,
  runners,
  loadPosts,
}) {
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const [posts, setPosts] = useState([]);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    setQ('');
    setSel(0);
    const t = setTimeout(() => inputRef.current?.focus(), 10);
    let cancelled = false;
    if (loadPosts) {
      loadPosts()
        .then((items) => {
          if (!cancelled) setPosts(items || []);
        })
        .catch(() => {
          /* swallow — palette still works for nav + cmd */
        });
    }
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [open, loadPosts]);

  const all = useMemo(
    () => buildPaletteItems({ navGroups, posts, runners, currentPath }),
    [navGroups, posts, runners, currentPath],
  );
  const items = useMemo(() => filterPaletteItems(all, q), [all, q]);
  const sectioned = useMemo(() => groupBySection(items), [items]);

  useEffect(() => {
    setSel(0);
  }, [q]);

  useEffect(() => {
    if (!open) return undefined;
    function onDocKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    }
    document.addEventListener('keydown', onDocKey);
    return () => document.removeEventListener('keydown', onDocKey);
  }, [open, onClose]);

  if (!open) return null;

  function run(it) {
    onClose();
    it.run();
  }

  function handleKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSel((s) => Math.min(items.length - 1, s + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSel((s) => Math.max(0, s - 1));
    } else if (e.key === 'Enter' && items[sel]) {
      e.preventDefault();
      run(items[sel]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  }

  return (
    <div
      className="palette-bg"
      data-testid="palette-bg"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="palette"
        data-testid="admin-palette"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          data-testid="palette-input"
          placeholder="> 跳转 / 命令 / 搜索文章…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="results">
          {items.length === 0 && (
            <div style={emptyStyle}>没有匹配项。换个关键词试试。</div>
          )}
          {['nav', 'cmd', 'post'].map((sec) => {
            const rows = sectioned[sec];
            if (!rows?.length) return null;
            return (
              <div key={sec} data-testid={`palette-section-${sec}`}>
                <div style={sectionHeadStyle}>{SECTION_LABEL[sec]}</div>
                {rows.map(({ it, idx }) => (
                  <div
                    key={idx}
                    className={`pitem ${idx === sel ? 'sel' : ''}`}
                    data-testid={`palette-item-${idx}`}
                    onMouseEnter={() => setSel(idx)}
                    onClick={() => run(it)}
                  >
                    <span className="ico">{it.ico}</span>
                    <span>{it.label}</span>
                    <span className="sub">{it.sub}</span>
                  </div>
                ))}
              </div>
            );
          })}
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

const emptyStyle = { padding: 20, color: 'var(--fg-4)', fontSize: 13 };

const sectionHeadStyle = {
  padding: '8px 12px 4px',
  fontSize: 9,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: 'var(--fg-4)',
};
