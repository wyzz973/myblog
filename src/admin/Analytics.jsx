import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiAnalytics } from '../api/analytics.js';

const RANGES = [
  { id: '7d', label: '7 天' },
  { id: '30d', label: '30 天' },
  { id: '90d', label: '90 天' },
];

export default function Analytics() {
  const [range, setRange] = useState('30d');
  const [bundle, setBundle] = useState(null);
  const [posts, setPosts] = useState(null);
  const [tags, setTags] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    Promise.all([
      apiAnalytics.bundle(range),
      apiAnalytics.posts(range),
      apiAnalytics.tags(range),
    ])
      .then(([b, p, t]) => {
        if (!mounted) return;
        setBundle(b);
        setPosts(p);
        setTags(t);
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
  }, [range]);

  return (
    <div>
      <header style={styles.header}>
        <div>
          <h1 style={styles.h1}>数据分析</h1>
          <p style={styles.lead}>查看所选时间窗口内的访问趋势和内容表现。</p>
        </div>
        <div style={styles.rangeRow}>
          {RANGES.map((r) => {
            const active = r.id === range;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => setRange(r.id)}
                style={{
                  ...styles.rangeBtn,
                  ...(active ? styles.rangeBtnActive : null),
                }}
              >
                {r.label}
              </button>
            );
          })}
          <SinceDatePicker range={range} onChange={setRange} />
          <ExportCsvButton range={range} />
        </div>
      </header>

      {loading && <div style={styles.muted}>正在加载数据...</div>}
      {error && !loading && <div style={styles.error}>错误：{error}</div>}

      {!loading && !error && bundle && (
        <>
          <Section title="每日访问">
            <HitsChart series={bundle.timeseries || []} />
          </Section>

          <div style={styles.grid}>
            <Section title="热门路径">
              <RankTable
                rows={(bundle.top_paths || []).map((r) => ({
                  label: r.path,
                  count: r.hits,
                }))}
              />
            </Section>
            <Section title="来源排行">
              <RankTable
                rows={(bundle.top_referrers || []).map((r) => ({
                  label: r.referrer || '直接访问',
                  count: r.hits,
                }))}
              />
            </Section>
            <Section title="国家 / 地区排行">
              <RankTable
                rows={(bundle.top_countries || []).map((r) => ({
                  label: r.country || '未知',
                  count: r.hits,
                }))}
              />
            </Section>
            <Section title="热门文章">
              <RankTable
                rows={(posts || []).map((r) => ({
                  label: r.title || r.post_id,
                  count: r.hits,
                  href: `/admin/analytics/posts/${encodeURIComponent(r.post_id)}?range=${range}`,
                  testId: `hot-post-${r.post_id}`,
                }))}
              />
            </Section>
            <Section title="热门标签">
              <RankTable
                rows={(tags || []).map((r) => ({
                  label: r.name || r.slug,
                  count: r.hits,
                }))}
              />
            </Section>
          </div>
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
  // Inline SVG bar chart. No libraries.
  const width = 720;
  const height = 180;
  const padX = 24;
  const padY = 16;

  const data = useMemo(() => series.map((p) => ({
    date: p.date,
    hits: Number(p.hits ?? 0),
  })), [series]);

  if (!data.length) {
    return <div style={styles.muted}>这个时间范围内暂无访问。</div>;
  }
  const max = Math.max(1, ...data.map((d) => d.hits));
  const nonZero = data.reduce((n, d) => n + (d.hits > 0 ? 1 : 0), 0);
  const innerW = width - padX * 2;
  const innerH = height - padY * 2;
  const barGap = 2;
  // 单点的特殊情况：把柱宽限到合理上限并居中渲染，否则 1 根柱占满整个轴
  // 视觉空旷。多点时按等分计算。
  let barW;
  let barX0;
  if (data.length === 1) {
    barW = Math.min(64, innerW / 2);
    barX0 = padX + (innerW - barW) / 2;
  } else {
    barW = Math.max(1, innerW / data.length - barGap);
    barX0 = padX;
  }
  // 「零访问日」用 1px baseline tick（var(--line-2)）来让轴上每一天都有
  // 可见标记，避免 30 天里只有一根柱时主视图看起来像是断的。
  const baselineY = height - padY;
  const tickH = 2;

  return (
    <div style={styles.chartShell}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label={`每日访问，${data.length} 天，最高 ${max}`}
      >
        <line
          x1={padX}
          x2={width - padX}
          y1={baselineY}
          y2={baselineY}
          stroke="var(--line)"
          strokeWidth="1"
        />
        {data.map((d, i) => {
          const h = (d.hits / max) * innerH;
          const x = barX0 + i * (data.length === 1 ? 0 : (barW + barGap));
          const y = baselineY - h;
          if (d.hits === 0) {
            return (
              <rect
                key={`${d.date}-${i}`}
                x={x}
                y={baselineY - tickH}
                width={Math.max(1, barW)}
                height={tickH}
                fill="var(--line-2)"
              >
                <title>{`${d.date}: 0`}</title>
              </rect>
            );
          }
          return (
            <rect
              key={`${d.date}-${i}`}
              x={x}
              y={y}
              width={barW}
              height={h}
              fill="var(--accent)"
              opacity={0.85}
            >
              <title>{`${d.date}: ${d.hits}`}</title>
            </rect>
          );
        })}
        <text
          x={padX}
          y={padY - 2}
          fill="var(--fg-4)"
          fontSize="10"
          fontFamily="'JetBrains Mono', ui-monospace, monospace"
        >
          最高 {max.toLocaleString()}
          {nonZero < data.length && ` · 仅 ${nonZero} / ${data.length} 天有访问`}
        </text>
      </svg>
      <div style={styles.chartAxis}>
        <span>{data[0].date}</span>
        <span>{data[data.length - 1].date}</span>
      </div>
    </div>
  );
}

function RankTable({ rows }) {
  if (!rows || rows.length === 0) {
    return <div style={styles.muted}>暂无数据。</div>;
  }
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <table style={styles.table}>
      <tbody>
        {rows.map((r, i) => {
          const pct = (r.count / max) * 100;
          const labelCell = r.href ? (
            <Link
              to={r.href}
              data-testid={r.testId}
              style={styles.tdLabelLink}
              title={r.label}
            >{r.label}</Link>
          ) : (
            <span title={r.label}>{r.label}</span>
          );
          return (
            <tr key={`${r.label}-${i}`}>
              <td style={styles.tdRank}>{i + 1}</td>
              <td style={styles.tdLabel}>{labelCell}</td>
              <td style={styles.tdCount}>{r.count.toLocaleString()}</td>
              <td style={styles.tdBar}>
                <div style={styles.barShell}>
                  <div style={{ ...styles.barFill, width: `${pct}%` }} />
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
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
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  rangeRow: { display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' },
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
    background: 'color-mix(in oklab, var(--accent) 16%, transparent)',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    color: 'var(--fg)',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: 14,
  },
  section: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '12px 14px 14px',
    marginBottom: 14,
  },
  sectionTitle: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
    marginBottom: 10,
  },
  sectionBody: {},
  chartShell: { width: '100%' },
  chartAxis: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 10,
    color: 'var(--fg-4)',
    marginTop: 4,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 12,
    color: 'var(--fg-2)',
    fontVariantNumeric: 'tabular-nums',
  },
  tdRank: {
    width: 22,
    color: 'var(--fg-4)',
    padding: '4px 6px 4px 0',
    textAlign: 'right',
  },
  tdLabel: {
    padding: '4px 8px 4px 0',
    color: 'var(--fg)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    maxWidth: 140,
  },
  tdLabelLink: {
    color: 'var(--accent)',
    textDecoration: 'none',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    display: 'inline-block',
    maxWidth: '100%',
  },
  tdCount: {
    padding: '4px 8px 4px 0',
    textAlign: 'right',
    color: 'var(--accent)',
    width: 64,
  },
  tdBar: { padding: '4px 0', width: '40%' },
  barShell: {
    height: 6,
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    background: 'var(--accent)',
    opacity: 0.7,
  },
  muted: { color: 'var(--fg-3)', fontSize: 12 },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
  },
};

// Task 25a: download per-post hits as CSV. Uses the authenticated
// `apiAnalytics.downloadPostsCsv(range)` which builds a blob URL and
// triggers a synthetic <a download> click — works in plain browsers
// without any extra deps.
// Task 25b: custom since-date picker. The active range is encoded as
// `since:YYYY-MM-DD` so the same `range` prop drives bundle/posts/tags
// fetches AND the CSV download. Value clears (=> falls back to a chip
// preset) when the input is emptied.
function SinceDatePicker({ range, onChange }) {
  // Decode the active range into (from, to). `since:YYYY-MM-DD` and
  // `range:YYYY-MM-DD..YYYY-MM-DD` both populate the from box; only
  // `range:` also populates the to box.
  let fromVal = '';
  let toVal = '';
  if (typeof range === 'string') {
    if (range.startsWith('since:')) {
      fromVal = range.slice('since:'.length);
    } else if (range.startsWith('range:')) {
      const [a, b] = range.slice('range:'.length).split('..');
      if (a && b) { fromVal = a; toVal = b; }
    }
  }
  const todayUtc = (() => {
    const d = new Date();
    d.setUTCHours(0, 0, 0, 0);
    return d.toISOString().slice(0, 10);
  })();

  function emit(nextFrom, nextTo) {
    if (!nextFrom && !nextTo) {
      onChange('30d');
      return;
    }
    if (nextFrom && nextTo) {
      // Inverted dates: keep the existing token; let the user fix the input.
      if (nextTo < nextFrom) return;
      onChange(`range:${nextFrom}..${nextTo}`);
      return;
    }
    if (nextFrom) onChange(`since:${nextFrom}`);
    else onChange('30d'); // only `to` filled is meaningless on its own
  }

  return (
    <span style={{ display: 'inline-flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}>
      <input
        type="date"
        value={fromVal}
        max={todayUtc}
        onChange={(e) => emit(e.target.value, toVal)}
        style={fromVal ? { ...styles.rangeBtn, ...styles.rangeBtnActive } : styles.rangeBtn}
        data-testid="analytics-since-date"
        data-active={fromVal ? 'true' : undefined}
        aria-label="自定义起始日期"
      />
      <span style={{ fontSize: 11, color: 'var(--fg-4)' }}>→</span>
      <input
        type="date"
        value={toVal}
        max={todayUtc}
        min={fromVal || undefined}
        onChange={(e) => emit(fromVal, e.target.value)}
        style={toVal ? { ...styles.rangeBtn, ...styles.rangeBtnActive } : styles.rangeBtn}
        data-testid="analytics-to-date"
        data-active={toVal ? 'true' : undefined}
        aria-label="自定义结束日期 (可选)"
        placeholder="今天"
      />
    </span>
  );
}

function ExportCsvButton({ range }) {
  const [busy, setBusy] = useState(false);
  async function onClick() {
    setBusy(true);
    try {
      await apiAnalytics.downloadPostsCsv(range);
    } catch {
      /* surface via inline status next round; for now silent */
    } finally {
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      style={styles.rangeBtn}
      data-testid="analytics-export-csv"
      title="导出 per-post CSV"
    >
      {busy ? '导出中…' : '导出 CSV'}
    </button>
  );
}
