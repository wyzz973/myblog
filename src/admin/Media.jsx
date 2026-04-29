import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiMedia, mediaUrl } from '../api/media.js';

export default function Media() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadFails, setUploadFails] = useState([]);
  const [toast, setToast] = useState(null);
  const fileRef = useRef(null);
  const dropRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiMedia.list();
      setItems(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(err?.detail || err?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Auto-clear toast.
  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const selected = useMemo(
    () => items.find((m) => m.id === selectedId) || null,
    [items, selectedId],
  );

  async function handleUpload(filesList) {
    const files = Array.from(filesList || []);
    if (files.length === 0) return;
    setUploading(true);
    setUploadFails([]);
    try {
      const res = await apiMedia.upload(files);
      const okCount = (res?.ok || []).length;
      const fails = res?.failed || [];
      setUploadFails(fails);
      setToast(
        `uploaded ${okCount}/${files.length}` +
          (fails.length ? ` · ${fails.length} failed` : ''),
      );
      await refresh();
    } catch (err) {
      setError(err?.detail || err?.message || 'upload failed');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  function onPickFiles() {
    fileRef.current?.click();
  }

  function onFileInput(e) {
    if (e.target.files && e.target.files.length) handleUpload(e.target.files);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer?.files?.length) handleUpload(e.dataTransfer.files);
  }
  function onDragOver(e) {
    e.preventDefault();
    if (!dragActive) setDragActive(true);
  }
  function onDragLeave(e) {
    e.preventDefault();
    if (e.target === dropRef.current) setDragActive(false);
  }

  async function onSaveAlt(id, alt) {
    try {
      const updated = await apiMedia.patch(id, { alt });
      setItems((prev) => prev.map((m) => (m.id === id ? updated : m)));
      setToast('alt saved');
    } catch (err) {
      setToast(`error: ${err?.detail || err.message}`);
    }
  }

  async function onDelete(id) {
    if (!confirm('Delete this media item? This cannot be undone.')) return;
    try {
      await apiMedia.remove(id);
      setItems((prev) => prev.filter((m) => m.id !== id));
      if (selectedId === id) setSelectedId(null);
      setToast('deleted');
    } catch (err) {
      setToast(`error: ${err?.detail || err.message}`);
    }
  }

  function onCopy(item) {
    const url = mediaUrl(item);
    try {
      navigator.clipboard?.writeText(url);
      setToast('link copied');
    } catch {
      setToast('copy failed');
    }
  }

  return (
    <div>
      <header style={styles.header}>
        <div>
          <h1 style={styles.h1}>Media</h1>
          <p style={styles.lead}>
            {items.length} item{items.length === 1 ? '' : 's'} ·
            {' '}upload images and manage alt text.
          </p>
        </div>
        <div style={styles.actions}>
          <button
            type="button"
            style={styles.btnPrimary}
            onClick={onPickFiles}
            disabled={uploading}
          >
            {uploading ? 'uploading…' : '+ upload'}
          </button>
          <input
            ref={fileRef}
            type="file"
            multiple
            style={{ display: 'none' }}
            onChange={onFileInput}
          />
        </div>
      </header>

      <div
        ref={dropRef}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        style={{
          ...styles.drop,
          ...(dragActive ? styles.dropActive : null),
        }}
      >
        {dragActive
          ? 'release to upload'
          : 'drag & drop images here, or click "+ upload"'}
      </div>

      {uploadFails.length > 0 && (
        <div style={styles.failBlock}>
          <div style={styles.failTitle}>upload failures</div>
          {uploadFails.map((f, i) => (
            <div key={i} style={styles.failRow}>
              <span style={styles.failName}>{f.filename}</span>
              <span style={styles.failErr}>{f.error}</span>
            </div>
          ))}
        </div>
      )}

      {loading && <div style={styles.muted}>loading media…</div>}
      {error && <div style={styles.error}>error: {error}</div>}
      {!loading && !error && items.length === 0 && (
        <div style={styles.muted}>no media yet — upload your first image.</div>
      )}

      {items.length > 0 && (
        <div style={styles.grid}>
          {items.map((m) => (
            <Tile
              key={m.id}
              item={m}
              active={m.id === selectedId}
              onClick={() => setSelectedId(m.id)}
            />
          ))}
        </div>
      )}

      {selected && (
        <DetailModal
          item={selected}
          onClose={() => setSelectedId(null)}
          onSaveAlt={onSaveAlt}
          onDelete={onDelete}
          onCopy={onCopy}
        />
      )}

      {toast && <div style={styles.toast}>{toast}</div>}
    </div>
  );
}

function Tile({ item, active, onClick }) {
  const isImage = (item.mime_type || '').startsWith('image/');
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        ...styles.tile,
        ...(active ? styles.tileActive : null),
      }}
    >
      <div style={styles.thumbBox}>
        {isImage ? (
          <img
            src={mediaUrl(item)}
            alt={item.alt || item.filename}
            style={styles.thumb}
            loading="lazy"
          />
        ) : (
          <div style={styles.fileGlyph}>{item.mime_type || 'file'}</div>
        )}
      </div>
      <div style={styles.tileMeta}>
        <div style={styles.tileName} title={item.filename}>
          {item.filename}
        </div>
        <div style={styles.tileSub}>
          {fmtBytes(item.size)}
          {item.width && item.height
            ? ` · ${item.width}×${item.height}`
            : ''}
        </div>
      </div>
    </button>
  );
}

