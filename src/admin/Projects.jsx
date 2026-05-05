import { useEffect, useState } from 'react';
import { apiProjects } from '../api/projects.js';
import { useConfirm, useToast } from './ui/UIProvider.jsx';

// Admin screen for the /projects portfolio list.
// Backend ProjectIn fields: name, description, lang, stars, status, sort_order, visible.
// Reorder endpoint payload key is `ids` but contains project names (string keys).
export default function Projects() {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [draft, setDraft] = useState(emptyDraft());
  const [creating, setCreating] = useState(false);

  const [edits, setEdits] = useState({}); // { [name]: partial }
  const [savingName, setSavingName] = useState(null);
  const confirm = useConfirm();
  const toast = useToast();

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiProjects.list();
      setRows(data);
      setEdits({});
    } catch (err) {
      setError(err?.detail || err?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function bufferEdit(name, key, value) {
    setEdits((prev) => ({
      ...prev,
      [name]: { ...(prev[name] || {}), [key]: value },
    }));
  }

  function isRowDirty(row) {
    const e = edits[row.name];
    if (!e) return false;
    return Object.keys(e).some((k) => e[k] !== row[k]);
  }

  async function saveRow(row) {
    const e = edits[row.name];
    if (!e) return;
    setSavingName(row.name);
    try {
      const updated = await apiProjects.patch(row.name, e);
      setRows((prev) => prev.map((r) => (r.name === row.name ? updated : r)));
      setEdits((prev) => {
        const next = { ...prev };
        delete next[row.name];
        return next;
      });
    } catch (err) {
      toast.error(`保存失败：${err?.detail || err.message}`);
    } finally {
      setSavingName(null);
    }
  }

  async function toggleVisible(row) {
    setSavingName(row.name);
    try {
      const updated = await apiProjects.patch(row.name, {
        visible: !row.visible,
      });
      setRows((prev) => prev.map((r) => (r.name === row.name ? updated : r)));
    } catch (err) {
      toast.error(`切换失败：${err?.detail || err.message}`);
    } finally {
      setSavingName(null);
    }
  }

  async function deleteRow(row) {
    const ok = await confirm({
      title: '删除项目',
      message: `确定删除项目 ${row.name} 吗？`,
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    setSavingName(row.name);
    try {
      await apiProjects.remove(row.name);
      setRows((prev) => prev.filter((r) => r.name !== row.name));
      toast.success('已删除');
    } catch (err) {
      toast.error(`删除失败：${err?.detail || err.message}`);
    } finally {
      setSavingName(null);
    }
  }

  async function moveRow(idx, delta) {
    if (!rows) return;
    const target = idx + delta;
    if (target < 0 || target >= rows.length) return;
    const next = rows.slice();
    const [item] = next.splice(idx, 1);
    next.splice(target, 0, item);
    setRows(next);
    try {
      await apiProjects.reorder(next.map((r) => r.name));
      load();
    } catch (err) {
      toast.error(`排序失败：${err?.detail || err.message}`);
      load();
    }
  }

  async function submitDraft(e) {
    e.preventDefault();
    if (!draft.name.trim()) return;
    setCreating(true);
    try {
      const sortOrder = rows ? rows.length : 0;
      await apiProjects.create({
        name: draft.name.trim(),
        description: draft.description.trim(),
        lang: draft.lang.trim(),
        stars: Number(draft.stars) || 0,
        status: draft.status.trim() || 'active',
        sort_order: sortOrder,
        visible: draft.visible,
      });
      setDraft(emptyDraft());
      load();
      toast.success('项目已创建');
    } catch (err) {
      toast.error(`创建失败：${err?.detail || err.message}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <header style={styles.header}>
        <h1 style={styles.h1}>Projects</h1>
        <p style={styles.lead}>
          Portfolio entries shown on the projects page.
        </p>
      </header>

      <form style={styles.newRow} onSubmit={submitDraft}>
        <div style={styles.newRowTitle}>+ new project</div>
        <div style={styles.formGrid}>
          <input
            style={styles.input}
            placeholder="name (slug-ish, unique)"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            required
          />
          <input
            style={styles.input}
            placeholder="lang"
            value={draft.lang}
            onChange={(e) => setDraft({ ...draft, lang: e.target.value })}
          />
          <input
            style={styles.input}
            type="number"
            placeholder="stars"
            value={draft.stars}
            onChange={(e) => setDraft({ ...draft, stars: e.target.value })}
          />
          <input
            style={styles.input}
            placeholder="status (active, archived…)"
            value={draft.status}
            onChange={(e) => setDraft({ ...draft, status: e.target.value })}
          />
          <label style={styles.toggleWrap}>
            <Toggle
              on={draft.visible}
              onChange={(v) => setDraft({ ...draft, visible: v })}
            />
            <span style={styles.toggleLabel}>visible</span>
          </label>
          <button type="submit" style={styles.primaryBtn} disabled={creating}>
            {creating ? 'adding…' : 'add'}
          </button>
        </div>
        <textarea
          style={{ ...styles.input, marginTop: 8, minHeight: 56, resize: 'vertical' }}
          placeholder="description"
          value={draft.description}
          onChange={(e) => setDraft({ ...draft, description: e.target.value })}
        />
      </form>

      {loading && <div style={styles.muted}>loading projects…</div>}
      {error && <div style={styles.error}>error: {error}</div>}

      {!loading && !error && rows && rows.length === 0 && (
        <div style={styles.empty}>no projects yet — add one above</div>
      )}

      {!loading && !error && rows && rows.length > 0 && (
        <div style={styles.tableWrap}>
          <div style={{ ...styles.row, ...styles.headRow }}>
            <div style={styles.cellOrder}>#</div>
            <div style={styles.cellName}>name</div>
            <div style={styles.cellLang}>lang</div>
            <div style={styles.cellStars}>★</div>
            <div style={styles.cellStatus}>status</div>
            <div style={styles.cellVisible}>visible</div>
            <div style={styles.cellActions}>actions</div>
          </div>
          {rows.map((row, idx) => {
            const merged = { ...row, ...(edits[row.name] || {}) };
            const dirty = isRowDirty(row);
            const busy = savingName === row.name;
            return (
              <div key={row.name} style={styles.rowGroup}>
                <div style={styles.row}>
                  <div style={styles.cellOrder}>
                    <button
                      type="button"
                      style={styles.arrowBtn}
                      onClick={() => moveRow(idx, -1)}
                      disabled={idx === 0 || busy}
                      title="move up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      style={styles.arrowBtn}
                      onClick={() => moveRow(idx, 1)}
                      disabled={idx === rows.length - 1 || busy}
                      title="move down"
                    >
                      ↓
                    </button>
                  </div>
                  <div style={styles.cellName}>
                    <span style={styles.nameText}>{row.name}</span>
                  </div>
                  <div style={styles.cellLang}>
                    <input
                      style={styles.cellInput}
                      value={merged.lang}
                      onChange={(e) =>
                        bufferEdit(row.name, 'lang', e.target.value)
                      }
                    />
                  </div>
                  <div style={styles.cellStars}>
                    <input
                      type="number"
                      style={styles.cellInput}
                      value={merged.stars}
                      onChange={(e) =>
                        bufferEdit(
                          row.name,
                          'stars',
                          Number(e.target.value) || 0,
                        )
                      }
                    />
                  </div>
                  <div style={styles.cellStatus}>
                    <input
                      style={styles.cellInput}
                      value={merged.status}
                      onChange={(e) =>
                        bufferEdit(row.name, 'status', e.target.value)
                      }
                    />
                  </div>
                  <div style={styles.cellVisible}>
                    <Toggle
                      on={row.visible}
                      onChange={() => toggleVisible(row)}
                      disabled={busy}
                    />
                  </div>
                  <div style={styles.cellActions}>
                    <button
                      type="button"
                      style={
                        dirty ? styles.primaryBtnSmall : styles.btnSmallDisabled
                      }
                      onClick={() => saveRow(row)}
                      disabled={!dirty || busy}
                    >
                      {busy ? '…' : 'save'}
                    </button>
                    <button
                      type="button"
                      style={styles.dangerBtnSmall}
                      onClick={() => deleteRow(row)}
                      disabled={busy}
                    >
                      del
                    </button>
                  </div>
                </div>
                <div style={styles.descRow}>
                  <textarea
                    style={styles.descArea}
                    placeholder="description"
                    value={merged.description ?? ''}
                    onChange={(e) =>
                      bufferEdit(row.name, 'description', e.target.value)
                    }
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function emptyDraft() {
  return {
    name: '',
    description: '',
    lang: '',
    stars: 0,
    status: 'active',
    visible: true,
  };
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
  empty: {
    border: '1px dashed var(--line-2)',
    padding: '20px',
    borderRadius: 6,
    color: 'var(--fg-3)',
    textAlign: 'center',
    fontSize: 12,
  },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
  },
  newRow: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '12px 14px',
    marginBottom: 18,
  },
  newRowTitle: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
    marginBottom: 8,
  },
  formGrid: {
    display: 'grid',
    gridTemplateColumns: '1.5fr 1fr 70px 1fr auto auto',
    gap: 8,
    alignItems: 'center',
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
  },
  toggleWrap: { display: 'flex', alignItems: 'center', gap: 6 },
  toggleLabel: { fontSize: 11, color: 'var(--fg-3)' },
  primaryBtn: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '8px 14px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
  },
  primaryBtnSmall: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '4px 10px',
    border: 0,
    borderRadius: 3,
    cursor: 'pointer',
    fontSize: 11,
    fontFamily: 'inherit',
  },
  btnSmallDisabled: {
    background: 'transparent',
    color: 'var(--fg-4)',
    padding: '4px 10px',
    border: '1px solid var(--line-2)',
    borderRadius: 3,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'not-allowed',
  },
  dangerBtnSmall: {
    background: 'transparent',
    color: 'var(--danger)',
    padding: '4px 8px',
    border: '1px solid var(--danger)',
    borderRadius: 3,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  tableWrap: {
    border: '1px solid var(--line)',
    borderRadius: 6,
    overflow: 'hidden',
  },
  rowGroup: { borderTop: '1px solid var(--line)' },
  row: {
    display: 'grid',
    gridTemplateColumns: '50px 1.5fr 1fr 70px 1fr 80px 130px',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    fontSize: 12,
  },
  headRow: {
    background: 'var(--bg-2)',
    color: 'var(--fg-3)',
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  cellOrder: { display: 'flex', flexDirection: 'column', gap: 2 },
  cellName: {},
  cellLang: {},
  cellStars: {},
  cellStatus: {},
  cellVisible: {},
  cellActions: { display: 'flex', gap: 6 },
  nameText: { color: 'var(--fg)', fontWeight: 500 },
  cellInput: {
    width: '100%',
    background: 'transparent',
    border: '1px solid transparent',
    color: 'var(--fg)',
    padding: '4px 6px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 3,
    outline: 'none',
  },
  arrowBtn: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    fontFamily: 'inherit',
    fontSize: 10,
    padding: '1px 6px',
    borderRadius: 3,
    cursor: 'pointer',
    lineHeight: 1.2,
  },
  descRow: {
    padding: '0 12px 10px 62px',
  },
  descArea: {
    width: '100%',
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '6px 8px',
    fontFamily: 'inherit',
    fontSize: 11,
    borderRadius: 3,
    outline: 'none',
    minHeight: 36,
    resize: 'vertical',
  },
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
