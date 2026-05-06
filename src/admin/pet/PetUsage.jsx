import { useEffect, useMemo, useState } from 'react';
import { apiPet } from '../../api/pet.js';
import {
  buildBars,
  buildCostLine,
  buildPieSlices,
  formatUSD,
  groupByDay,
  groupByMode,
  groupCostByDay,
  legendFromData,
  SOURCE_COLORS,
  SOURCE_LABELS,
} from './petUsageChart.js';

export default function PetUsage() {
  const [items, setItems] = useState([]);
  const [rates, setRates] = useState(null); // null until first /cost-rates fetch lands
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  async function reloadRates() {
    try {
      const r = await apiPet.getCostRates();
      setRates(r?.rates || null);
    } catch {
      // Cost-rates endpoint failure is non-fatal — chart falls back to
      // the bundled defaults in petUsageChart.js.
      setRates(null);
    }
  }

  useEffect(() => {
    let mounted = true;
    Promise.all([apiPet.getUsage(), apiPet.getCostRates().catch(() => null)])
      .then(([usage, rateRes]) => {
        if (!mounted) return;
        setItems(usage?.items || []);
        setRates(rateRes?.rates || null);
        setError(null);
      })
      .catch((e) => mounted && setError(e?.detail || e?.message || '加载用量失败'))
      .finally(() => mounted && setLoading(false));
    return () => { mounted = false; };
  }, []);

  if (loading) return <div className="hint pad">加载中...</div>;
  if (error) return <div className="err pad">{error}</div>;

  return (
    <div className="form pad">
      <h2 style={{ margin: 0, fontSize: 14 }}>用量统计</h2>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'flex-start' }}>
        <div style={{ flex: '1 1 480px', minWidth: 320 }}>
          <UsageChart items={items} />
          <CostChart items={items} rates={rates} />
          <CostRatesEditor rates={rates} onChanged={reloadRates} />
        </div>
        <div style={{ flex: '0 0 220px' }}>
          <ModePieChart items={items} />
        </div>
      </div>
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

