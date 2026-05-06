import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiAdmin } from '../api/admin.js';
import { activityApi } from '../api/activity.js';
import SectionHead from './ui/SectionHead.jsx';

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiAdmin
      .dashboard()
      .then((res) => {
        if (!mounted) return;
        setData(res);
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
  }, []);

  if (loading) return <div style={styles.muted}>loading dashboard…</div>;
  if (error) return <div style={styles.error}>error: {error}</div>;
  if (!data) return <div style={styles.muted}>no data</div>;

  const tiles = buildTiles(data);

  return (
    <div>
      <header style={styles.header}>
        <SectionHead
          n="01"
          title="./dashboard"
          lead="站点活动快照"
        />
      </header>
      <div style={styles.grid}>
        {tiles.map((t) => (
          <Card
            key={t.key}
            title={t.title}
            headline={t.headline}
            subs={t.subs}
            to={t.to}
            testid={`dashboard-tile-${t.key}`}
          />
        ))}
      </div>
      <RecentActivity />
    </div>
  );
}

function RecentActivity() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    activityApi
      .recent({ limit: 20 })
      .then((data) => {
        if (!mounted) return;
        setRows(data || []);
        setError(null);
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
  }, []);

  return (
    <section style={styles.activitySection} data-testid="dashboard-activity">
      <div style={styles.activityHead}>
        <div style={styles.activityHeadLeft}>
          <span style={styles.activityHeadN}>01</span>
          <span style={styles.activityHeadSlash}>/</span>
          <span style={styles.activityHeadTitle}>最近活动</span>
        </div>
        <Link to="/admin/activity-log" style={styles.activityMore}>
          查看全部 →
        </Link>
      </div>
      {error && <div style={styles.activityError}>! {error}</div>}
      {!error && (
        <ul style={styles.activityList}>
          {loading && rows.length === 0 ? (
            <li style={styles.activityMuted}>loading…</li>
          ) : rows.length === 0 ? (
            <li style={styles.activityMuted}>[ 暂无事件 ]</li>
          ) : (
            rows.map((it) => (
              <li key={it.id} style={styles.activityRow}>
                <span style={styles.activityType}>{it.type}</span>
                <span style={styles.activitySep}>·</span>
                <span style={styles.activityActor}>{it.actor || '—'}</span>
                {it.target && (
                  <>
                    <span style={styles.activitySep}>·</span>
                    <span style={styles.activityTarget}>{it.target}</span>
                  </>
                )}
                <span style={styles.activityAgo}>{ago(it.created_at)}</span>
              </li>
            ))
          )}
        </ul>
      )}
    </section>
  );
}

function ago(iso) {
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
  const days = Math.floor(h / 24);
  if (days < 30) return `${days}d`;
  return d.toLocaleDateString();
}

function buildTiles(d) {
  return [
    {
      key: 'hits',
      title: 'Hits today',
      headline: fmt(d.hits?.today),
      subs: [
        ['last 7d', fmt(d.hits?.last_7d)],
        ['last 30d', fmt(d.hits?.last_30d)],
      ],
      to: '/admin/analytics',
    },
    {
      key: 'likes',
      title: 'Likes total',
      headline: fmt(d.likes?.total),
      subs: [['last 7d', fmt(d.likes?.last_7d)]],
      to: '/admin/analytics',
    },
    {
      key: 'comments',
      title: 'Comments',
      headline: fmt(d.comments?.total),
      subs: [['pending', fmt(d.comments?.pending)]],
      to: '/admin/comments',
    },
    {
      key: 'posts',
      title: 'Posts published',
      headline: fmt(d.posts?.published),
      subs: [
        ['draft', fmt(d.posts?.draft)],
        ['scheduled', fmt(d.posts?.scheduled)],
      ],
      to: '/admin/posts',
    },
    {
      key: 'media',
      title: 'Media items',
      headline: fmt(d.media?.count),
      subs: [],
      to: '/admin/media',
    },
    // Task 57: pet helper traffic. Hidden when the field is missing
    // (older deploys / tests) — keeps existing snapshots stable.
    ...(d.pet ? [{
      key: 'pet',
      title: 'Pet conversations',
      headline: fmt(d.pet.conversations),
      subs: [['msgs / 7d', fmt(d.pet.messages_last_7d)]],
      to: '/admin/pet?tab=conversations',
    }] : []),
  ];
}

