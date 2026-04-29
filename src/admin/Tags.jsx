import { useCallback, useEffect, useState } from 'react';
import { tagsApi } from '../api/tags.js';

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,31}$/;
const DEFAULT_NEW = { slug: '', name: '', color: '#7dd3a4', sort_order: 0 };

export default function Tags() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingDraft, setEditingDraft] = useState(null);
  const [newDraft, setNewDraft] = useState(null); // null when not creating
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    let mounted = true;
    setLoading(true);
    tagsApi
      .list()
      .then((rows) => {
        if (!mounted) return;
        setItems(rows || []);
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
    const cleanup = load();
    return cleanup;
  }, [load]);

  function startEdit(t) {
    setEditingId(t.id);
    setEditingDraft({ slug: t.slug, name: t.name, color: t.color, sort_order: t.sort_order });
  }

  function cancelEdit() {
    setEditingId(null);
    setEditingDraft(null);
  }

  async function saveEdit() {
    if (!editingDraft) return;
    if (!SLUG_RE.test(editingDraft.slug)) {
      // eslint-disable-next-line no-alert
      alert('slug must match ^[a-z0-9][a-z0-9-]{1,31}$');
      return;
    }
    setBusy(true);
    try {
      await tagsApi.patch(editingId, editingDraft);
      setEditingId(null);
      setEditingDraft(null);
      load();
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(`save failed: ${err?.detail || err?.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(t) {
    // eslint-disable-next-line no-alert
    if (!confirm(`Delete tag "${t.slug}"?`)) return;
    setBusy(true);
    try {
      await tagsApi.remove(t.id);
      load();
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(`delete failed: ${err?.detail || err?.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function createNew() {
    if (!newDraft) return;
    if (!SLUG_RE.test(newDraft.slug)) {
      // eslint-disable-next-line no-alert
      alert('slug must match ^[a-z0-9][a-z0-9-]{1,31}$');
      return;
    }
    setBusy(true);
    try {
      await tagsApi.create(newDraft);
      setNewDraft(null);
      load();
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(`create failed: ${err?.detail || err?.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function move(idx, dir) {
    const ni = idx + dir;
    if (ni < 0 || ni >= items.length) return;
    const next = items.slice();
    [next[idx], next[ni]] = [next[ni], next[idx]];
    setItems(next); // optimistic
    try {
      await tagsApi.reorder(next.map((t) => t.id));
    } catch (err) {
      // eslint-disable-next-line no-alert
      alert(`reorder failed: ${err?.detail || err?.message}`);
      load();
    }
  }

  return (
    <div>
      <header style={styles.header}>
        <div>
          <h1 style={styles.h1}>Tags</h1>
          <p style={styles.lead}>
            {loading ? 'loading…' : `${items.length} tag${items.length === 1 ? '' : 's'}`}
          </p>
        </div>
        {!newDraft && (
          <button
            type="button"
            style={styles.btnPrimary}
            onClick={() => setNewDraft({ ...DEFAULT_NEW })}
          >
            + new tag
          </button>
        )}
      </header>

      {error && <div style={styles.error}>! {error}</div>}

      {newDraft && (
        <div style={styles.newRow}>
          <div style={styles.colHead}>new tag</div>
          <div style={styles.fieldGrid}>
            <Field label="slug">
              <input
                style={styles.input}
                value={newDraft.slug}
                onChange={(e) => setNewDraft({ ...newDraft, slug: e.target.value })}
                placeholder="my-tag"
              />
            </Field>
            <Field label="name">
              <input
                style={styles.input}
                value={newDraft.name}
                onChange={(e) => setNewDraft({ ...newDraft, name: e.target.value })}
                placeholder="Display name"
              />
            </Field>
            <Field label="color">
              <input
                type="color"
                style={styles.colorInput}
                value={newDraft.color}
                onChange={(e) => setNewDraft({ ...newDraft, color: e.target.value })}
              />
            </Field>
            <Field label="sort_order">
              <input
                type="number"
                style={styles.input}
                value={newDraft.sort_order}
                onChange={(e) =>
                  setNewDraft({ ...newDraft, sort_order: Number(e.target.value) || 0 })
                }
              />
            </Field>
          </div>
          <div style={styles.rowBtns}>
            <button
              type="button"
              style={styles.btnGhost}
              onClick={() => setNewDraft(null)}
              disabled={busy}
            >
              cancel
            </button>
            <button
              type="button"
              style={styles.btnPrimary}
              onClick={createNew}
              disabled={busy}
            >
              {busy ? 'creating…' : 'create →'}
            </button>
          </div>
        </div>
      )}

      <div style={styles.tableWrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={{ ...styles.th, width: 70 }}>order</th>
              <th style={styles.th}>slug</th>
              <th style={styles.th}>name</th>
              <th style={styles.th}>color</th>
              <th style={{ ...styles.th, width: 80 }}>sort</th>
              <th style={{ ...styles.th, textAlign: 'right' }}>actions</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading && (
              <tr>
                <td colSpan={6} style={styles.empty}>
                  no tags yet
                </td>
              </tr>
            )}
            {items.map((t, idx) => {
              const isEditing = editingId === t.id;
              return (
                <tr key={t.id} style={styles.tr}>
                  <td style={styles.td}>
                    <button
                      type="button"
                      style={styles.arrow}
                      onClick={() => move(idx, -1)}
                      disabled={idx === 0 || busy}
                      title="move up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      style={styles.arrow}
                      onClick={() => move(idx, +1)}
                      disabled={idx === items.length - 1 || busy}
                      title="move down"
                    >
                      ↓
                    </button>
                  </td>
                  <td style={styles.td}>
                    {isEditing ? (
                      <input
                        style={styles.input}
                        value={editingDraft.slug}
                        onChange={(e) =>
                          setEditingDraft({ ...editingDraft, slug: e.target.value })
                        }
                      />
                    ) : (
                      <code style={styles.slug}>{t.slug}</code>
                    )}
                  </td>
                  <td style={styles.td}>
                    {isEditing ? (
                      <input
                        style={styles.input}
                        value={editingDraft.name}
                        onChange={(e) =>
                          setEditingDraft({ ...editingDraft, name: e.target.value })
                        }
                      />
                    ) : (
                      t.name
                    )}
                  </td>
                  <td style={styles.td}>
                    {isEditing ? (
                      <input
                        type="color"
                        style={styles.colorInput}
                        value={editingDraft.color}
                        onChange={(e) =>
                          setEditingDraft({ ...editingDraft, color: e.target.value })
                        }
                      />
                    ) : (
                      <span style={styles.swatchRow}>
                        <span
                          style={{ ...styles.swatch, background: t.color }}
                        />
                        <code style={styles.colorCode}>{t.color}</code>
                      </span>
                    )}
                  </td>
                  <td style={styles.td}>
                    {isEditing ? (
                      <input
                        type="number"
                        style={styles.input}
                        value={editingDraft.sort_order}
                        onChange={(e) =>
                          setEditingDraft({
                            ...editingDraft,
                            sort_order: Number(e.target.value) || 0,
                          })
                        }
                      />
                    ) : (
                      <span style={styles.dim}>{t.sort_order}</span>
                    )}
                  </td>
                  <td style={{ ...styles.td, textAlign: 'right' }}>
                    {isEditing ? (
                      <>
                        <button
                          type="button"
                          style={styles.btnGhost}
                          onClick={cancelEdit}
                          disabled={busy}
                        >
                          cancel
                        </button>
                        <button
                          type="button"
                          style={styles.btnPrimaryS}
                          onClick={saveEdit}
                          disabled={busy}
                        >
                          save
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          style={styles.btnGhost}
                          onClick={() => startEdit(t)}
                          disabled={busy}
                        >
                          edit
                        </button>
                        <button
                          type="button"
                          style={styles.btnDanger}
                          onClick={() => onDelete(t)}
                          disabled={busy}
                        >
                          delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label style={styles.field}>
      <span style={styles.fieldLabel}>{label}</span>
      {children}
    </label>
  );
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 18,
  },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  btnPrimary: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '8px 14px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
    letterSpacing: '0.04em',
  },
  btnPrimaryS: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '4px 10px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 11,
    fontFamily: 'inherit',
    marginLeft: 6,
  },
  btnGhost: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
    marginRight: 6,
  },
  btnDanger: {
    background: 'transparent',
    border: '1px solid color-mix(in oklab, var(--danger) 60%, transparent)',
    color: 'var(--danger)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  newRow: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '12px 14px',
    marginBottom: 14,
  },
  colHead: {
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 8,
  },
  fieldGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: 10,
  },
  field: { display: 'flex', flexDirection: 'column', gap: 4 },
  fieldLabel: {
    fontSize: 10,
    color: 'var(--fg-4)',
    letterSpacing: '0.06em',
    textTransform: 'lowercase',
  },
  input: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '6px 8px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box',
  },
  colorInput: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    height: 28,
    width: '100%',
    padding: 2,
    borderRadius: 4,
  },
  rowBtns: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginTop: 10,
    gap: 8,
  },
  tableWrap: {
    border: '1px solid var(--line)',
    borderRadius: 6,
    overflow: 'hidden',
    background: 'var(--bg-2)',
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    borderBottom: '1px solid var(--line)',
    fontWeight: 500,
  },
  tr: { borderBottom: '1px solid var(--line)' },
  td: { padding: '8px 12px', color: 'var(--fg-2)', verticalAlign: 'middle' },
  arrow: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '2px 6px',
    borderRadius: 3,
    fontSize: 10,
    fontFamily: 'inherit',
    cursor: 'pointer',
    marginRight: 4,
  },
  slug: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    padding: '2px 6px',
    fontSize: 11,
    borderRadius: 3,
    color: 'var(--fg)',
  },
  swatchRow: { display: 'inline-flex', alignItems: 'center', gap: 8 },
  swatch: {
    display: 'inline-block',
    width: 16,
    height: 16,
    borderRadius: 3,
    border: '1px solid var(--line-2)',
  },
  colorCode: { color: 'var(--fg-3)', fontSize: 11 },
  dim: { color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums' },
  empty: {
    padding: '40px 12px',
    textAlign: 'center',
    color: 'var(--fg-4)',
    fontSize: 12,
  },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
    marginBottom: 14,
  },
};
