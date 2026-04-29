import { useEffect, useState } from 'react';
import { apiSite } from '../api/site.js';

// Field set per backend `SiteIn` (routers/admin/site.py). The mission spec
// mentions `bio_md` / `avatar_id` / `name`, but the admin /site endpoint
// does NOT expose those — they live on /profile (handled by Profile.jsx).
// We surface only the fields the backend actually accepts here.
const SITE_FIELDS = [
  { key: 'handle', label: 'handle', placeholder: 'wangyang', kind: 'text' },
  { key: 'tagline', label: 'tagline', placeholder: 'a short one-liner', kind: 'text' },
  { key: 'email', label: 'contact email', placeholder: 'you@example.com', kind: 'text' },
  { key: 'github', label: 'github', placeholder: 'username', kind: 'text' },
  { key: 'footer_note', label: 'footer note', placeholder: '', kind: 'text' },
  {
    key: 'default_theme',
    label: 'default theme',
    kind: 'select',
    options: [
      { value: 'dark', label: 'dark' },
      { value: 'light', label: 'light' },
    ],
  },
  { key: 'launched_at', label: 'launched at (ISO date)', placeholder: '2026-01-01', kind: 'text' },
];

const THEME_FIELDS = [
  { key: 'accent_color', label: 'accent', placeholder: 'oklch(82% 0.17 152)' },
  { key: 'accent2_color', label: 'accent 2', placeholder: 'oklch(80% 0.15 70)' },
  { key: 'violet_color', label: 'violet', placeholder: 'oklch(72% 0.18 295)' },
  { key: 'danger_color', label: 'danger', placeholder: 'oklch(70% 0.2 25)' },
];

