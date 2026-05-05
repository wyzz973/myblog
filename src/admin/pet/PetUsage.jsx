import { useEffect, useMemo, useState } from 'react';
import { apiPet } from '../../api/pet.js';
import {
  buildBars,
  groupByDay,
  legendFromData,
  SOURCE_COLORS,
  SOURCE_LABELS,
} from './petUsageChart.js';

export default function PetUsage() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    apiPet.getUsage()
      .then((res) => mounted && (setItems(res.items || []), setError(null)))
      .catch((e) => mounted && setError(e?.detail || e?.message || '加载用量失败'))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  if (loading) return <div className="hint pad">加载中...</div>;
  if (error) return <div className="err pad">{error}</div>;

  return (
    <div className="form pad">
      <h2 style={{ margin: 0, fontSize: 14 }}>用量统计</h2>
      <UsageChart items={items} />
      <div className="pet-usage-table">
        <div className="pet-usage-head">
          <span>日期</span><span>模式</span><span>来源</span><span>调用</span><span>Token</span>
        </div>
        {items.map((row, i) => (
          <div className="pet-usage-row" key={`${row.day}-${row.mode}-${row.source}-${i}`}>
            <span>{row.day}</span>
            <span>{row.mode}</span>
            <span>{row.source}</span>
            <span>{row.calls}</span>
            <span>{row.estimated_total_tokens}</span>
          </div>
        ))}
        {items.length === 0 && <div className="hint">暂无用量记录</div>}
      </div>
    </div>
  );
}

// Daily stacked bar — one column per day, segments per source.
// Inline SVG, no chart library. Empty state renders a placeholder.
function UsageChart({ items }) {
  const daily = useMemo(() => groupByDay(items), [items]);
  const W = 720;
  const H = 180;
  const PAD_X = 28;
  const PAD_Y = 16;
  const bars = useMemo(
    () => buildBars(daily, { width: W, height: H, padX: PAD_X, padY: PAD_Y }),
    [daily],
  );
  const legend = useMemo(() => legendFromData(daily), [daily]);

  if (daily.length === 0) {
    return (
      <div data-testid="pet-usage-chart-empty" style={{ color: 'var(--fg-4)', fontSize: 12, padding: '8px 0' }}>
        暂无图表数据。
      </div>
    );
  }

  return (
    <div data-testid="pet-usage-chart" style={{ marginTop: 12, marginBottom: 12 }}>
      <div
        data-testid="pet-usage-legend"
        style={{
          display: 'flex',
          gap: 14,
          flexWrap: 'wrap',
          fontSize: 11,
          color: 'var(--fg-3)',
          marginBottom: 6,
        }}
      >
        {legend.map((e) => (
          <span
            key={e.source}
            data-testid={`pet-usage-legend-${e.source}`}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <span
              aria-hidden="true"
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: 2,
                background: e.color,
              }}
            />
            <span>{e.label}</span>
          </span>
        ))}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label={`pet usage: ${daily.length} days`}
      >
        <line
          x1={PAD_X}
          x2={W - PAD_X}
          y1={H - PAD_Y}
          y2={H - PAD_Y}
          stroke="var(--line)"
          strokeWidth="1"
        />
        {bars.map((bar) =>
          bar.segments.map((seg, i) => (
            <rect
              key={`${bar.day}-${seg.source}-${i}`}
              x={seg.x}
              y={seg.y}
              width={seg.w}
              height={seg.h}
              fill={SOURCE_COLORS[seg.source] || 'var(--fg-4)'}
              opacity={0.85}
              data-testid={`pet-usage-bar-${bar.day}-${seg.source}`}
            >
              <title>{`${bar.day} · ${SOURCE_LABELS[seg.source] || seg.source}: ${seg.calls}`}</title>
            </rect>
          )),
        )}
        {bars.length > 0 && (
          <>
            <text
              x={PAD_X}
              y={PAD_Y - 2}
              fill="var(--fg-4)"
              fontSize="10"
              fontFamily="'JetBrains Mono', ui-monospace, monospace"
            >
              {bars[0].day}
            </text>
            <text
              x={W - PAD_X}
              y={PAD_Y - 2}
              fill="var(--fg-4)"
              fontSize="10"
              textAnchor="end"
              fontFamily="'JetBrains Mono', ui-monospace, monospace"
            >
              {bars[bars.length - 1].day}
            </text>
          </>
        )}
      </svg>
    </div>
  );
}
