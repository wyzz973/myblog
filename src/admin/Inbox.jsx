// 01 · 运营中枢 / 收件箱 — unified triage page that pulls visitor-derived
// signals (待审评论 / 最新宠物对话 / 登录与异常) into one place so the
// owner doesn't bounce between three pages just to see what needs
// attention. Composed entirely from existing endpoints; no backend
// changes.

import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { commentsApi } from '../api/comments.js';
import { apiPet } from '../api/pet.js';
import { activityApi } from '../api/activity.js';
import SectionHead from './ui/SectionHead.jsx';

const LAST_SEEN_KEY = 'bl.admin.inbox.last_seen';
const DISMISSED_KEY = 'bl.admin.inbox.dismissed';
const SECTION_LIMIT = 10;
const AUTH_TYPES = ['auth.login.fail', 'auth.login.success', 'auth.2fa.fail'];

function readLastSeen() {
  try {
    const v = localStorage.getItem(LAST_SEEN_KEY);
    return v ? Number(v) : 0;
  } catch {
    return 0;
  }
}

function writeLastSeen(ts) {
  try {
    localStorage.setItem(LAST_SEEN_KEY, String(ts));
  } catch {
    /* ignore */
  }
}

// Task 63: per-row dismiss state. Stored as a Set of "section:id" strings
// in localStorage so individual cards can be marked read without nuking
// every "new" badge via the global markAllRead.
function readDismissed() {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw));
  } catch {
    return new Set();
  }
}

function writeDismissed(set) {
  try {
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(Array.from(set)));
  } catch {
    /* ignore */
  }
}