function fmt(v) {
  if (v == null) return '—';
  if (typeof v === 'number') return v.toLocaleString();
  return String(v);
}

function Card({ title, headline, subs, to, testid }) {
  // Task 65: 卡片可点击 → 跳到对应模块。无 `to` 时降级为 div。
  const inner = (
    <>
      <div style={styles.cardTitle}>{title}</div>
      <div style={styles.headline}>{headline}</div>
      {subs && subs.length > 0 && (
        <div style={styles.subRow}>
          {subs.map(([label, value]) => (
            <div key={label} style={styles.subItem}>
              <span style={styles.subLabel}>{label}</span>
              <span style={styles.subValue}>{value}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
  if (to) {
    return (
      <Link to={to} style={{ ...styles.card, ...styles.cardLink }} data-testid={testid}>
        {inner}
      </Link>
    );
  }
  return <div style={styles.card} data-testid={testid}>{inner}</div>;
}

const styles = {
  header: { marginBottom: 18 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: 14,
  },
  card: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '14px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    minHeight: 120,
  },
  cardLink: {
    textDecoration: 'none', color: 'inherit', cursor: 'pointer',
    transition: 'border-color 120ms',
  },
  cardTitle: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  headline: {
    fontSize: 32,
    fontWeight: 600,
    color: 'var(--accent)',
    lineHeight: 1.1,
    fontVariantNumeric: 'tabular-nums',
  },
  subRow: {
    display: 'flex',
    gap: 14,
    marginTop: 'auto',
    paddingTop: 6,
    borderTop: '1px dashed var(--line)',
    fontSize: 11,
  },
  subItem: { display: 'flex', flexDirection: 'column' },
  subLabel: { color: 'var(--fg-4)', textTransform: 'lowercase' },
  subValue: { color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' },
  muted: { color: 'var(--fg-3)', fontSize: 12 },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
  },
  activitySection: {
    marginTop: 24,
    border: '1px solid var(--line)',
    borderRadius: 6,
    background: 'var(--bg-2)',
    overflow: 'hidden',
  },
  activityHead: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 14px',
    borderBottom: '1px solid var(--line)',
    background: 'var(--bg)',
  },
  activityHeadLeft: { display: 'flex', alignItems: 'baseline', gap: 6 },
  activityHeadN: {
    color: 'var(--accent)',
    fontSize: 9,
    letterSpacing: '0.12em',
    fontWeight: 600,
  },
  activityHeadSlash: { color: 'var(--fg-4)', fontSize: 11 },
  activityHeadTitle: {
    color: 'var(--fg-2)',
    fontSize: 11,
    letterSpacing: '0.06em',
  },
  activityMore: {
    color: 'var(--fg-3)',
    fontSize: 11,
    textDecoration: 'none',
    letterSpacing: '0.04em',
  },
  activityList: {
    margin: 0,
    padding: 0,
    listStyle: 'none',
    fontSize: 11,
  },
  activityRow: {
    display: 'grid',
    gridTemplateColumns: 'minmax(140px, max-content) 8px minmax(120px, 1fr) 8px minmax(0, 2fr) max-content',
    alignItems: 'baseline',
    gap: 6,
    padding: '7px 14px',
    borderBottom: '1px solid var(--line)',
    color: 'var(--fg-2)',
    fontVariantNumeric: 'tabular-nums',
  },
  activityType: { color: 'var(--fg)' },
  activityActor: { color: 'var(--fg-2)' },
  activityTarget: {
    color: 'var(--fg-3)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  activitySep: { color: 'var(--fg-4)' },
  activityAgo: {
    color: 'var(--fg-4)',
    textAlign: 'right',
  },
  activityMuted: {
    padding: '14px 16px',
    color: 'var(--fg-4)',
    fontSize: 12,
    fontStyle: 'italic',
    listStyle: 'none',
  },
  activityError: {
    color: 'var(--danger)',
    fontSize: 11,
    padding: '10px 14px',
  },
};
