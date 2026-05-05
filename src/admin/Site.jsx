// /admin/site is now the theme-only page (PRD §5.2 rename — site
// identity moved to /admin/site-identity in Task 6). Replaces the
// freeform oklch text inputs with a swatch-based picker that emits
// canonical oklch() and a live preview pane mirroring the public hero.

import { useEffect, useMemo, useState } from 'react';
import { apiSite } from '../api/site.js';
import { formatOklch, parseOklch, THEME_DEFAULTS } from './oklch.js';

const THEME_FIELDS = [
  { key: 'accent_color', label: 'accent', hint: 'main brand color — buttons, dot, focus rings' },
  { key: 'accent2_color', label: 'accent 2', hint: 'secondary highlight (e.g. amber chips)' },
  { key: 'violet_color', label: 'violet', hint: '#ai / #ml tag tint' },
  { key: 'danger_color', label: 'danger', hint: 'destructive actions, error borders' },
];

function norm(v) {
  if (v == null) return '';
  return String(v);
}

export default function Site() {
  const [theme, setTheme] = useState(null);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiSite
      .getTheme()
      .then((t) => {
        if (!mounted) return;
        setTheme(t);
        setDraft({ ...t });
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

  useEffect(() => {
    if (!toast) return undefined;
    const id = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(id);
  }, [toast]);

  const dirty = useMemo(() => {
    if (!theme || !draft) return false;
    return THEME_FIELDS.some((f) => norm(theme[f.key]) !== norm(draft[f.key]));
  }, [theme, draft]);

  function setField(k, v) {
    setDraft((d) => ({ ...d, [k]: v }));
  }

  function resetField(k) {
    setField(k, THEME_DEFAULTS[k] || '');
  }

  async function save(e) {
    e?.preventDefault?.();
    if (!draft || !dirty) return;
    setSaving(true);
    try {
      const patch = {};
      for (const f of THEME_FIELDS) {
        if (norm(theme[f.key]) !== norm(draft[f.key])) {
          patch[f.key] = draft[f.key] === '' ? null : draft[f.key];
        }
      }
      const updated = await apiSite.putTheme(patch);
      setTheme(updated);
      setDraft({ ...updated });
      setToast('已保存');
    } catch (err) {
      setToast(`错误：${err?.detail || err.message}`);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={styles.muted}>正在加载主题...</div>;
  if (error) return <div style={styles.error}>错误：{error}</div>;
  if (!draft) return <div style={styles.muted}>暂无数据</div>;

  return (
    <div data-testid="theme-page">
      <header style={styles.header}>
        <h1 style={styles.h1}>
          <span style={styles.headN}>04</span>{' '}
          <span style={styles.headSlash}>/</span> 主题
        </h1>
        <p style={styles.lead}>
          调整公开站点的 OKLCH 颜色变量。每个色相用 <code>L / C / H</code>{' '}
          滑块控制，也可直接粘贴 <code>oklch()</code> 字符串。预览块实时反映改动；
          保存后 <code>PUT /api/admin/theme</code> 将值写入 site_meta。
        </p>
      </header>

      <form onSubmit={save}>
        <section style={styles.panel}>
          <div style={styles.panelHead}>
            <span style={styles.panelTitle}>颜色</span>
            <span style={styles.panelHint}>PUT /theme</span>
          </div>
          <div style={styles.panelBody}>
            {THEME_FIELDS.map((f) => (
              <ColorRow
                key={f.key}
                field={f}
                value={draft[f.key] ?? ''}
                onChange={(v) => setField(f.key, v)}
                onReset={() => resetField(f.key)}
                isDefault={draft[f.key] === THEME_DEFAULTS[f.key]}
              />
            ))}
          </div>
        </section>

        <ThemePreview theme={draft} />

        <div style={styles.actionRow}>
          <button
            type="submit"
            style={styles.btnPrimary}
            disabled={saving || !dirty}
            data-testid="save-theme-btn"
          >
            {saving ? '保存中...' : '保存'}
          </button>
          <button
            type="button"
            style={styles.btn}
            disabled={saving || !dirty}
            onClick={() => setDraft({ ...theme })}
          >
            重置改动
          </button>
          <span style={styles.dirtyHint}>
            {dirty ? '有未保存的更改' : '已与后端一致'}
          </span>
        </div>
      </form>

      {toast && <div style={styles.toast}>{toast}</div>}
    </div>
  );
}

function ColorRow({ field, value, onChange, onReset, isDefault }) {
  const parsed = parseOklch(value) || { l: 70, c: 0.15, h: 200 };

  function setLCH(next) {
    onChange(formatOklch(next));
  }

  return (
    <div style={styles.colorRow} data-testid={`color-${field.key}`}>
      <div style={styles.rowHead}>
        <span style={styles.rowLabel}>{field.label}</span>
        <span style={styles.rowHint}>{field.hint}</span>
      </div>
      <div style={styles.rowBody}>
        <div
          style={{
            ...styles.swatch,
            background: value || 'transparent',
          }}
          aria-hidden
          data-testid={`swatch-${field.key}`}
        />
        <div style={styles.controls}>
          <Slider
            label="L"
            min={0}
            max={100}
            step={1}
            value={parsed.l}
            onChange={(l) => setLCH({ ...parsed, l })}
            suffix="%"
            testid={`slider-l-${field.key}`}
          />
          <Slider
            label="C"
            min={0}
            max={0.4}
            step={0.005}
            value={parsed.c}
            onChange={(c) => setLCH({ ...parsed, c })}
            decimals={3}
            testid={`slider-c-${field.key}`}
          />
          <Slider
            label="H"
            min={0}
            max={360}
            step={1}
            value={parsed.h}
            onChange={(h) => setLCH({ ...parsed, h })}
            suffix="°"
            testid={`slider-h-${field.key}`}
          />
          <div style={styles.rawRow}>
            <input
              type="text"
              value={value ?? ''}
              onChange={(e) => onChange(e.target.value)}
              style={styles.rawInput}
              placeholder="oklch(72% 0.18 295)"
              data-testid={`raw-${field.key}`}
              spellCheck={false}
            />
            <button
              type="button"
              onClick={onReset}
              style={styles.rowResetBtn}
              disabled={isDefault}
              title={isDefault ? '已是默认' : '重置为默认值'}
              data-testid={`reset-${field.key}`}
            >
              默认
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Slider({ label, min, max, step, value, onChange, suffix = '', decimals = 0, testid }) {
  const display = decimals > 0 ? Number(value).toFixed(decimals) : Math.round(value);
  return (
    <label style={styles.sliderRow}>
      <span style={styles.sliderLabel}>{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={styles.sliderInput}
        data-testid={testid}
      />
      <span style={styles.sliderValue}>{display}{suffix}</span>
    </label>
  );
}

function ThemePreview({ theme }) {
  // Apply the candidate values via inline CSS variables so the preview
  // pane reflects edits without touching the global stylesheet.
  const previewVars = {
    '--accent': theme.accent_color || THEME_DEFAULTS.accent_color,
    '--accent-2': theme.accent2_color || THEME_DEFAULTS.accent2_color,
    '--violet': theme.violet_color || THEME_DEFAULTS.violet_color,
    '--danger': theme.danger_color || THEME_DEFAULTS.danger_color,
  };
  return (
    <section style={styles.panel} data-testid="theme-preview">
      <div style={styles.panelHead}>
        <span style={styles.panelTitle}>预览</span>
        <span style={styles.panelHint}>对照公开站 hero / button 样式</span>
      </div>
      <div style={{ ...styles.previewBox, ...previewVars }}>
        <div style={styles.previewHero}>
          <span style={styles.previewDot} />
          <span style={styles.previewBrand}>myblog</span>
          <span style={styles.previewMuted}>预览主题</span>
        </div>
        <div style={styles.previewButtons}>
          <button type="button" style={styles.previewBtnAccent}>主按钮</button>
          <button type="button" style={styles.previewBtnAccent2}>次要</button>
          <span style={styles.previewTagViolet}>#ai</span>
          <button type="button" style={styles.previewBtnDanger}>danger</button>
        </div>
      </div>
    </section>
  );
}

const styles = {
  header: { marginBottom: 18 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  headN: { color: 'var(--accent)', fontSize: 14, letterSpacing: '0.06em' },
  headSlash: { color: 'var(--fg-4)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0', maxWidth: 720, lineHeight: 1.6 },
  panel: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    marginBottom: 14,
  },
  panelHead: {
    padding: '10px 14px',
    borderBottom: '1px solid var(--line)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  panelTitle: {
    fontSize: 11,
    color: 'var(--fg-2)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  panelHint: { fontSize: 10, color: 'var(--fg-4)' },
  panelBody: { padding: 14, display: 'flex', flexDirection: 'column', gap: 14 },
  colorRow: {
    border: '1px dashed var(--line-2)',
    borderRadius: 4,
    padding: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  rowHead: { display: 'flex', alignItems: 'baseline', gap: 8 },
  rowLabel: { fontSize: 12, color: 'var(--fg)', letterSpacing: '0.04em' },
  rowHint: { fontSize: 10, color: 'var(--fg-4)' },
  rowBody: { display: 'flex', alignItems: 'flex-start', gap: 14 },
  swatch: {
    width: 64,
    height: 64,
    borderRadius: 6,
    border: '1px solid var(--line-2)',
    flexShrink: 0,
  },
  controls: { flex: 1, display: 'flex', flexDirection: 'column', gap: 6 },
  sliderRow: {
    display: 'grid',
    gridTemplateColumns: '20px 1fr 60px',
    alignItems: 'center',
    gap: 10,
    fontSize: 11,
    color: 'var(--fg-3)',
  },
  sliderLabel: { color: 'var(--fg-2)', fontWeight: 600 },
  sliderInput: {
    width: '100%',
    accentColor: 'var(--accent)',
  },
  sliderValue: { color: 'var(--fg-3)', textAlign: 'right', fontVariantNumeric: 'tabular-nums' },
  rawRow: { display: 'flex', gap: 6, marginTop: 4 },
  rawInput: {
    flex: 1,
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '5px 9px',
    fontFamily: 'inherit',
    fontSize: 11,
    borderRadius: 3,
    outline: 'none',
  },
  rowResetBtn: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    fontFamily: 'inherit',
    fontSize: 10,
    padding: '4px 10px',
    borderRadius: 3,
    cursor: 'pointer',
  },
  previewBox: {
    padding: 18,
    background: 'var(--bg)',
    borderRadius: 4,
    margin: 14,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
  },
  previewHero: { display: 'flex', alignItems: 'center', gap: 10 },
  previewDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
    background: 'var(--accent)',
    boxShadow: '0 0 10px color-mix(in oklab, var(--accent) 40%, transparent)',
  },
  previewBrand: { fontSize: 13, color: 'var(--fg)', fontWeight: 600 },
  previewMuted: { fontSize: 10, color: 'var(--fg-4)', letterSpacing: '0.08em' },
  previewButtons: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  previewBtnAccent: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    border: 0,
    padding: '6px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
  },
  previewBtnAccent2: {
    background: 'transparent',
    color: 'var(--accent-2)',
    border: '1px solid color-mix(in oklab, var(--accent-2) 40%, transparent)',
    padding: '5px 11px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 11,
    cursor: 'pointer',
  },
  previewTagViolet: {
    color: 'var(--violet)',
    background: 'color-mix(in oklab, var(--violet) 14%, transparent)',
    border: '1px solid color-mix(in oklab, var(--violet) 40%, transparent)',
    fontSize: 10,
    padding: '3px 8px',
    borderRadius: 999,
  },
  previewBtnDanger: {
    background: 'transparent',
    color: 'var(--danger)',
    border: '1px solid color-mix(in oklab, var(--danger) 60%, transparent)',
    padding: '5px 11px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 11,
    cursor: 'pointer',
  },
  actionRow: { display: 'flex', alignItems: 'center', gap: 10, padding: '14px 0' },
  dirtyHint: { color: 'var(--fg-4)', fontSize: 11 },
  btn: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '8px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 12,
    cursor: 'pointer',
  },
  btnPrimary: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    border: 0,
    padding: '8px 14px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  toast: {
    position: 'fixed',
    bottom: 20,
    right: 20,
    background: 'var(--bg-2)',
    border: '1px solid var(--accent)',
    color: 'var(--fg)',
    padding: '10px 14px',
    borderRadius: 4,
    fontSize: 12,
    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    zIndex: 60,
  },
  muted: { color: 'var(--fg-3)', fontSize: 12, padding: '24px 0' },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
  },
};