export default function Inbox() {
  const [comments, setComments] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [authEvents, setAuthEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastSeen, setLastSeen] = useState(readLastSeen);
  const [dismissed, setDismissed] = useState(readDismissed);
  const [tick, setTick] = useState(0);

  function dismissOne(section, rowId) {
    if (!rowId) return;
    const key = `${section}:${rowId}`;
    const next = new Set(dismissed);
    next.add(key);
    writeDismissed(next);
    setDismissed(next);
  }
  function isDismissed(section, rowId) {
    return rowId != null && dismissed.has(`${section}:${rowId}`);
  }

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.allSettled([
      commentsApi.list({ status: 'pending', limit: SECTION_LIMIT }),
      apiPet.listConversations({ limit: SECTION_LIMIT }),
      activityApi.list({ types: AUTH_TYPES, limit: SECTION_LIMIT }),
    ])
      .then(([c, p, a]) => {
        if (!mounted) return;
        setComments(c.status === 'fulfilled' ? c.value || [] : []);
        const pVal = p.status === 'fulfilled' ? p.value : null;
        setConversations(pVal?.items || pVal || []);
        setAuthEvents(a.status === 'fulfilled' ? a.value || [] : []);
        // Surface the first failure (if any) so the owner knows a section is empty.
        const failed = [c, p, a].filter((r) => r.status === 'rejected');
        setError(failed.length ? failed[0].reason?.detail || failed[0].reason?.message : null);
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [tick]);

  const totalNew = useMemo(() => {
    const count = (rows, getTs) =>
      rows.filter((r) => Number(getTs(r)) > lastSeen).length;
    return (
      count(comments, (c) => msTs(c.created_at)) +
      count(conversations, (c) => msTs(c.last_msg_at)) +
      count(authEvents, (e) => msTs(e.created_at))
    );
  }, [comments, conversations, authEvents, lastSeen]);

  function markAllRead() {
    const now = Date.now();
    writeLastSeen(now);
    setLastSeen(now);
  }

  return (
    <div data-testid="inbox-page">
      <header style={styles.header}>
        <div style={{ flex: 1 }}>
          <SectionHead
            n="01"
            title="./inbox · 收件箱"
            lead="把待审评论、最新宠物对话、登录异常合并到一屏。点击行跳转到原位继续处理。"
          />
        </div>
        <div style={styles.headerRight}>
          <span style={styles.newCount} data-testid="inbox-new-count">
            {totalNew > 0 ? `${totalNew} 条新` : '已全部查看'}
          </span>
          <button
            type="button"
            style={styles.btnGhost}
            onClick={() => setTick((t) => t + 1)}
            disabled={loading}
          >
            刷新
          </button>
          <button
            type="button"
            style={styles.btn}
            onClick={markAllRead}
            disabled={loading || totalNew === 0}
            data-testid="mark-all-read"
          >
            全部已读
          </button>
        </div>
      </header>

      {error && (
        <div style={styles.error}>! 部分模块加载失败：{error}（其他模块仍可用）</div>
      )}

      <div style={styles.grid}>
        <Section
          testid="inbox-comments"
          title="评论待审"
          link={{ to: '/admin/comments', label: '前往评论 →' }}
          rows={comments}
          empty="[ 暂无 pending 评论 ]"
          renderRow={(c) => (
            <RowWrap
              isNew={msTs(c.created_at) > lastSeen && !isDismissed('comments', c.id)}
              testid={`inbox-row-comments-${c.id}`}
              onDismiss={() => dismissOne('comments', c.id)}
              to="/admin/comments"
              cells={[
                <span key="who" style={styles.rowAccent}>{c.who}</span>,
                <span key="post" style={styles.rowMuted}>
                  on {c.post_title || c.post_id}
                </span>,
                <span key="body" style={styles.rowBody}>{c.body}</span>,
                <span key="ago" style={styles.rowAgo}>{ago(c.created_at)}</span>,
              ]}
            />
          )}
        />

        <Section
          testid="inbox-conversations"
          title="宠物新对话"
          link={{ to: '/admin/pet?tab=conversations', label: '前往对话 →' }}
          rows={conversations}
          empty="[ 暂无对话 ]"
          renderRow={(c) => (
            <RowWrap
              isNew={msTs(c.last_msg_at) > lastSeen && !isDismissed('conversations', c.visitor_hash)}
              testid={`inbox-row-conversations-${c.visitor_hash}`}
              onDismiss={() => dismissOne('conversations', c.visitor_hash)}
              to={`/admin/pet/conversations/${c.visitor_hash}`}
              cells={[
                <span key="vh" style={styles.rowAccent}>
                  {String(c.visitor_hash || '').slice(0, 12)}
                </span>,
                <span key="sp" style={styles.rowMuted}>{c.species}</span>,
                <span key="msg" style={styles.rowBody}>
                  {c.message_count} 条 · {c.last_reply_preview || '—'}
                </span>,
                <span key="ago" style={styles.rowAgo}>{ago(c.last_msg_at)}</span>,
              ]}
            />
          )}
        />

        <Section
          testid="inbox-auth"
          title="登录与异常"
          link={{ to: '/admin/activity-log', label: '前往活动日志 →' }}
          rows={authEvents}
          empty="[ 暂无登录事件 ]"
          renderRow={(e) => (
            <RowWrap
              isNew={msTs(e.created_at) > lastSeen && !isDismissed('auth', e.id)}
              testid={`inbox-row-auth-${e.id}`}
              onDismiss={() => dismissOne('auth', e.id)}
              to="/admin/activity-log"
              cells={[
                <span key="t" style={styles.rowAccent}>{e.type}</span>,
                <span key="a" style={styles.rowMuted}>{e.actor || '—'}</span>,
                <span key="m" style={styles.rowBody}>
                  {e.meta?.ip ? `ip: ${e.meta.ip}` : ''}
                  {e.meta?.reason ? ` · ${e.meta.reason}` : ''}
                </span>,
                <span key="ago" style={styles.rowAgo}>{ago(e.created_at)}</span>,
              ]}
            />
          )}
        />
      </div>
    </div>
  );
}

function Section({ testid, title, link, rows, empty, renderRow }) {
  return (
    <section style={styles.section} data-testid={testid}>
      <div style={styles.sectionHead}>
        <span style={styles.sectionTitle}>{title}</span>
        <span style={styles.sectionCount}>{rows.length} 条</span>
        <span style={{ flex: 1 }} />
        <Link to={link.to} style={styles.sectionLink}>{link.label}</Link>
      </div>
      <ul style={styles.list}>
        {rows.length === 0 ? (
          <li style={styles.empty}>{empty}</li>
        ) : (
          rows.map((r, i) => <li key={r.id ?? r.visitor_hash ?? i} style={styles.li}>{renderRow(r)}</li>)
        )}
      </ul>
    </section>
  );
}

function RowGrid({ isNew, cells }) {
  return (
    <div
      style={{
        ...styles.row,
        borderLeft: isNew
          ? '2px solid var(--accent)'
          : '2px solid transparent',
      }}
      data-isnew={isNew ? 'true' : 'false'}
    >
      {cells}
    </div>
  );
}

// Task 63: 行容器 — Link 包裹的 RowGrid + 右侧 ✓ dismiss 按钮。
// 按钮的 onClick 必须 stopPropagation/preventDefault，否则会被 Link 吞掉。
function RowWrap({ isNew, cells, to, onDismiss, testid }) {
  return (
    <div style={styles.rowWrap} data-testid={testid}>
      <Link to={to} style={styles.rowLink}>
        <RowGrid isNew={isNew} cells={cells} />
      </Link>
      <button
        type="button"
        title="标为已读"
        style={styles.dismissBtn}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onDismiss?.();
        }}
        data-testid={`${testid}-dismiss`}
      >
        ✓
      </button>
    </div>
  );
}

