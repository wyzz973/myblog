import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { postsApi } from '../api/posts.js';
import PostEditor from './PostEditor.jsx';
import { shouldIgnoreEvent } from './keyboardShortcuts.js';
import useSyncedSearchParams from './useSyncedSearchParams.js';
import { intParser } from './searchParamsState.js';
import { useConfirm, useToast } from './ui/UIProvider.jsx';
import SectionHead from './ui/SectionHead.jsx';

const STATUS_FILTERS = [
  { key: 'all', label: 'all' },
  { key: 'published', label: 'published' },
  { key: 'draft', label: 'draft' },
  { key: 'scheduled', label: 'scheduled' },
];

const PAGE_SIZE_OPTIONS = [20, 50, 100];

// querystring schema — kept module-level so the hook's deps stay stable.
const URL_SCHEMA = [
  { key: 'status', defaultValue: 'all' },
  { key: 'q', defaultValue: '' },
  { key: 'page', defaultValue: 1, parse: intParser(1, 1) },
  { key: 'pageSize', defaultValue: 20, parse: intParser(1, 20) },
];

export default function Posts() {
  const [filters, setFilters] = useSyncedSearchParams(URL_SCHEMA);
  const { status: statusFilter, q, page, pageSize } = filters;
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // null | "__new__" | id
  const [reloadTick, setReloadTick] = useState(0);
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const rowRefs = useRef([]);

  const reload = useCallback(() => setReloadTick((t) => t + 1), []);

  // Side-door for ⌘K: the command palette navigates here with
  // `state.editPost` set to either an id or "__new__". We pop it once and
  // clear the state so a Back/Forward doesn't re-open the editor.
  // Preserve the current querystring so URL-synced filters survive.
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const want = location.state?.editPost;
    if (!want) return;
    setEditing(want);
    navigate(
      { pathname: location.pathname, search: location.search },
      { replace: true, state: null },
    );
  }, [location, navigate]);

  useEffect(() => {
    if (editing !== null) return;
    let mounted = true;
    setLoading(true);
    postsApi
      .list({
        status: statusFilter === 'all' ? undefined : statusFilter,
        q: q.trim() || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      })
      .then((res) => {
        if (!mounted) return;
        setItems(res.items || []);
        setTotal(res.total ?? (res.items || []).length);
        setError(null);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.detail || err?.message || 'failed to load');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [statusFilter, q, editing, reloadTick, pageSize, page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const onPage = useCallback(
    (n) => setFilters({ page: Math.min(Math.max(1, n), totalPages) }),
    [setFilters, totalPages],
  );

  // Reset row focus whenever the visible item set changes.
  useEffect(() => {
    setFocusedIdx(items.length > 0 ? 0 : -1);
  }, [items]);

  // j/k row navigation, Enter / e edit, n new. Listener detaches while
  // editing (PostEditor is rendered instead) or while a global suppress
  // surface (palette / modal / help) is mounted — `shouldIgnoreEvent`
  // covers both via its DOM probe.
  useEffect(() => {
    if (editing !== null) return undefined;
    function onKey(e) {
      if (shouldIgnoreEvent(e)) return;
      if (e.key === 'j') {
        e.preventDefault();
        setFocusedIdx((i) => Math.min((items.length || 1) - 1, i + 1));
      } else if (e.key === 'k') {
        e.preventDefault();
        setFocusedIdx((i) => Math.max(0, i - 1));
      } else if (e.key === 'Enter' || e.key === 'e') {
        const row = items[focusedIdx];
        if (!row) return;
        e.preventDefault();
        setEditing(row.id);
      } else if (e.key === 'n') {
        e.preventDefault();
        setEditing('__new__');
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editing, items, focusedIdx]);

  // Scroll the focused row into view if the user moved past the
  // viewport via j/k.
  useEffect(() => {
    const el = rowRefs.current[focusedIdx];
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    }
  }, [focusedIdx]);

  const confirm = useConfirm();
  const toast = useToast();

  async function onDelete(id) {
    const ok = await confirm({
      title: '删除文章',
      message: `确定删除 “${id}” 吗？此操作不可撤销。`,
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    try {
      await postsApi.remove(id);
      toast.success(`已删除 ${id}`);
      reload();
    } catch (err) {
      toast.error(`删除失败：${err?.detail || err?.message || '未知错误'}`);
    }
  }

  if (editing !== null) {
    return (
      <PostEditor
        id={editing === '__new__' ? null : editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          reload();
        }}
      />
    );
  }

  return (
    <div>
      <header style={styles.header}>
        <div style={{ flex: 1 }}>
          <SectionHead
            n="02"
            title="./posts"
            count={loading ? 'loading…' : `${total} entries`}
          />
        </div>
        <button
          type="button"
          style={styles.btnPrimary}
          onClick={() => setEditing('__new__')}
        >
          + 新建文章
        </button>
      </header>

      <div style={styles.toolRow}>
        <div style={styles.chips}>
          {STATUS_FILTERS.map((f) => {
            const active = f.key === statusFilter;
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilters({ status: f.key, page: 1 })}
                style={{ ...styles.chip, ...(active ? styles.chipActive : null) }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
        <input
          type="search"
          placeholder="search title / body…"
          value={q}
          onChange={(e) => setFilters({ q: e.target.value, page: 1 })}
          style={styles.search}
        />
      </div>

      {error && <div style={styles.error}>! {error}</div>}

      {!error && (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>n</th>
                <th style={styles.th}>title</th>
                <th style={styles.th}>tag</th>
                <th style={styles.th}>date</th>
                <th style={styles.th}>lang</th>
                <th style={styles.th}>read</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>likes</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>actions</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} style={styles.empty}>
                    no posts
                  </td>
                </tr>
              )}
              {items.map((p, idx) => (
                <tr
                  key={p.id}
                  ref={(el) => { rowRefs.current[idx] = el; }}
                  data-testid={`post-row-${idx}`}
                  data-focused={idx === focusedIdx ? 'true' : undefined}
                  style={{
                    ...styles.tr,
                    ...(idx === focusedIdx ? styles.trFocused : null),
                  }}
                  onMouseEnter={() => setFocusedIdx(idx)}
                >
                  <td style={styles.tdN}>{p.n || '—'}</td>
                  <td style={styles.tdTitle}>
                    <div style={styles.title}>{p.title}</div>
                    {p.subtitle && (
                      <div style={styles.subtitle}>{p.subtitle}</div>
                    )}
                    <div style={styles.idHint}>id: {p.id}</div>
                  </td>
                  <td style={styles.td}>
                    <span style={styles.tagPill}>{p.tag}</span>
                  </td>
                  <td style={styles.td}>{p.date}</td>
                  <td style={styles.td}>{p.lang}</td>
                  <td style={styles.td}>{p.read || '—'}</td>
                  <td
                    style={{ ...styles.td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}
                    data-testid={`likes-${p.id}`}
                  >
                    {typeof p.likes === 'number' ? p.likes : 0}
                  </td>
                  <td style={{ ...styles.td, textAlign: 'right' }}>
                    <button
                      type="button"
                      style={styles.btnGhost}
                      onClick={() => setEditing(p.id)}
                    >
                      edit
                    </button>
                    <button
                      type="button"
                      style={styles.btnDanger}
                      onClick={() => onDelete(p.id)}
                    >
                      delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!error && total > 0 && (
        <div style={styles.pager}>
          <div style={styles.pagerInfo}>
            page {page} / {totalPages} · showing {items.length} of {total}
          </div>
          <div style={styles.pagerControls}>
            <label style={styles.pagerLabel}>
              <span style={styles.dim}>per page</span>
              <select
                value={pageSize}
                onChange={(e) => setFilters({ pageSize: Number(e.target.value), page: 1 })}
                style={styles.pagerSelect}
              >
                {PAGE_SIZE_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              style={styles.btnGhost}
              onClick={() => onPage(page - 1)}
              disabled={page <= 1 || loading}
            >
              ← prev
            </button>
            <button
              type="button"
              style={styles.btnGhost}
              onClick={() => onPage(page + 1)}
              disabled={page >= totalPages || loading}
            >
              next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 18,
    gap: 12,
  },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  btnPrimary: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '8px 14px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
    letterSpacing: '0.04em',
  },
  toolRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
    gap: 12,
  },
  chips: { display: 'flex', gap: 6 },
  chip: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '4px 12px',
    borderRadius: 999,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
    letterSpacing: '0.04em',
  },
  chipActive: {
    color: 'var(--fg)',
    borderColor: 'color-mix(in oklab, var(--accent) 50%, transparent)',
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
  },
  search: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '6px 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    minWidth: 220,
  },
  tableWrap: {
    border: '1px solid var(--line)',
    borderRadius: 6,
    overflow: 'hidden',
    background: 'var(--bg-2)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 12,
  },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    borderBottom: '1px solid var(--line)',
    fontWeight: 500,
  },
  tr: {
    borderBottom: '1px solid var(--line)',
  },
  trFocused: {
    background: 'color-mix(in oklab, var(--accent) 12%, transparent)',
    boxShadow: 'inset 3px 0 0 var(--accent)',
  },
  td: {
    padding: '10px 12px',
    color: 'var(--fg-2)',
    verticalAlign: 'top',
  },
  tdN: {
    padding: '10px 12px',
    color: 'var(--accent)',
    fontVariantNumeric: 'tabular-nums',
    verticalAlign: 'top',
    width: 60,
  },
  tdTitle: {
    padding: '10px 12px',
    verticalAlign: 'top',
    minWidth: 240,
  },
  title: { color: 'var(--fg)', fontWeight: 500 },
  subtitle: { color: 'var(--fg-3)', fontSize: 11, marginTop: 2 },
  idHint: { color: 'var(--fg-4)', fontSize: 10, marginTop: 4 },
  tagPill: {
    display: 'inline-block',
    padding: '2px 8px',
    fontSize: 10,
    borderRadius: 3,
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    letterSpacing: '0.04em',
  },
  empty: {
    padding: '40px 12px',
    textAlign: 'center',
    color: 'var(--fg-4)',
    fontSize: 12,
  },
  btnGhost: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
    marginRight: 6,
  },
  btnDanger: {
    background: 'transparent',
    border: '1px solid color-mix(in oklab, var(--danger) 60%, transparent)',
    color: 'var(--danger)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
    marginBottom: 14,
  },
  pager: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 14,
    fontSize: 11,
    color: 'var(--fg-3)',
  },
  pagerInfo: { letterSpacing: '0.04em' },
  pagerControls: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  pagerLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 11,
    color: 'var(--fg-3)',
    marginRight: 6,
  },
  pagerSelect: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    fontSize: 11,
    fontFamily: 'inherit',
    padding: '3px 6px',
    borderRadius: 4,
  },
  dim: { color: 'var(--fg-4)' },
};