function DetailModal({ item, onClose, onSaveAlt, onDelete, onCopy }) {
  const [alt, setAlt] = useState(item.alt || '');
  const [saving, setSaving] = useState(false);

  // When the item changes (selecting another), reset local alt.
  useEffect(() => {
    setAlt(item.alt || '');
  }, [item.id, item.alt]);

  async function save() {
    setSaving(true);
    try {
      await onSaveAlt(item.id, alt);
    } finally {
      setSaving(false);
    }
  }

  const dirty = (alt || '') !== (item.alt || '');
  const isImage = (item.mime_type || '').startsWith('image/');

  return (
    <div style={styles.modalShell} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHead}>
          <span style={styles.modalTitle}>media #{item.id}</span>
          <button type="button" onClick={onClose} style={styles.iconBtn}>
            close ✕
          </button>
        </div>
        <div style={styles.modalBody}>
          <div style={styles.preview}>
            {isImage ? (
              <img src={mediaUrl(item)} alt={item.alt || ''} style={styles.previewImg} />
            ) : (
              <div style={styles.fileGlyphLg}>{item.mime_type || 'file'}</div>
            )}
          </div>
          <dl style={styles.facts}>
            <Fact k="filename" v={item.filename} />
            <Fact k="mime" v={item.mime_type} />
            <Fact k="size" v={fmtBytes(item.size)} />
            <Fact
              k="dim"
              v={item.width && item.height ? `${item.width}×${item.height}` : '—'}
            />
            <Fact k="created" v={fmtDate(item.created_at)} />
            <Fact k="url" v={item.url} mono />
          </dl>

          <label style={styles.label}>
            <span style={styles.labelText}>alt text</span>
            <textarea
              value={alt}
              onChange={(e) => setAlt(e.target.value)}
              maxLength={512}
              rows={3}
              style={styles.textarea}
              placeholder="Describe the image for accessibility…"
            />
            <span style={styles.counter}>{alt.length}/512</span>
          </label>
        </div>
        <div style={styles.modalFoot}>
          <button type="button" style={styles.btn} onClick={() => onCopy(item)}>
            copy link
          </button>
          <button
            type="button"
            style={styles.btnDanger}
            onClick={() => onDelete(item.id)}
          >
            delete
          </button>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            style={styles.btnPrimary}
            onClick={save}
            disabled={!dirty || saving}
          >
            {saving ? 'saving…' : 'save alt'}
          </button>
        </div>
      </div>
    </div>
  );
}

function Fact({ k, v, mono }) {
  return (
    <div style={styles.factRow}>
      <dt style={styles.factK}>{k}</dt>
      <dd
        style={{
          ...styles.factV,
          ...(mono ? { fontFamily: 'inherit', fontSize: 11 } : null),
        }}
      >
        {v == null || v === '' ? '—' : v}
      </dd>
    </div>
  );
}

