import { useEffect, useState } from 'react';
import { apiContacts } from '../api/contacts.js';
import { useConfirm, useToast } from './ui/UIProvider.jsx';
import SectionHead from './ui/SectionHead.jsx';

// Admin screen for the social-link contacts strip.
// - Lists rows in sort_order
// - Inline editing of label / value / href
// - Visible toggle PATCHes immediately
// - Up/Down arrow buttons reorder via PUT /contacts/order
// - "+ new" form at top
export default function Contacts() {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // local form state for the "new contact" row
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(emptyDraft());

  // dirty editing state keyed by id: { id: { label, value, href } }
  const [edits, setEdits] = useState({});
  const confirm = useConfirm();
  const toast = useToast();
  const [savingId, setSavingId] = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiContacts.list();
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

  function bufferEdit(id, key, value) {
    setEdits((prev) => ({
      ...prev,
      [id]: { ...(prev[id] || {}), [key]: value },
    }));
  }

  function isRowDirty(row) {
    const e = edits[row.id];
    if (!e) return false;
    return ['label', 'value', 'href'].some(
      (k) => k in e && e[k] !== row[k],
    );
  }

  async function saveRow(row) {
    const e = edits[row.id];
    if (!e) return;
    setSavingId(row.id);
    try {
      const updated = await apiContacts.patch(row.id, e);
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)));
      setEdits((prev) => {
        const next = { ...prev };
        delete next[row.id];
        return next;
      });
    } catch (err) {
      toast.error(`保存失败：${err?.detail || err.message}`);
    } finally {
      setSavingId(null);
    }
  }

  async function toggleVisible(row) {
    setSavingId(row.id);
    try {
      const updated = await apiContacts.patch(row.id, {
        visible: !row.visible,
      });
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)));
    } catch (err) {
      toast.error(`切换失败：${err?.detail || err.message}`);
    } finally {
      setSavingId(null);
    }
  }

  async function deleteRow(row) {
    const ok = await confirm({
      title: '删除联系方式',
      message: `确定删除 ${row.label} 吗？`,
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    setSavingId(row.id);
    try {
      await apiContacts.remove(row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      toast.success('已删除');
    } catch (err) {
      toast.error(`删除失败：${err?.detail || err.message}`);
    } finally {
      setSavingId(null);
    }
  }

  async function moveRow(idx, delta) {
    if (!rows) return;
    const target = idx + delta;
    if (target < 0 || target >= rows.length) return;
    const next = rows.slice();
    const [item] = next.splice(idx, 1);
    next.splice(target, 0, item);
    // optimistic
    setRows(next);
    try {
      await apiContacts.reorder(next.map((r) => r.id));
      // refresh sort_order values from backend
      load();
    } catch (err) {
      toast.error(`排序失败：${err?.detail || err.message}`);
      load();
    }
  }

  async function submitDraft(e) {
    e.preventDefault();
    if (!draft.label.trim() || !draft.value.trim()) return;
    setCreating(true);
    try {
      const sortOrder = rows ? rows.length : 0;
      await apiContacts.create({
        label: draft.label.trim(),
        value: draft.value.trim(),
        href: draft.href.trim(),
        visible: draft.visible,
        sort_order: sortOrder,
      });
      setDraft(emptyDraft());
      load();
      toast.success('已新建联系方式');
    } catch (err) {
      toast.error(`新建失败：${err?.detail || err.message}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <header style={styles.header}>
        <SectionHead
          n="04"
          title="./contacts"
          count={rows ? `${rows.length} 项` : ''}
          lead="联系方式条 — 公开站点 hero / footer 用同一份数据；拖拽或方向键调整顺序。"
        />
      </header>

      <form style={styles.newRow} onSubmit={submitDraft}>
        <div style={styles.newRowTitle}>+ 新建联系方式</div>
        <div style={styles.formGrid}>
          <input
            style={styles.input}
            placeholder="标签（例：github）"
            value={draft.label}
            onChange={(e) => setDraft({ ...draft, label: e.target.value })}
            required
          />
          <input
            style={styles.input}
            placeholder="展示文本"
            value={draft.value}
            onChange={(e) => setDraft({ ...draft, value: e.target.value })}
            required
          />
          <input
            style={styles.input}
            placeholder="链接（https://…）"
            value={draft.href}
            onChange={(e) => setDraft({ ...draft, href: e.target.value })}
          />
          <label style={styles.toggleWrap}>
            <Toggle
              on={draft.visible}
              onChange={(v) => setDraft({ ...draft, visible: v })}
            />
            <span style={styles.toggleLabel}>对公开站点可见</span>
          </label>
          <button type="submit" style={styles.primaryBtn} disabled={creating}>
            {creating ? '添加中…' : '添加'}
          </button>
        </div>
      </form>

      {loading && <div style={styles.muted}>加载中…</div>}
      {error && <div style={styles.error}>! {error}</div>}

      {!loading && !error && rows && rows.length === 0 && (
        <div style={styles.empty} data-testid="contacts-empty">
          暂无联系方式 — 在上方表单添加一条。
        </div>
      )}

      {!loading && !error && rows && rows.length > 0 && (
        <div style={styles.tableWrap}>
          <div style={{ ...styles.row, ...styles.headRow }}>
            <div style={styles.cellOrder}>#</div>
            <div style={styles.cellLabel}>标签</div>
            <div style={styles.cellValue}>展示文本</div>
            <div style={styles.cellHref}>链接</div>
            <div style={styles.cellVisible}>可见</div>
            <div style={styles.cellActions}>操作</div>
          </div>
          {rows.map((row, idx) => {
            const merged = { ...row, ...(edits[row.id] || {}) };
            const dirty = isRowDirty(row);
            const busy = savingId === row.id;
            return (
              <div key={row.id} style={styles.row}>
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
                <div style={styles.cellLabel}>
                  <input
                    style={styles.cellInput}
                    value={merged.label}
                    onChange={(e) =>
                      bufferEdit(row.id, 'label', e.target.value)
                    }
                  />
                </div>
                <div style={styles.cellValue}>
                  <input
                    style={styles.cellInput}
                    value={merged.value}
                    onChange={(e) =>
                      bufferEdit(row.id, 'value', e.target.value)
                    }
                  />
                </div>
                <div style={styles.cellHref}>
                  <input
                    style={styles.cellInput}
                    value={merged.href}
                    onChange={(e) =>
                      bufferEdit(row.id, 'href', e.target.value)
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
            );
          })}
        </div>
      )}
    </div>
  );
}

function emptyDraft() {
  return { label: '', value: '', href: '', visible: true };
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
    gridTemplateColumns: '1fr 1.5fr 2fr auto auto',
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
  row: {
    display: 'grid',
    gridTemplateColumns: '50px 1fr 1.5fr 2fr 80px 130px',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    borderTop: '1px solid var(--line)',
    fontSize: 12,
  },
  headRow: {
    background: 'var(--bg-2)',
    color: 'var(--fg-3)',
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    borderTop: 0,
  },
  cellOrder: { display: 'flex', flexDirection: 'column', gap: 2 },
  cellLabel: {},
  cellValue: {},
  cellHref: {},
  cellVisible: {},
  cellActions: { display: 'flex', gap: 6 },
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
