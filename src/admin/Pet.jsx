import { useEffect, useState } from 'react';
import { apiPet } from '../api/pet.js';

// Single-config form for the desktop pet (PetConfig, verified against
// backend/app/schemas/pet.py). Fields:
//   - model (str, ≤64)
//   - system_prompt (str, ≤2000)
//   - fallback_lines (list[str], ≥1) — edited as one-per-line textarea
//   - rate_limit_per_min (int, 1..60)
//   - enabled (bool)
//   - species ("cat" | "dog" | "rabbit" | "fox")
//   - hat (str, ≤32)
//   - tint (str, ≤16)  — typically "#rrggbb"
//   - visitor_can_change (bool)
const SPECIES = ['cat', 'dog', 'rabbit', 'fox'];

export default function Pet() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savedTick, setSavedTick] = useState(0);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiPet
      .get()
      .then((res) => {
        if (!mounted) return;
        setConfig(res);
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

  function patch(partial) {
    setConfig((prev) => ({ ...prev, ...partial }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!config) return;

    // light validation matching the backend constraints
    const lines = (config.fallback_lines || []).filter((l) => l.trim() !== '');
    if (lines.length === 0) {
      alert('fallback_lines must contain at least one non-empty line');
      return;
    }
    const rate = Number(config.rate_limit_per_min);
    if (!Number.isInteger(rate) || rate < 1 || rate > 60) {
      alert('rate_limit_per_min must be an integer between 1 and 60');
      return;
    }

    const payload = {
      model: config.model,
      system_prompt: config.system_prompt,
      fallback_lines: lines,
      rate_limit_per_min: rate,
      enabled: !!config.enabled,
      species: config.species,
      hat: config.hat,
      tint: config.tint,
      visitor_can_change: !!config.visitor_can_change,
    };

    setSaving(true);
    try {
      const updated = await apiPet.put(payload);
      setConfig(updated);
      setSavedTick(Date.now());
    } catch (err) {
      alert(`save failed: ${err?.detail || err.message}`);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={styles.muted}>loading pet config…</div>;
  if (error) return <div style={styles.error}>error: {error}</div>;
  if (!config) return <div style={styles.muted}>no config</div>;

  const fallbackText = (config.fallback_lines || []).join('\n');

  return (
    <div>
      <header style={styles.header}>
        <h1 style={styles.h1}>Pet</h1>
        <p style={styles.lead}>
          Desktop-pet companion: appearance + LLM behavior.
        </p>
      </header>

      <form style={styles.form} onSubmit={onSubmit}>
        <Section title="appearance">
          <Field label="species">
            <select
              style={styles.input}
              value={config.species}
              onChange={(e) => patch({ species: e.target.value })}
            >
              {SPECIES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="hat">
            <input
              style={styles.input}
              value={config.hat || ''}
              onChange={(e) => patch({ hat: e.target.value })}
              maxLength={32}
              placeholder="none"
            />
          </Field>
          <Field label="tint">
            <div style={styles.tintRow}>
              <input
                type="color"
                style={styles.colorInput}
                value={
                  isHexColor(config.tint) ? config.tint : '#7aa7ff'
                }
                onChange={(e) => patch({ tint: e.target.value })}
              />
              <input
                style={{ ...styles.input, flex: 1 }}
                value={config.tint || ''}
                onChange={(e) => patch({ tint: e.target.value })}
                maxLength={16}
                placeholder="#7aa7ff"
              />
            </div>
          </Field>
        </Section>

        <Section title="behavior">
          <Field label="enabled">
            <Toggle
              on={!!config.enabled}
              onChange={(v) => patch({ enabled: v })}
            />
          </Field>
          <Field label="visitor can change">
            <Toggle
              on={!!config.visitor_can_change}
              onChange={(v) => patch({ visitor_can_change: v })}
            />
          </Field>
          <Field label="rate limit / min">
            <input
              type="number"
              min={1}
              max={60}
              style={styles.input}
              value={config.rate_limit_per_min}
              onChange={(e) =>
                patch({ rate_limit_per_min: Number(e.target.value) || 0 })
              }
            />
          </Field>
        </Section>

        <Section title="llm">
          <Field label="model" wide>
            <input
              style={styles.input}
              value={config.model || ''}
              onChange={(e) => patch({ model: e.target.value })}
              maxLength={64}
            />
          </Field>
          <Field label="system prompt" wide>
            <textarea
              style={{ ...styles.input, minHeight: 90, resize: 'vertical' }}
              value={config.system_prompt || ''}
              onChange={(e) => patch({ system_prompt: e.target.value })}
              maxLength={2000}
            />
          </Field>
          <Field label="fallback lines (one per line)" wide>
            <textarea
              style={{ ...styles.input, minHeight: 90, resize: 'vertical' }}
              value={fallbackText}
              onChange={(e) =>
                patch({ fallback_lines: e.target.value.split('\n') })
              }
            />
          </Field>
        </Section>

        <div style={styles.footer}>
          <button type="submit" style={styles.primaryBtn} disabled={saving}>
            {saving ? 'saving…' : 'save'}
          </button>
          {savedTick > 0 && !saving && (
            <span style={styles.savedHint}>
              saved {new Date(savedTick).toLocaleTimeString()}
            </span>
          )}
        </div>
      </form>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <fieldset style={styles.section}>
      <legend style={styles.legend}>{title}</legend>
      <div style={styles.fields}>{children}</div>
    </fieldset>
  );
}

function Field({ label, wide, children }) {
  return (
    <label style={{ ...styles.field, ...(wide ? styles.fieldWide : null) }}>
      <span style={styles.fieldLabel}>{label}</span>
      {children}
    </label>
  );
}

function isHexColor(s) {
  return typeof s === 'string' && /^#[0-9a-fA-F]{6}$/.test(s);
}

function Toggle({ on, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => !disabled && onChange(!on)}
      disabled={disabled}
      style={{
        ...styles.switch,
        ...(on ? styles.switchOn : styles.switchOff),
        ...(disabled ? { opacity: 0.5, cursor: 'not-allowed' } : null),
      }}
    >
      <span
        style={{
          ...styles.switchKnob,
          ...(on ? styles.switchKnobOn : null),
        }}
      />
    </button>
  );
}

const styles = {
  header: { marginBottom: 18 },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  muted: { color: 'var(--fg-3)', fontSize: 12 },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
  },
  form: { display: 'flex', flexDirection: 'column', gap: 18, maxWidth: 720 },
  section: {
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '12px 16px 16px',
    background: 'var(--bg-2)',
    margin: 0,
  },
  legend: {
    fontSize: 10,
    color: 'var(--fg-3)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    padding: '0 6px',
  },
  fields: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: 14,
  },
  field: { display: 'flex', flexDirection: 'column', gap: 6 },
  fieldWide: { gridColumn: '1 / -1' },
  fieldLabel: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  input: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '8px 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  },
  tintRow: { display: 'flex', alignItems: 'center', gap: 8 },
  colorInput: {
    width: 36,
    height: 30,
    background: 'transparent',
    border: '1px solid var(--line-2)',
    borderRadius: 4,
    padding: 2,
    cursor: 'pointer',
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  primaryBtn: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '10px 18px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 13,
    fontFamily: 'inherit',
    letterSpacing: '0.04em',
  },
  savedHint: { fontSize: 11, color: 'var(--fg-3)' },
  switch: {
    width: 32,
    height: 18,
    border: '1px solid var(--line-2)',
    borderRadius: 999,
    padding: 1,
    cursor: 'pointer',
    transition: 'background 0.15s ease',
    display: 'inline-flex',
    alignItems: 'center',
  },
  switchOff: { background: 'var(--bg)' },
  switchOn: {
    background: 'color-mix(in oklab, var(--accent) 50%, transparent)',
    borderColor: 'var(--accent)',
  },
  switchKnob: {
    width: 12,
    height: 12,
    background: 'var(--fg-3)',
    borderRadius: 999,
    transition: 'transform 0.15s ease, background 0.15s ease',
  },
  switchKnobOn: {
    transform: 'translateX(14px)',
    background: 'var(--accent)',
  },
};
