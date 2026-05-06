import { useCallback, useEffect, useState } from 'react';
import { commentsApi } from '../api/comments.js';
import { useConfirm, useToast } from './ui/UIProvider.jsx';
import SectionHead from './ui/SectionHead.jsx';
import useSyncedSearchParams from './useSyncedSearchParams.js';

// Backend status enum is pending|approved|spam; "all" is a frontend-only
// pseudo-filter that omits the status query param.
const TABS = [
  { key: 'pending', label: 'pending' },
  { key: 'approved', label: 'approved' },
  { key: 'spam', label: 'spam' },
  { key: 'all', label: 'all' },
];

const URL_SCHEMA = [
  { key: 'status', defaultValue: 'pending' },
  { key: 'post_id', defaultValue: '' },
  { key: 'q', defaultValue: '' },
];

export default function Comments() {
  // 把 tab / post_id 过滤 / 文本搜索都挂到 URL，于是
  // /admin/comments?status=all&post_id=vps 这样的深链能直接落到目标视图，
  // 也方便从 Inbox / Reader admin bar / Dashboard tile 跳过来。
  const [filters, setFilters] = useSyncedSearchParams(URL_SCHEMA);
  const tab = filters.status;
  const postFilter = filters.post_id;
  const textQuery = filters.q;
  const setTab = (v) => setFilters({ status: v });
  const setPostFilter = (v) => setFilters({ post_id: v });
  const setTextQuery = (v) => setFilters({ q: v });
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [reloadTick, setReloadTick] = useState(0);
  const [replyOpen, setReplyOpen] = useState(null); // id of comment whose reply form is open
  const [replyText, setReplyText] = useState('');
  const [selected, setSelected] = useState(() => new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const confirm = useConfirm();
  const toast = useToast();

  const reload = useCallback(() => setReloadTick((t) => t + 1), []);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setSelected(new Set());
    commentsApi
      .list({
        status: tab === 'all' ? undefined : tab,
        post_id: postFilter.trim() || undefined,
        q: textQuery.trim() || undefined,
      })
      .then((rows) => {
        if (!mounted) return;
        setItems(rows || []);
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
  }, [tab, postFilter, textQuery, reloadTick]);

  function toggleSelected(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((prev) =>
      prev.size === items.length && items.length > 0
        ? new Set()
        : new Set(items.map((c) => c.id)),
    );
  }

  async function bulkAction(action) {
    if (selected.size === 0) return;
    const verb = { approve: '通过', spam: '标垃圾', pending: '退回待审', delete: '删除' }[action];
    const ok = await confirm({
      title: `${verb}评论`,
      message: `确定${verb} ${selected.size} 条评论吗？`,
      confirmLabel: verb,
      destructive: action === 'delete',
    });
    if (!ok) return;
    setBulkBusy(true);
    try {
      const ids = [...selected];
      const res = await commentsApi.bulk(action, ids);
      setSelected(new Set());
      reload();
      if (typeof res?.affected === 'number' && res.affected !== ids.length) {
        toast.info(`已处理 ${res.affected}/${ids.length} 条`);
      } else {
        toast.success(`已${verb} ${ids.length} 条评论`);
      }
    } catch (err) {
      toast.error(`批量操作失败：${err?.detail || err?.message}`);
    } finally {
      setBulkBusy(false);
    }
  }

  async function setStatus(c, status) {
    setBusyId(c.id);
    // Optimistic
    const prev = items;
    setItems((arr) =>
      arr.map((x) => (x.id === c.id ? { ...x, status } : x)),
    );
    try {
      const res = await commentsApi.patch(c.id, { status });
      // Reconcile from server response
      setItems((arr) =>
        arr.map((x) =>
          x.id === c.id ? { ...x, status: res.status, flag: res.flag } : x,
        ),
      );
      // If we just moved a comment out of the current tab, drop it.
      if (tab !== 'all' && res.status !== tab) {
        setItems((arr) => arr.filter((x) => x.id !== c.id));
      }
    } catch (err) {
      setItems(prev);
      toast.error(`更新失败：${err?.detail || err?.message}`);
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(c) {
    const ok = await confirm({
      title: '删除评论',
      message: `确定删除 “${c.who}” 的评论吗？此操作不可撤销。`,
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    setBusyId(c.id);
    const prev = items;
    setItems((arr) => arr.filter((x) => x.id !== c.id));
    try {
      await commentsApi.remove(c.id);
      toast.success('已删除');
    } catch (err) {
      setItems(prev);
      toast.error(`删除失败：${err?.detail || err?.message}`);
    } finally {
      setBusyId(null);
    }
  }

  async function submitReply(c) {
    const text = replyText.trim();
    if (!text) return;
    setBusyId(c.id);
    try {
      await commentsApi.patch(c.id, { reply_body: text });
      setReplyOpen(null);
      setReplyText('');
      toast.success('已回复');
      reload();
    } catch (err) {
      toast.error(`回复失败：${err?.detail || err?.message}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <header style={styles.header}>
        <div style={{ flex: 1 }}>
          <SectionHead
            n="03"
            title="./comments"
            count={loading ? '加载中…' : `${items.length} ${tab === 'all' ? '条' : tab}`}
          />
        </div>
        <div style={styles.tabs}>
          {TABS.map((t) => {
            const active = t.key === tab;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                style={{ ...styles.tab, ...(active ? styles.tabActive : null) }}
              >
                {t.label}
              </button>
            );
          })}
        </div>
      </header>

      <div style={styles.toolRow}>
        <input
          type="text"
          value={postFilter}
          onChange={(e) => setPostFilter(e.target.value)}
          placeholder="按 post id 过滤（如 vps）"
          style={styles.postFilter}
          data-testid="post-filter"
        />
        {postFilter && (
          <button
            type="button"
            onClick={() => setPostFilter('')}
            style={styles.btnGhost}
          >
            清除
          </button>
        )}
        <input
          type="search"
          value={textQuery}
          onChange={(e) => setTextQuery(e.target.value)}
          placeholder="搜作者 / 正文…"
          style={styles.postFilter}
          data-testid="text-search"
          aria-label="搜索作者或评论正文"
        />
        {textQuery && (
          <button
            type="button"
            onClick={() => setTextQuery('')}
            style={styles.btnGhost}
            data-testid="text-search-clear"
          >
            清除
          </button>
        )}
        <span style={{ flex: 1 }} />
        {items.length > 0 && (
          <label style={styles.selectAll}>
            <input
              type="checkbox"
              checked={selected.size === items.length && items.length > 0}
              onChange={toggleAll}
              data-testid="select-all"
            />
            <span>{selected.size > 0 ? `已选 ${selected.size}/${items.length}` : `全选 (${items.length})`}</span>
          </label>
        )}
      </div>

      {selected.size > 0 && (
        <div style={styles.bulkBar} data-testid="bulk-bar">
          <span style={styles.bulkInfo}>已选 {selected.size} 条</span>
          <button
            type="button"
            style={styles.btnAction}
            onClick={() => bulkAction('approve')}
            disabled={bulkBusy}
            data-testid="bulk-approve"
          >
            批量通过
          </button>
          <button
            type="button"
            style={styles.btnAction}
            onClick={() => bulkAction('spam')}
            disabled={bulkBusy}
          >
            批量标垃圾
          </button>
          <button
            type="button"
            style={styles.btnAction}
            onClick={() => bulkAction('pending')}
            disabled={bulkBusy}
          >
            批量退回待审
          </button>
          <button
            type="button"
            style={styles.btnDanger}
            onClick={() => bulkAction('delete')}
            disabled={bulkBusy}
          >
            批量删除
          </button>
          <button
            type="button"
            style={styles.btnGhost}
            onClick={() => setSelected(new Set())}
            disabled={bulkBusy}
          >
            清除选择
          </button>
        </div>
      )}

      {error && <div style={styles.error}>! {error}</div>}

      <div style={styles.list}>
        {items.length === 0 && !loading && !error && (
          <div style={styles.empty}>no {tab === 'all' ? '' : tab + ' '}comments</div>
        )}
        {items.map((c) => {
          const isBusy = busyId === c.id;
          const replyForThis = replyOpen === c.id;
          return (
            <article key={c.id} style={styles.card} data-testid={`comment-${c.id}`}>
              <header style={styles.cardHead}>
                <div style={styles.who}>
                  <input
                    type="checkbox"
                    checked={selected.has(c.id)}
                    onChange={() => toggleSelected(c.id)}
                    style={styles.rowCheckbox}
                    data-testid={`select-${c.id}`}
                  />
                  <span style={styles.whoName}>{c.who}</span>
                  {c.parent_id && (
                    <span style={styles.replyBadge}>reply to #{c.parent_id}</span>
                  )}
                  {c.flag && <span style={styles.flagBadge}>flag</span>}
                  <StatusPill status={c.status} />
                </div>
                <div style={styles.meta}>
                  <a
                    href={`/p/${encodeURIComponent(c.post_id)}#comment-${c.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={styles.metaLinkAnchor}
                    title={`在新标签页打开 ${c.post_id}`}
                    data-testid={`comment-post-link-${c.id}`}
                  >
                    post: {c.post_title || c.post_id} <span style={styles.metaArrow}>↗</span>
                  </a>
                  <span style={styles.dim}>·</span>
                  <span style={styles.dim}>{fmtDate(c.created_at)}</span>
                  <span style={styles.dim}>· #{c.id}</span>
                </div>
              </header>
              <div style={styles.body}>{c.body}</div>
              <footer style={styles.actions}>
                {c.status !== 'approved' && (
                  <button
                    type="button"
                    style={styles.btnAction}
                    onClick={() => setStatus(c, 'approved')}
                    disabled={isBusy}
                  >
                    approve
                  </button>
                )}
                {c.status !== 'spam' && (
                  <button
                    type="button"
                    style={styles.btnAction}
                    onClick={() => setStatus(c, 'spam')}
                    disabled={isBusy}
                  >
                    mark spam
                  </button>
                )}
                {c.status !== 'pending' && (
                  <button
                    type="button"
                    style={styles.btnAction}
                    onClick={() => setStatus(c, 'pending')}
                    disabled={isBusy}
                  >
                    re-queue
                  </button>
                )}
                <button
                  type="button"
                  style={styles.btnAction}
                  onClick={() => {
                    setReplyOpen(replyForThis ? null : c.id);
                    setReplyText('');
                  }}
                  disabled={isBusy}
                >
                  {replyForThis ? 'cancel reply' : 'reply'}
                </button>
                <button
                  type="button"
                  style={styles.btnDanger}
                  onClick={() => onDelete(c)}
                  disabled={isBusy}
                >
                  delete
                </button>
              </footer>
              {replyForThis && (
                <div style={styles.replyBox}>
                  <textarea
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder="reply as admin…"
                    style={styles.replyTextarea}
                    rows={3}
                  />
                  <div style={styles.replyBtns}>
                    <button
                      type="button"
                      style={styles.btnPrimary}
                      onClick={() => submitReply(c)}
                      disabled={isBusy || !replyText.trim()}
                    >
                      {isBusy ? 'sending…' : 'send reply →'}
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    pending: { color: 'var(--accent)', label: 'pending' },
    approved: { color: '#7dd3a4', label: 'approved' },
    spam: { color: 'var(--danger)', label: 'spam' },
  };
  const m = map[status] || { color: 'var(--fg-3)', label: status };
  return (
    <span
      style={{
        ...styles.statusPill,
        color: m.color,
        borderColor: `color-mix(in oklab, ${m.color} 50%, transparent)`,
      }}
    >
      {m.label}
    </span>
  );
}

function fmtDate(s) {
  if (!s) return '';
  try {
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return s;
  }
}

const styles = {
  toolRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    flexWrap: 'wrap',
  },
  postFilter: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '7px 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    minWidth: 200,
    flex: '1 1 240px',
  },
  selectAll: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 11,
    color: 'var(--fg-3)',
    cursor: 'pointer',
  },
  bulkBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    background: 'color-mix(in oklab, var(--accent) 10%, transparent)',
    borderRadius: 4,
    marginBottom: 10,
    fontSize: 11,
    flexWrap: 'wrap',
  },
  bulkInfo: { color: 'var(--fg-2)', marginRight: 4 },
  rowCheckbox: { marginRight: 8, cursor: 'pointer' },
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 18,
    gap: 12,
    flexWrap: 'wrap',
  },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  tabs: { display: 'flex', gap: 4 },
  tab: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '5px 14px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
    letterSpacing: '0.04em',
  },
  tabActive: {
    color: 'var(--fg)',
    borderColor: 'color-mix(in oklab, var(--accent) 50%, transparent)',
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
  },
  list: { display: 'flex', flexDirection: 'column', gap: 10 },
  card: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '12px 14px',
  },
  cardHead: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 6,
  },
  who: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  whoName: { fontSize: 13, color: 'var(--fg)', fontWeight: 500 },
  replyBadge: {
    fontSize: 10,
    color: 'var(--fg-4)',
    border: '1px solid var(--line-2)',
    padding: '1px 6px',
    borderRadius: 3,
    letterSpacing: '0.04em',
  },
  flagBadge: {
    fontSize: 10,
    color: 'var(--danger)',
    border: '1px solid color-mix(in oklab, var(--danger) 50%, transparent)',
    padding: '1px 6px',
    borderRadius: 3,
    letterSpacing: '0.04em',
  },
  statusPill: {
    fontSize: 10,
    padding: '1px 8px',
    border: '1px solid',
    borderRadius: 999,
    letterSpacing: '0.06em',
    textTransform: 'lowercase',
  },
  meta: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 11,
    color: 'var(--fg-3)',
  },
  metaLinkAnchor: {
    color: 'var(--fg-3)',
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    padding: '1px 6px',
    borderRadius: 3,
    textDecoration: 'none',
    fontSize: 11,
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
  },
  metaArrow: { fontSize: 10, opacity: 0.7 },
  metaLink: {
    color: 'var(--fg-3)',
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    padding: '1px 6px',
    borderRadius: 3,
    fontSize: 10,
  },
  dim: { color: 'var(--fg-4)' },
  body: {
    fontSize: 13,
    color: 'var(--fg-2)',
    whiteSpace: 'pre-wrap',
    lineHeight: 1.55,
    padding: '6px 0 8px',
  },
  actions: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap',
    paddingTop: 8,
    borderTop: '1px dashed var(--line)',
  },
  btnAction: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  btnGhost: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
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
    marginLeft: 'auto',
  },
  btnPrimary: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '6px 14px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
  },
  replyBox: {
    marginTop: 10,
    padding: 10,
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 4,
  },
  replyTextarea: {
    width: '100%',
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '8px 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    resize: 'vertical',
    boxSizing: 'border-box',
  },
  replyBtns: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginTop: 8,
  },
  empty: {
    border: '1px dashed var(--line-2)',
    borderRadius: 6,
    padding: '40px 20px',
    textAlign: 'center',
    color: 'var(--fg-4)',
    fontSize: 12,
  },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
    marginBottom: 14,
  },
};