export default function Site() {
  const [site, setSite] = useState(null);
  const [siteDraft, setSiteDraft] = useState(null);
  const [theme, setTheme] = useState(null);
  const [themeDraft, setThemeDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [savingSite, setSavingSite] = useState(false);
  const [savingTheme, setSavingTheme] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([apiSite.getSite(), apiSite.getTheme()])
      .then(([s, t]) => {
        if (!mounted) return;
        setSite(s);
        setSiteDraft({ ...s });
        setTheme(t);
        setThemeDraft({ ...t });
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

  useEffect(() => {
    if (!toast) return undefined;
    const id = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(id);
  }, [toast]);

  function dirtySite() {
    if (!site || !siteDraft) return false;
    return SITE_FIELDS.some((f) => norm(site[f.key]) !== norm(siteDraft[f.key]));
  }
  function dirtyTheme() {
    if (!theme || !themeDraft) return false;
    return THEME_FIELDS.some((f) => norm(theme[f.key]) !== norm(themeDraft[f.key]));
  }

  function setSiteField(k, v) {
    setSiteDraft((d) => ({ ...d, [k]: v }));
  }
  function setThemeField(k, v) {
    setThemeDraft((d) => ({ ...d, [k]: v }));
  }

  async function saveSite(e) {
    e?.preventDefault?.();
    if (!siteDraft) return;
    setSavingSite(true);
    try {
      // Send only changed fields → matches PUT /site (exclude_unset semantics).
      const patch = {};
      for (const f of SITE_FIELDS) {
        if (norm(site[f.key]) !== norm(siteDraft[f.key])) {
          patch[f.key] = siteDraft[f.key] === '' ? null : siteDraft[f.key];
        }
      }
      const updated = await apiSite.putSite(patch);
      setSite(updated);
      setSiteDraft({ ...updated });
      setToast('site saved');
    } catch (err) {
      setToast(`error: ${err?.detail || err.message}`);
    } finally {
      setSavingSite(false);
    }
  }

  async function saveTheme(e) {
    e?.preventDefault?.();
    if (!themeDraft) return;
    setSavingTheme(true);
    try {
      const patch = {};
      for (const f of THEME_FIELDS) {
        if (norm(theme[f.key]) !== norm(themeDraft[f.key])) {
          patch[f.key] = themeDraft[f.key] === '' ? null : themeDraft[f.key];
        }
      }
      const updated = await apiSite.putTheme(patch);
      setTheme(updated);
      setThemeDraft({ ...updated });
      setToast('theme saved');
    } catch (err) {
      setToast(`error: ${err?.detail || err.message}`);
    } finally {
      setSavingTheme(false);
    }
  }

  if (loading) return <div style={styles.muted}>loading site…</div>;
  if (error) return <div style={styles.error}>error: {error}</div>;

  return (
    <div>
      <header style={styles.header}>
        <h1 style={styles.h1}>Site</h1>
        <p style={styles.lead}>
          Site-level identity, contact channels, and theme tokens. Author bio
          and avatar are managed in <code>Profile</code>.
        </p>
      </header>

      <form onSubmit={saveSite} style={styles.panel}>
        <div style={styles.panelHead}>
          <span style={styles.panelTitle}>identity & metadata</span>
          <span style={styles.panelHint}>PUT /site</span>
        </div>
        <div style={styles.panelBody}>
          {SITE_FIELDS.map((f) => (
            <Field
              key={f.key}
              field={f}
              value={siteDraft?.[f.key] ?? ''}
              onChange={(v) => setSiteField(f.key, v)}
            />
          ))}
        </div>
        <div style={styles.panelFoot}>
          <button
            type="submit"
            style={styles.btnPrimary}
            disabled={savingSite || !dirtySite()}
          >
            {savingSite ? 'saving…' : 'save site'}
          </button>
          <button
            type="button"
            style={styles.btn}
            disabled={savingSite || !dirtySite()}
            onClick={() => setSiteDraft({ ...site })}
          >
            reset
          </button>
        </div>
      </form>

      <form onSubmit={saveTheme} style={styles.panel}>
        <div style={styles.panelHead}>
          <span style={styles.panelTitle}>theme tokens</span>
          <span style={styles.panelHint}>PUT /theme</span>
        </div>
        <div style={styles.panelBody}>
          {THEME_FIELDS.map((f) => (
            <ThemeRow
              key={f.key}
              field={f}
              value={themeDraft?.[f.key] ?? ''}
              onChange={(v) => setThemeField(f.key, v)}
            />
          ))}
        </div>
        <div style={styles.panelFoot}>
          <button
            type="submit"
            style={styles.btnPrimary}
            disabled={savingTheme || !dirtyTheme()}
          >
            {savingTheme ? 'saving…' : 'save theme'}
          </button>
          <button
            type="button"
            style={styles.btn}
            disabled={savingTheme || !dirtyTheme()}
            onClick={() => setThemeDraft({ ...theme })}
          >
            reset
          </button>
        </div>
      </form>

      {toast && <div style={styles.toast}>{toast}</div>}
    </div>
  );
}

function Field({ field, value, onChange }) {
  if (field.kind === 'select') {
    return (
      <label style={styles.label}>
        <span style={styles.labelText}>{field.label}</span>
        <select
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          style={styles.input}
        >
          {field.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label style={styles.label}>
      <span style={styles.labelText}>{field.label}</span>
      <input
        type="text"
        value={value ?? ''}
        placeholder={field.placeholder}
        onChange={(e) => onChange(e.target.value)}
        style={styles.input}
      />
    </label>
  );
}

function ThemeRow({ field, value, onChange }) {
  return (
    <label style={styles.label}>
      <span style={styles.labelText}>{field.label}</span>
      <div style={styles.themeRow}>
        <span
          style={{
            ...styles.swatch,
            background: value || 'transparent',
          }}
          aria-hidden
        />
        <input
          type="text"
          value={value ?? ''}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
          style={{ ...styles.input, flex: 1 }}
        />
      </div>
    </label>
  );
}

function norm(v) {
  if (v == null) return '';
  return String(v);
}

const styles = {
  header: { marginBottom: 18 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  panel: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    marginBottom: 16,
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
  panelBody: {
    padding: 16,
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
    gap: 12,
  },
  panelFoot: {
    padding: '10px 14px',
    borderTop: '1px solid var(--line)',
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  label: { display: 'flex', flexDirection: 'column', gap: 6 },
  labelText: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  input: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '9px 11px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
  },
  themeRow: { display: 'flex', alignItems: 'center', gap: 8 },
  swatch: {
    width: 24,
    height: 24,
    borderRadius: 4,
    border: '1px solid var(--line-2)',
    flexShrink: 0,
  },
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
