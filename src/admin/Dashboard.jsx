import { useEffect, useState } from 'react';
import { apiAdmin } from '../api/admin.js';

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
        <h1 style={styles.h1}>Dashboard</h1>
        <p style={styles.lead}>Snapshot of site activity.</p>
      </header>
      <div style={styles.grid}>
        {tiles.map((t) => (
          <Card key={t.key} title={t.title} headline={t.headline} subs={t.subs} />
        ))}
      </div>
    </div>
  );
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
    },
    {
      key: 'likes',
      title: 'Likes total',
      headline: fmt(d.likes?.total),
      subs: [['last 7d', fmt(d.likes?.last_7d)]],
    },
    {
      key: 'comments',
      title: 'Comments',
      headline: fmt(d.comments?.total),
      subs: [['pending', fmt(d.comments?.pending)]],
    },
    {
      key: 'posts',
      title: 'Posts published',
      headline: fmt(d.posts?.published),
      subs: [
        ['draft', fmt(d.posts?.draft)],
        ['scheduled', fmt(d.posts?.scheduled)],
      ],
    },
    {
      key: 'media',
      title: 'Media items',
      headline: fmt(d.media?.count),
      subs: [],
    },
  ];
}

function fmt(v) {
  if (v == null) return '—';
  if (typeof v === 'number') return v.toLocaleString();
  return String(v);
}

function Card({ title, headline, subs }) {
  return (
    <div style={styles.card}>
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
    </div>
  );
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
};