function fmtBytes(n) {
  if (n == null) return '—';
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / (1024 * 1024)).toFixed(2)}MB`;
}

function fmtDate(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleString();
  } catch {
    return String(s);
  }
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 14,
    gap: 16,
    flexWrap: 'wrap',
  },
  h1: { fontSize: 20, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  actions: { display: 'flex', gap: 8 },
  drop: {
    border: '1px dashed var(--line-2)',
    borderRadius: 6,
    padding: '20px 16px',
    textAlign: 'center',
    color: 'var(--fg-3)',
    fontSize: 12,
    marginBottom: 14,
    transition: 'all 100ms',
  },
  dropActive: {
    borderColor: 'var(--accent)',
    color: 'var(--accent)',
    background: 'color-mix(in oklab, var(--accent) 10%, transparent)',
  },
  failBlock: {
    border: '1px solid var(--danger)',
    borderRadius: 4,
    padding: '10px 12px',
    marginBottom: 14,
    background: 'color-mix(in oklab, var(--danger) 8%, transparent)',
  },
  failTitle: {
    fontSize: 11,
    color: 'var(--danger)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
    marginBottom: 6,
  },
  failRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 11,
    color: 'var(--fg-2)',
    padding: '2px 0',
  },
  failName: { fontWeight: 500 },
  failErr: { color: 'var(--fg-3)' },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: 12,
  },
  tile: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: 0,
    overflow: 'hidden',
    cursor: 'pointer',
    fontFamily: 'inherit',
    color: 'inherit',
    display: 'flex',
    flexDirection: 'column',
    textAlign: 'left',
  },
  tileActive: {
    borderColor: 'var(--accent)',
    boxShadow: '0 0 0 1px var(--accent) inset',
  },
  thumbBox: {
    aspectRatio: '4 / 3',
    background: 'var(--bg)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    borderBottom: '1px solid var(--line)',
  },
  thumb: { width: '100%', height: '100%', objectFit: 'cover' },
  fileGlyph: {
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  fileGlyphLg: {
    fontSize: 14,
    color: 'var(--fg-3)',
    padding: 40,
    textAlign: 'center',
  },
  tileMeta: { padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 2 },
  tileName: {
    fontSize: 12,
    color: 'var(--fg)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  tileSub: { fontSize: 10, color: 'var(--fg-4)' },
  modalShell: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.6)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    zIndex: 50,
  },
  modal: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 8,
    width: '100%',
    maxWidth: 720,
    maxHeight: '90vh',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, monospace",
  },
  modalHead: {
    padding: '12px 16px',
    borderBottom: '1px solid var(--line)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  modalTitle: { fontSize: 13, color: 'var(--fg)' },
  modalBody: {
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflow: 'auto',
  },
  preview: {
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    minHeight: 180,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  previewImg: { maxWidth: '100%', maxHeight: 320, objectFit: 'contain' },
  facts: { margin: 0, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 },
  factRow: { display: 'flex', flexDirection: 'column', minWidth: 0 },
  factK: {
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  factV: {
    margin: 0,
    fontSize: 12,
    color: 'var(--fg-2)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  label: { display: 'flex', flexDirection: 'column', gap: 6, position: 'relative' },
  labelText: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  textarea: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '10px 12px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    outline: 'none',
    resize: 'vertical',
  },
  counter: {
    position: 'absolute',
    right: 6,
    bottom: 6,
    fontSize: 10,
    color: 'var(--fg-4)',
  },
  modalFoot: {
    padding: '12px 16px',
    borderTop: '1px solid var(--line)',
    display: 'flex',
    gap: 8,
    alignItems: 'center',
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
  btnDanger: {
    background: 'transparent',
    border: '1px solid var(--danger)',
    color: 'var(--danger)',
    padding: '8px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 12,
    cursor: 'pointer',
  },
  iconBtn: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '4px 10px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 11,
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
    margin: '8px 0',
  },
};
