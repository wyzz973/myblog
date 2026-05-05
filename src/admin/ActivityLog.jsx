import { useEffect, useMemo, useState } from 'react';
import { activityApi } from '../api/activity.js';

const PAGE_SIZE = 50;
// Anchor types — a curated list of the most useful event categories.
// Anything outside this list still appears under "其他" if seen.
const KNOWN_TYPES = [
  'auth.login.success',
  'auth.login.fail',
  'auth.2fa.success',
  'auth.refresh',
  'auth.logout',
  'post.created',
  'post.updated',
  'post.deleted',
  'comment.status',
  'comment.replied',
  'media.uploaded',
  'media.deleted',
  'media.alt_updated',
  'tag.created',
  'tag.updated',
  'tag.deleted',
  'profile.updated',
  'site.updated',
  'theme.updated',
  'integration.updated',
  'pet.updated',
  'now.created',
  'now.updated',
  'now.deleted',
  'project.updated',
  'project.deleted',
  'contact.updated',
];

export default function ActivityLog() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offset, setOffset] = useState(0);
  const [reachedEnd, setReachedEnd] = useState(false);
  const [filterType, setFilterType] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    activityApi
      .list({ types: filterType ? [filterType] : undefined, limit: PAGE_SIZE, offset })
      .then((rows) => {
        if (!mounted) return;
        setItems((prev) => (offset === 0 ? rows : [...prev, ...rows]));
        setReachedEnd((rows || []).length < PAGE_SIZE);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.detail || err?.message || '加载失败');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [offset, filterType]);

  // Reset pagination when the filter changes.
  function pickFilter(t) {
    setFilterType(t);
    setOffset(0);
    setItems([]);
    setReachedEnd(false);
  }

  function toggle(id) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Surface event types actually seen in the loaded items so the chip bar
  // adapts to the user's site without listing every theoretical type.
  const seenTypes = useMemo(() => {
    const set = new Set();
    items.forEach((it) => set.add(it.type));
    return set;
  }, [items]);

  return (
    <div>
      <header style={styles.header} data-testid="activity-log-head">
        <div>
          <h1 style={styles.h1}>
            <span style={styles.headN}>06</span>{' '}
            <span style={styles.headSlash}>/</span> 活动日志
          </h1>
          <p style={styles.lead}>
            后台所有写操作都会写入 event_log。这里按时间倒序展示，可按类型筛选并展开 meta。
          </p>
        </div>
      </header>

      <div style={styles.chipRow} data-testid="activity-chips">
        <FilterChip
          label="全部"
          active={filterType == null}
          onClick={() => pickFilter(null)}
        />
        {KNOWN_TYPES.filter((t) => seenTypes.has(t)).map((t) => (
          <FilterChip
            key={t}
            label={t}
            active={filterType === t}
            onClick={() => pickFilter(t)}
          />
        ))}
        {[...seenTypes]
          .filter((t) => !KNOWN_TYPES.includes(t))
          .sort()
          .map((t) => (
            <FilterChip
              key={t}
              label={t}
              active={filterType === t}
              onClick={() => pickFilter(t)}
            />
          ))}
      </div>

      {error && <div style={styles.error}>! {error}</div>}

      <div style={styles.tableWrap}>
        <table style={styles.table} data-testid="activity-table">
          <thead>
            <tr>
              <th style={styles.th}>type</th>
              <th style={styles.th}>actor</th>
              <th style={styles.th}>target</th>
              <th style={styles.th}>at</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading ? (
              <tr>
                <td colSpan={4} style={styles.emptyTd}>
                  [ 暂无事件 ]
                </td>
              </tr>
            ) : (
              items.map((it) => (
                <Row
                  key={it.id}
                  item={it}
                  expanded={expanded.has(it.id)}
                  onToggle={() => toggle(it.id)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      <div style={styles.footer}>
        {loading && <span style={styles.muted}>加载中…</span>}
        {!loading && !reachedEnd && (
          <button
            type="button"
            onClick={() => setOffset(items.length)}
            style={styles.moreBtn}
          >
            加载更多
          </button>
        )}
        {!loading && reachedEnd && items.length > 0 && (
          <span style={styles.muted}>— 末尾 —</span>
        )}
      </div>
    </div>
  );
}

function FilterChip({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        ...styles.chip,
        ...(active ? styles.chipActive : null),
      }}
      data-testid={`chip-${label}`}
    >
      {label}
    </button>
  );
}

function Row({ item, expanded, onToggle }) {
  const hasMeta = item.meta && Object.keys(item.meta).length > 0;
  return (
    <>
      <tr style={styles.tr} onClick={onToggle} data-testid={`row-${item.id}`}>
        <td style={styles.tdType}>{item.type}</td>
        <td style={styles.td}>{item.actor || '—'}</td>
        <td style={styles.tdTarget}>{item.target || '—'}</td>
        <td style={styles.td}>{ago(item.created_at)}</td>
      </tr>
      {expanded && (
        <tr data-testid={`meta-${item.id}`}>
          <td colSpan={4} style={styles.metaTd}>
            {hasMeta ? (
              <pre style={styles.metaPre}>{JSON.stringify(item.meta, null, 2)}</pre>
            ) : (
              <div style={styles.metaEmpty}>[ 无 meta — 后端未附加额外字段 ]</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function ago(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const ms = Date.now() - d.getTime();
  if (ms < 0) return d.toLocaleString();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

const styles = {
  header: { marginBottom: 16 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  headN: { color: 'var(--accent)', fontSize: 14, letterSpacing: '0.06em' },
  headSlash: { color: 'var(--fg-4)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  chipRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 14,
  },
  chip: {
    fontFamily: 'inherit',
    fontSize: 11,
    padding: '4px 9px',
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    borderRadius: 999,
    cursor: 'pointer',
  },
  chipActive: {
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    color: 'var(--fg)',
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
    fontFamily: 'inherit',
  },
  th: {
    textAlign: 'left',
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    padding: '8px 12px',
    borderBottom: '1px solid var(--line)',
    background: 'var(--bg)',
    fontWeight: 600,
  },
  tr: {
    cursor: 'pointer',
    borderBottom: '1px solid var(--line)',
  },
  td: {
    padding: '8px 12px',
    color: 'var(--fg-2)',
    fontVariantNumeric: 'tabular-nums',
  },
  tdType: {
    padding: '8px 12px',
    color: 'var(--fg)',
    fontVariantNumeric: 'tabular-nums',
  },
  tdTarget: {
    padding: '8px 12px',
    color: 'var(--fg-3)',
    fontFamily: 'inherit',
    maxWidth: 380,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  metaTd: {
    padding: 0,
    background: 'var(--bg)',
    borderBottom: '1px solid var(--line)',
  },
  metaPre: {
    margin: 0,
    padding: '10px 16px',
    fontSize: 11,
    color: 'var(--fg-2)',
    fontFamily: 'inherit',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  metaEmpty: {
    padding: '10px 16px',
    fontSize: 11,
    color: 'var(--fg-4)',
    fontStyle: 'italic',
  },
  emptyTd: {
    padding: '16px 12px',
    fontSize: 12,
    color: 'var(--fg-4)',
    textAlign: 'center',
    fontStyle: 'italic',
  },
  footer: { marginTop: 12, display: 'flex', justifyContent: 'center' },
  moreBtn: {
    fontFamily: 'inherit',
    fontSize: 12,
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '6px 14px',
    borderRadius: 4,
    cursor: 'pointer',
  },
  muted: { color: 'var(--fg-4)', fontSize: 11 },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '8px 12px',
    borderRadius: 4,
    marginBottom: 12,
  },
};