// Per-mode donut chart. Aggregates from the same flat /pet/usage rows
// and renders an SVG path per mode + a side legend with call totals.
function ModePieChart({ items }) {
  const modes = useMemo(() => groupByMode(items), [items]);
  const SIZE = 180;
  const slices = useMemo(
    () => buildPieSlices(modes, { cx: SIZE / 2, cy: SIZE / 2, r: 80, inner: 38 }),
    [modes],
  );
  if (slices.length === 0) {
    return (
      <div data-testid="pet-usage-pie-empty" style={{ color: 'var(--fg-4)', fontSize: 12, padding: '8px 0' }}>
        暂无模式分布。
      </div>
    );
  }
  const total = modes.reduce((a, m) => a + m.calls, 0);
  return (
    <div data-testid="pet-usage-pie">
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 6 }}>按模式分布</div>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        width={SIZE}
        height={SIZE}
        role="img"
        aria-label={`pet usage by mode (${modes.length} modes)`}
      >
        {slices.map((s) => (
          <path
            key={s.mode}
            d={s.path}
            fill={s.color}
            opacity={0.85}
            stroke="var(--bg-2)"
            strokeWidth="1"
            data-testid={`pet-usage-pie-slice-${s.mode}`}
          >
            <title>{`${s.mode}: ${s.calls} (${(s.frac * 100).toFixed(1)}%)`}</title>
          </path>
        ))}
        <text
          x={SIZE / 2}
          y={SIZE / 2}
          textAnchor="middle"
          dominantBaseline="central"
          fill="var(--fg-3)"
          fontSize="11"
          fontFamily="'JetBrains Mono', ui-monospace, monospace"
        >
          {total.toLocaleString()}
        </text>
      </svg>
      <ul
        data-testid="pet-usage-pie-legend"
        style={{
          listStyle: 'none', padding: 0, margin: '6px 0 0',
          display: 'flex', flexDirection: 'column', gap: 4, fontSize: 11,
        }}
      >
        {modes.map((m) => (
          <li
            key={m.mode}
            data-testid={`pet-usage-pie-legend-${m.mode}`}
            style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--fg-2)' }}
          >
            <span
              aria-hidden="true"
              style={{
                width: 8, height: 8, borderRadius: 1, background: m.color,
                flexShrink: 0,
              }}
            />
            <span style={{ flex: 1, fontFamily: 'JetBrains Mono, monospace' }}>{m.mode}</span>
            <span style={{ color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums' }}>
              {m.calls}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Daily estimated-cost line chart (Task 26c). The math lives in
// petUsageChart.js (rowCostUSD + groupCostByDay + buildCostLine) and
// applies per-provider $/M token rates to in/out token splits. Cache
// hits / fallbacks / rate-limited calls cost zero.
function CostChart({ items, rates }) {
  // rates is either null (use built-in defaults) or a {provider: {in_per_m, out_per_m}} map.
  const daily = useMemo(() => groupCostByDay(items, rates || undefined), [items, rates]);
  const W = 720;
  const H = 120;
  const PAD_X = 28;
  const PAD_Y = 16;
  const line = useMemo(
    () => buildCostLine(daily, { width: W, height: H, padX: PAD_X, padY: PAD_Y }),
    [daily],
  );
  const total = useMemo(() => daily.reduce((a, d) => a + d.cost, 0), [daily]);

  if (daily.length === 0 || total === 0) {
    return (
      <div data-testid="pet-usage-cost-empty" style={{ color: 'var(--fg-4)', fontSize: 12, padding: '8px 0' }}>
        暂无估算成本（缓存或降级调用计为 $0）。
      </div>
    );
  }

  return (
    <div data-testid="pet-usage-cost" style={{ marginTop: 12 }}>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 8,
        fontSize: 11, color: 'var(--fg-3)', marginBottom: 6,
      }}>
        <span>窗口估算成本</span>
        <strong
          data-testid="pet-usage-cost-total"
          style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--accent)' }}
        >{formatUSD(total)}</strong>
        <span style={{ color: 'var(--fg-4)' }}>· {daily.length} 天 · 按提供商 $/M token 估算</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
        role="img"
        aria-label={`pet usage estimated cost across ${daily.length} days`}
      >
        <line
          x1={PAD_X} x2={W - PAD_X}
          y1={H - PAD_Y} y2={H - PAD_Y}
          stroke="var(--line)" strokeWidth="1"
        />
        <polyline
          points={line.points}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          data-testid="pet-usage-cost-line"
        />
        {line.dots.map((d) => (
          <circle
            key={d.day}
            cx={d.cx}
            cy={d.cy}
            r="2.5"
            fill="var(--accent)"
            data-testid={`pet-usage-cost-dot-${d.day}`}
          >
            <title>{`${d.day}: ${formatUSD(d.cost)}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

// Task 36: per-provider cost-rate editor.
//
// Collapsed by default behind ⚙ to keep the usage page focused on the
// charts. Saving one provider's rates triggers a parent reload so the
// cost line redraws against the new rate immediately.
const RATES_PROVIDERS = ['anthropic', 'zhipu', 'qwen', 'doubao', 'deepseek'];

function CostRatesEditor({ rates, onChanged }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({});      // provider -> {in_per_m, out_per_m}
  const [savingFor, setSavingFor] = useState(null);
  const [error, setError] = useState(null);

  function valueFor(provider, field) {
    if (draft[provider] && draft[provider][field] !== undefined) {
      return draft[provider][field];
    }
    if (rates && rates[provider] && rates[provider][field] !== undefined) {
      return rates[provider][field];
    }
    return '';
  }

  function setField(provider, field, raw) {
    setDraft((prev) => ({
      ...prev,
      [provider]: { ...(prev[provider] || {}), [field]: raw },
    }));
  }

  async function saveOne(provider) {
    const cur = draft[provider];
    if (!cur) return;
    setSavingFor(provider);
    setError(null);
    try {
      const inN = Number(cur.in_per_m ?? rates?.[provider]?.in_per_m ?? 0);
      const outN = Number(cur.out_per_m ?? rates?.[provider]?.out_per_m ?? 0);
      if (Number.isNaN(inN) || Number.isNaN(outN) || inN < 0 || outN < 0) {
        throw new Error('rate must be a non-negative number');
      }
      await apiPet.setCostRate({ provider, in_per_m: inN, out_per_m: outN });
      setDraft((prev) => {
        const { [provider]: _, ...rest } = prev;
        return rest;
      });
      if (typeof onChanged === 'function') await onChanged();
    } catch (e) {
      setError(`${provider}: ${e?.detail || e?.message || 'save failed'}`);
    } finally {
      setSavingFor(null);
    }
  }

  return (
    <div data-testid="pet-cost-rates-editor" style={{ marginTop: 12 }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        data-testid="pet-cost-rates-toggle"
        aria-expanded={open}
        style={{ fontSize: 11, color: 'var(--fg-3)' }}
      >{open ? '收起' : '⚙ 设置成本费率'}</button>

      {open && (
        <div
          data-testid="pet-cost-rates-panel"
          style={{
            marginTop: 8, padding: '10px 12px',
            border: '1px dashed var(--line)', borderRadius: 4,
            background: 'var(--bg)',
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 8 }}>
            按 USD / 1M tokens 设置每个 provider 的输入价 / 输出价。未配置 API key 的 provider 无法设置费率（404）。
          </div>
          {error && (
            <div data-testid="pet-cost-rates-error" style={{
              fontSize: 11, color: 'var(--danger)', marginBottom: 8,
            }} role="alert">{error}</div>
          )}
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', color: 'var(--fg-4)', fontSize: 10 }}>provider</th>
                <th style={{ textAlign: 'right', color: 'var(--fg-4)', fontSize: 10 }}>输入 $/M</th>
                <th style={{ textAlign: 'right', color: 'var(--fg-4)', fontSize: 10 }}>输出 $/M</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {RATES_PROVIDERS.map((p) => {
                const isDirty = Boolean(draft[p]);
                return (
                  <tr key={p} data-testid={`pet-cost-rate-row-${p}`}>
                    <td><code>{p}</code></td>
                    <td style={{ textAlign: 'right' }}>
                      <input
                        type="number"
                        step="0.01"
                        min={0}
                        value={valueFor(p, 'in_per_m')}
                        onChange={(e) => setField(p, 'in_per_m', e.target.value)}
                        data-testid={`pet-cost-rate-in-${p}`}
                        style={{ width: 80, textAlign: 'right' }}
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <input
                        type="number"
                        step="0.01"
                        min={0}
                        value={valueFor(p, 'out_per_m')}
                        onChange={(e) => setField(p, 'out_per_m', e.target.value)}
                        data-testid={`pet-cost-rate-out-${p}`}
                        style={{ width: 80, textAlign: 'right' }}
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        type="button"
                        disabled={!isDirty || savingFor === p}
                        onClick={() => saveOne(p)}
                        data-testid={`pet-cost-rate-save-${p}`}
                        className="primary"
                      >{savingFor === p ? 'saving…' : '保存'}</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
