import { useEffect, useState } from 'react';
import { apiNow } from '../api/now.js';
import { useConfirm, useToast } from './ui/UIProvider.jsx';
import SectionHead from './ui/SectionHead.jsx';
import { renderNowMarkdown } from './nowMarkdown.js';

// Admin timeline of "now" entries.
// Single is_current at any time — backend auto-flips others off when one
// is set true (verified in backend/app/services/now.py), so toggling here
// just refreshes from server.
export default function Now() {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const confirm = useConfirm();
  const toast = useToast();
  // per-row preview open/closed flag. Rendering is local + sync via
  // renderNowMarkdown — no API roundtrip needed for short entries.
  const [previewOpen, setPreviewOpen] = useState({});
  function togglePreview(id) {
    setPreviewOpen((p) => ({ ...p, [id]: !p[id] }));
  }

  const [draft, setDraft] = useState(emptyDraft());
  const [creating, setCreating] = useState(false);

  // active edits per id
  const [edits, setEdits] = useState({});
  const [busyId, setBusyId] = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiNow.list();
      // newest first by created_at, falling back to id
      const sorted = data.slice().sort((a, b) => {
        const ad = new Date(a.created_at).getTime();
        const bd = new Date(b.created_at).getTime();
        if (bd !== ad) return bd - ad;
        return b.id - a.id;
      });
      setRows(sorted);
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

  function isDirty(row) {
    const e = edits[row.id];
    if (!e) return false;
    return Object.keys(e).some((k) => (e[k] ?? '') !== (row[k] ?? ''));
  }

  async function saveRow(row) {
    const e = edits[row.id];
    if (!e) return;
    // body_md cannot be empty on save
    if ('body_md' in e && !e.body_md.trim()) {
      toast.error('内容不能为空');
      return;
    }
    setBusyId(row.id);
    try {
      const updated = await apiNow.patch(row.id, e);
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)));
      setEdits((prev) => {
        const next = { ...prev };
        delete next[row.id];
        return next;
      });
      toast.success('已保存');
    } catch (err) {
      toast.error(`保存失败：${err?.detail || err.message}`);
    } finally {
      setBusyId(null);
    }
  }

  async function toggleCurrent(row) {
    setBusyId(row.id);
    try {
      await apiNow.patch(row.id, { is_current: !row.is_current });
      // backend flips others off — reload to stay consistent
      await load();
    } catch (err) {
      toast.error(`切换失败：${err?.detail || err.message}`);
    } finally {
      setBusyId(null);
    }
  }

  async function deleteRow(row) {
    const ok = await confirm({
      title: '删除近况',
      message: '确定删除这条近况吗？',
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    setBusyId(row.id);
    try {
      await apiNow.remove(row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      toast.success('已删除');
    } catch (err) {
      toast.error(`删除失败：${err?.detail || err.message}`);
    } finally {
      setBusyId(null);
    }
  }

  async function submitDraft(e) {
    e.preventDefault();
    if (!draft.body_md.trim()) return;
    setCreating(true);
    try {
      await apiNow.create({
        body_md: draft.body_md.trim(),
        listening: draft.listening.trim() || null,
        reading: draft.reading.trim() || null,
        is_current: draft.is_current,
      });
      setDraft(emptyDraft());
      await load();
      toast.success('近况已发布');
    } catch (err) {
      toast.error(`发布失败：${err?.detail || err.message}`);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <header style={styles.header}>
        <SectionHead
          n="02"
          title="./now"
          count={rows ? `${rows.length} 条` : undefined}
          lead="你当下在做的事 — 当前条目展示在 /now 页"
        />
      </header>

      <form style={styles.composer} onSubmit={submitDraft}>
        <div style={styles.composerTitle}>+ new entry</div>
        <textarea
          style={styles.bodyArea}
          placeholder="body (markdown)…"
          value={draft.body_md}
          onChange={(e) => setDraft({ ...draft, body_md: e.target.value })}
          required
          maxLength={5000}
        />
        <div style={styles.metaGrid}>
          <input
            style={styles.input}
            placeholder="listening (e.g. artist — track)"
            value={draft.listening}
            onChange={(e) => setDraft({ ...draft, listening: e.target.value })}
            maxLength={256}
          />
          <input
            style={styles.input}
            placeholder="reading (e.g. book title)"
            value={draft.reading}
            onChange={(e) => setDraft({ ...draft, reading: e.target.value })}
            maxLength={256}
          />
          <label style={styles.toggleWrap}>
            <Toggle
              on={draft.is_current}
              onChange={(v) => setDraft({ ...draft, is_current: v })}
            />
            <span style={styles.toggleLabel}>set as current</span>
          </label>
          <button type="submit" style={styles.primaryBtn} disabled={creating}>
            {creating ? 'posting…' : 'post'}
          </button>
        </div>
      </form>

      {loading && <div style={styles.muted}>loading entries…</div>}
      {error && <div style={styles.error}>error: {error}</div>}

      {!loading && !error && rows && rows.length === 0 && (
        <div style={styles.empty}>no entries yet — post the first one</div>
      )}

      {!loading && !error && rows && rows.length > 0 && (
        <div style={styles.timeline}>
          {rows.map((row) => {
            const merged = { ...row, ...(edits[row.id] || {}) };
            const dirty = isDirty(row);
            const busy = busyId === row.id;
            return (
              <article
                key={row.id}
                style={{
                  ...styles.card,
                  ...(row.is_current ? styles.cardCurrent : null),
                }}
              >
                <div style={styles.cardHead}>
                  <span style={styles.cardDate}>
                    {formatDate(row.created_at)}
                  </span>
                  {row.is_current && (
                    <span style={styles.currentBadge}>current</span>
                  )}
                  <span style={styles.cardId}>#{row.id}</span>
                  <div style={styles.cardActions}>
                    <label style={styles.toggleWrap}>
                      <Toggle
                        on={row.is_current}
                        onChange={() => toggleCurrent(row)}
                        disabled={busy}
                      />
                      <span style={styles.toggleLabel}>current</span>
                    </label>
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
                      style={
                        previewOpen[row.id]
                          ? styles.primaryBtnSmall
                          : styles.btnSmallDisabled
                      }
                      onClick={() => togglePreview(row.id)}
                      disabled={busy}
                      data-testid={`now-preview-${row.id}`}
                      data-active={previewOpen[row.id] ? 'true' : undefined}
                    >
                      预览
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
                {previewOpen[row.id] ? (
                  <div
                    style={styles.previewBox}
                    data-testid={`now-preview-body-${row.id}`}
                  >
                    <div
                      className="reader-md"
                      dangerouslySetInnerHTML={{
                        __html:
                          renderNowMarkdown(merged.body_md) ||
                          '<p style="color:var(--fg-4)">（空）</p>',
                      }}
                    />
                  </div>
                ) : (
                  <textarea
                    style={styles.bodyEditor}
                    value={merged.body_md}
                    onChange={(e) =>
                      bufferEdit(row.id, 'body_md', e.target.value)
                    }
                    maxLength={5000}
                  />
                )}
                <div style={styles.metaInline}>
                  <label style={styles.metaItem}>
                    <span style={styles.metaLabel}>listening</span>
                    <input
                      style={styles.metaInput}
                      value={merged.listening ?? ''}
                      onChange={(e) =>
                        bufferEdit(row.id, 'listening', e.target.value)
                      }
                      maxLength={256}
                    />
                  </label>
                  <label style={styles.metaItem}>
                    <span style={styles.metaLabel}>reading</span>
                    <input
                      style={styles.metaInput}
                      value={merged.reading ?? ''}
                      onChange={(e) =>
                        bufferEdit(row.id, 'reading', e.target.value)
                      }
                      maxLength={256}
                    />
                  </label>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

function emptyDraft() {
  return { body_md: '', listening: '', reading: '', is_current: false };
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toISOString().slice(0, 16).replace('T', ' ');
  } catch {
    return String(iso);
  }
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
  composer: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '12px 14px',
    marginBottom: 18,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  composerTitle: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  bodyArea: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '8px 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    minHeight: 80,
    resize: 'vertical',
  },
  metaGrid: {
    display: 'grid',
    // auto-fit 让移动端 listening / reading / toggle / post 自然堆叠。
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
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
    minWidth: 0,
    boxSizing: 'border-box',
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
  timeline: { display: 'flex', flexDirection: 'column', gap: 12 },
  card: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '12px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  cardCurrent: {
    border: '1px solid color-mix(in oklab, var(--accent) 50%, transparent)',
    boxShadow:
      '0 0 0 1px color-mix(in oklab, var(--accent) 25%, transparent) inset',
  },
  cardHead: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    fontSize: 11,
  },
  cardDate: {
    color: 'var(--fg-2)',
    fontVariantNumeric: 'tabular-nums',
  },
  cardId: { color: 'var(--fg-4)' },
  currentBadge: {
    fontSize: 9,
    color: '#0a0b0d',
    background: 'var(--accent)',
    padding: '1px 6px',
    borderRadius: 3,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontWeight: 600,
  },
  cardActions: {
    marginLeft: 'auto',
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  previewBox: {
    background: 'var(--bg)',
    border: '1px dashed var(--line-2)',
    padding: '8px 12px',
    fontSize: 13,
    borderRadius: 4,
    minHeight: 60,
    color: 'var(--fg-2)',
    lineHeight: 1.6,
  },
  previewMuted: { color: 'var(--fg-4)', fontSize: 12 },
  previewError: {
    color: 'var(--danger, #c44)',
    fontSize: 12,
    border: '1px solid var(--danger, #c44)',
    padding: '6px 10px',
    borderRadius: 4,
  },
  bodyEditor: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '8px 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    minHeight: 60,
    resize: 'vertical',
    width: '100%',
    boxSizing: 'border-box',
  },
  metaInline: {
    display: 'grid',
    // 桌面 2 列；移动 viewport <440px 时自动塞 1 列。auto-fit 是关键。
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 8,
  },
  metaItem: { display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 },
  metaLabel: {
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  metaInput: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '6px 8px',
    fontFamily: 'inherit',
    fontSize: 11,
    borderRadius: 3,
    outline: 'none',
    minWidth: 0,
    boxSizing: 'border-box',
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
