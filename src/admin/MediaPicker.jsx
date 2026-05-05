// Shared image-only media picker. Used by the Posts editor's
// 插入图片 button (Task 12) and could be reused by Profile/SiteIdentity
// avatar pickers later — kept generic with a single onPick callback.

import { useEffect, useState } from 'react';
import { apiMedia, mediaUrl } from '../api/media.js';

export default function MediaPicker({
  open,
  onPick,
  onClose,
  title = '选择图片',
  filterImagesOnly = true,
  current = null,
}) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    let mounted = true;
    setItems(null);
    setError(null);
    apiMedia
      .list({ limit: 200 })
      .then((rows) => {
        if (!mounted) return;
        const filtered = filterImagesOnly
          ? (rows || []).filter(
              (m) => typeof m.mime_type === 'string' && m.mime_type.startsWith('image/'),
            )
          : rows || [];
        setItems(filtered);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.detail || err?.message || '加载失败');
      });
    return () => {
      mounted = false;
    };
  }, [open, filterImagesOnly]);

  if (!open) return null;

  return (
    <div style={styles.shell} onClick={onClose} data-testid="media-picker">
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.head}>
          <span style={styles.title}>{title}</span>
          <button type="button" onClick={onClose} style={styles.iconBtn}>
            关闭 ✕
          </button>
        </div>
        <div style={styles.body}>
          {items === null && !error && <div style={styles.muted}>加载图片中…</div>}
          {error && <div style={styles.error}>错误：{error}</div>}
          {items && items.length === 0 && (
            <div style={styles.muted}>媒体库还没有图片 — 请先在「媒体」上传。</div>
          )}
          {items && items.length > 0 && (
            <div style={styles.grid}>
              {items.map((m) => {
                const active = current != null && m.id === current;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => onPick(m)}
                    style={{ ...styles.tile, ...(active ? styles.tileActive : null) }}
                    title={`${m.filename} · ${m.alt || '无 alt'}`}
                    data-testid={`media-tile-${m.id}`}
                  >
                    <img src={mediaUrl(m)} alt={m.alt || m.filename} style={styles.img} />
                    <div style={styles.cap}>{m.filename}</div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div style={styles.foot}>
          <span style={{ flex: 1 }} />
          <button type="button" style={styles.btn} onClick={onClose}>
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  shell: {
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
    maxHeight: '85vh',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, monospace",
  },
  head: {
    padding: '12px 16px',
    borderBottom: '1px solid var(--line)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  title: { fontSize: 13, color: 'var(--fg)' },
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
  body: {
    padding: 16,
    overflow: 'auto',
    flex: 1,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
    gap: 10,
  },
  tile: {
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: 0,
    overflow: 'hidden',
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: 'inherit',
  },
  tileActive: {
    borderColor: 'var(--accent)',
    boxShadow: '0 0 0 1px var(--accent) inset',
  },
  img: { width: '100%', aspectRatio: '1 / 1', objectFit: 'cover' },
  cap: {
    padding: '5px 8px',
    fontSize: 10,
    color: 'var(--fg-3)',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  foot: {
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
    padding: '6px 12px',
    borderRadius: 4,
    fontFamily: 'inherit',
    fontSize: 12,
    cursor: 'pointer',
  },
  muted: { color: 'var(--fg-3)', fontSize: 12, padding: '24px 0', textAlign: 'center' },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
  },
};