function msTs(iso) {
  if (!iso) return 0;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function ago(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const ms = Date.now() - d.getTime();
  if (ms < 0) return d.toLocaleString();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 16,
    gap: 12,
    flexWrap: 'wrap',
  },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  headN: { color: 'var(--accent)', fontSize: 14, letterSpacing: '0.06em' },
  headSlash: { color: 'var(--fg-4)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0', maxWidth: 640 },
  headerRight: { display: 'flex', alignItems: 'center', gap: 10 },
  newCount: { fontSize: 11, color: 'var(--fg-3)' },
  btn: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '5px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 11,
    cursor: 'pointer',
  },
  btnGhost: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '5px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 11,
    cursor: 'pointer',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
    gap: 14,
  },
  section: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    overflow: 'hidden',
    minWidth: 0,
  },
  sectionHead: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 8,
    padding: '10px 14px',
    borderBottom: '1px solid var(--line)',
    background: 'var(--bg)',
  },
  sectionTitle: {
    fontSize: 11,
    color: 'var(--fg-2)',
    letterSpacing: '0.06em',
    fontWeight: 600,
  },
  sectionCount: {
    fontSize: 10,
    color: 'var(--fg-4)',
    letterSpacing: '0.04em',
  },
  sectionLink: { fontSize: 10, color: 'var(--fg-3)', textDecoration: 'none' },
  list: { margin: 0, padding: 0, listStyle: 'none' },
  li: { borderBottom: '1px solid var(--line)' },
  empty: {
    padding: '14px',
    fontSize: 11,
    color: 'var(--fg-4)',
    fontStyle: 'italic',
    textAlign: 'center',
  },
  rowLink: { textDecoration: 'none', color: 'inherit', display: 'block', flex: 1, minWidth: 0 },
  rowWrap: { display: 'flex', alignItems: 'stretch' },
  dismissBtn: {
    background: 'transparent', border: '1px solid var(--line-2)',
    color: 'var(--fg-3)', fontFamily: 'inherit', fontSize: 11,
    padding: '0 10px', cursor: 'pointer',
    borderRadius: 3, marginLeft: 6, alignSelf: 'center',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: 'minmax(80px, max-content) minmax(80px, max-content) minmax(0, 1fr) max-content',
    alignItems: 'baseline',
    gap: 8,
    padding: '7px 14px 7px 12px',
    fontSize: 11,
    color: 'var(--fg-2)',
    fontVariantNumeric: 'tabular-nums',
  },
  rowAccent: { color: 'var(--fg)', fontWeight: 600 },
  rowMuted: { color: 'var(--fg-3)' },
  rowBody: {
    color: 'var(--fg-2)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  rowAgo: { color: 'var(--fg-4)' },
  error: {
    color: 'var(--danger)',
    fontSize: 11,
    border: '1px solid var(--danger)',
    padding: '8px 12px',
    borderRadius: 4,
    marginBottom: 12,
  },
};
