// Per-post analytics drilldown (Task 25c, extended 25b-csv-drilldown).
// Mounted at /admin/analytics/posts/:postId — shows the post title, total
// hits in the active window, and a daily timeseries chart. Range chips
// mirror the parent Analytics page; arbitrary `since:` and `range:`
// tokens carried over from the parent's URL state are accepted as-is so
// the drilldown chart matches what the user was just looking at.

import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { apiAnalytics } from '../../api/analytics.js';

const RANGE_PRESETS = [
  { id: '7d', label: '7 天' },
  { id: '30d', label: '30 天' },
  { id: '90d', label: '90 天' },
];

function isAcceptedRange(token) {
  if (typeof token !== 'string') return false;
  if (RANGE_PRESETS.some((p) => p.id === token)) return true;
  if (token.startsWith('since:') || token.startsWith('range:')) return true;
  return false;
}

function formatRangeLabel(token) {
  if (token.startsWith('since:')) return `自 ${token.slice('since:'.length)}`;
  if (token.startsWith('range:')) {
    const [a, b] = token.slice('range:'.length).split('..');
    return `${a} → ${b}`;
  }
  return null;
}

export default function AnalyticsPostDetail() {
  const { postId } = useParams();
  const [params, setParams] = useSearchParams();
  const rawRange = params.get('range');
  const range = isAcceptedRange(rawRange) ? rawRange : '30d';
  const customLabel = formatRangeLabel(range);

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    apiAnalytics.postTimeseries(postId, range)
      .then((res) => alive && (setData(res), setError(null)))
      .catch((e) => alive && setError(e?.detail || e?.message || 'load failed'))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [postId, range]);

  return (
    <div data-testid="analytics-post-detail">
      <header style={styles.header}>
        <div>
          <Link to={`/admin/analytics?range=${range}`} style={styles.back}>
            ← 返回数据分析
          </Link>
          <h1 style={styles.h1}>
            <code style={styles.code}>{postId}</code>
            {data?.title && <span style={styles.title}> · {data.title}</span>}
          </h1>
          <p style={styles.lead}>
            单篇文章的每日访问量。今天的数字是实时的（来自 hit_events），
            历史天数来自 hit_daily 汇总。
          </p>
        </div>
        <div style={styles.rangeRow}>
          {customLabel && (
            <span
              data-testid="range-custom-label"
              style={{
                fontSize: 11,
                color: 'var(--accent)',
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                marginRight: 6,
              }}
              title="窗口由父页 ?range=... 传递"
            >{customLabel}</span>
          )}
          {RANGE_PRESETS.map((p) => (
            <button
              type="button"
              key={p.id}
              data-testid={`range-${p.id}`}
              onClick={() => setParams({ range: p.id })}
              style={{
                ...styles.rangeBtn,
                ...(range === p.id ? styles.rangeBtnActive : null),
              }}
            >{p.label}</button>
          ))}
        </div>
      </header>

      {loading && <div className="pad">加载中…</div>}

      {error && (
        <div className="pad err" role="alert" data-testid="post-detail-error">
          {error}
        </div>
      )}

      {!loading && !error && data && (
        <>
          <div style={styles.kpis}>
            <div style={styles.kpi}>
              <div style={styles.kpiLabel}>窗口总访问</div>
              <div style={styles.kpiValue} data-testid="post-detail-total">
                {data.total.toLocaleString()}
              </div>
              <div style={styles.kpiHint}>{data.timeseries.length} 天</div>
            </div>
          </div>

          <Section title="每日访问">
            <HitsChart series={data.timeseries} />
          </Section>
        </>
      )}
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section style={styles.section}>
      <div style={styles.sectionTitle}>{title}</div>
      <div style={styles.sectionBody}>{children}</div>
    </section>
  );
}

function HitsChart({ series }) {
  const width = 720;
  const height = 180;
  const padX = 24;
  const padY = 16;
  const data = useMemo(() => series.map((p) => ({
    date: p.date,
    hits: Number(p.hits ?? 0),
  })), [series]);
  if (!data.length) return <div style={styles.muted}>这段时间内没有访问。</div>;
  const max = Math.max(1, ...data.map((d) => d.hits));
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;
  const barGap = 2;
  const barW = Math.max(1, innerW / data.length - barGap);
  return (
    <div style={styles.chartShell}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label={`每日访问，${data.length} 天，最高 ${max}`}
      >
        <line
          x1={padX} x2={width - padX}
          y1={height - padY} y2={height - padY}
          stroke="var(--line)" strokeWidth="1"
        />
        {data.map((d, i) => {
          const h = (d.hits / max) * innerH;
          const x = padX + i * (barW + barGap);
          const y = height - padY - h;
          return (
            <rect
              key={d.date}
              data-testid={`bar-${d.date}`}
              x={x} y={y} width={barW} height={Math.max(1, h)}
              fill="var(--accent)"
            >
              <title>{`${d.date}: ${d.hits}`}</title>
            </rect>
          );
        })}
      </svg>
    </div>
  );
}

const styles = {
  header: {
    marginBottom: 18,
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: 16,
    flexWrap: 'wrap',
  },
  back: { fontSize: 12, color: 'var(--accent)', textDecoration: 'none' },
  h1: { fontSize: 18, margin: '4px 0 0', fontWeight: 600, color: 'var(--fg)' },
  code: {
    fontFamily: "'JetBrains Mono', monospace",
    color: 'var(--accent)',
    fontSize: 13,
    fontWeight: 500,
  },
  title: { color: 'var(--fg-2)', fontWeight: 400, marginLeft: 6 },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  rangeRow: { display: 'flex', gap: 4, alignItems: 'center' },
  rangeBtn: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '6px 12px',
    fontFamily: 'inherit',
    fontSize: 11,
    borderRadius: 4,
    cursor: 'pointer',
    letterSpacing: '0.04em',
  },
  rangeBtnActive: {
    background: 'var(--bg)',
    color: 'var(--accent)',
    borderColor: 'var(--accent)',
  },
  kpis: { display: 'flex', gap: 12, marginBottom: 16 },
  kpi: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    padding: '12px 16px',
    borderRadius: 4,
    minWidth: 120,
  },
  kpiLabel: { fontSize: 11, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.06em' },
  kpiValue: { fontSize: 24, color: 'var(--accent)', fontWeight: 600, margin: '4px 0' },
  kpiHint: { fontSize: 11, color: 'var(--fg-3)' },
  section: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 4,
    marginBottom: 12,
  },
  sectionTitle: {
    padding: '8px 12px',
    borderBottom: '1px solid var(--line)',
    fontSize: 12,
    color: 'var(--fg-3)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  sectionBody: { padding: 12 },
  chartShell: { padding: 4 },
  muted: { color: 'var(--fg-3)', fontSize: 12 },
};
