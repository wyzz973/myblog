import { useEffect, useMemo, useRef, useState } from 'react';
import { postsApi } from '../api/posts.js';

const NEW_POST_TEMPLATE = `---
id: my-new-post
n: "001"
title: "My new post"
subtitle: ""
tag: notes
date: ${new Date().toISOString().slice(0, 10)}
lang: en
read: "5 min"
status: draft
summary: ""
tldr: ""
---

Write your post body here in **markdown**.
`;

export default function PostEditor({ id, onClose, onSaved }) {
  const isNew = id == null;
  const [markdown, setMarkdown] = useState(isNew ? NEW_POST_TEMPLATE : '');
  const [originalId] = useState(id);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [overwrite, setOverwrite] = useState(false);

  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (isNew) return;
    let mounted = true;
    setLoading(true);
    postsApi
      .get(id)
      .then((p) => {
        if (!mounted) return;
        const fmLines = [
          '---',
          `id: ${p.id}`,
          `n: "${p.n ?? ''}"`,
          `title: ${jsonish(p.title)}`,
          p.subtitle != null ? `subtitle: ${jsonish(p.subtitle)}` : null,
          `tag: ${p.tag}`,
          `date: ${p.date}`,
          `lang: ${p.lang}`,
          p.read != null ? `read: ${jsonish(p.read)}` : null,
          p.summary != null ? `summary: ${jsonish(p.summary)}` : null,
          p.tldr != null ? `tldr: ${jsonish(p.tldr)}` : null,
          '---',
          '',
        ]
          .filter(Boolean)
          .join('\n');
        setMarkdown(fmLines + (p.body_md ?? ''));
        setLoadError(null);
      })
      .catch((err) => {
        if (!mounted) return;
        setLoadError(err?.detail || err?.message || 'failed to load');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [id, isNew]);

  // Debounced live preview.
  useEffect(() => {
    if (!markdown.trim()) {
      setPreview(null);
      setPreviewError(null);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPreviewing(true);
      postsApi
        .renderPreview(markdown)
        .then((res) => {
          setPreview(res);
          setPreviewError(null);
        })
        .catch((err) => {
          setPreviewError(err?.detail || err?.message || 'preview failed');
        })
        .finally(() => setPreviewing(false));
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [markdown]);

  async function onSave() {
    setSaving(true);
    setSaveError(null);
    try {
      if (isNew) {
        await postsApi.create(markdown, { overwrite });
      } else {
        await postsApi.patch(originalId, markdown);
      }
      onSaved?.();
    } catch (err) {
      setSaveError(err?.detail || err?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }

  const fmInfo = useMemo(() => {
    if (!preview || !preview.frontmatter) return null;
    return preview.frontmatter;
  }, [preview]);

  return (
    <div>
      <header style={styles.header}>
        <div>
          <h1 style={styles.h1}>
            {isNew ? 'New post' : `Edit · ${originalId}`}
          </h1>
          <p style={styles.lead}>
            Markdown source with YAML frontmatter. Saves through the markdown
            ingest pipeline.
          </p>
        </div>
        <div style={styles.headerBtns}>
          <button type="button" style={styles.btnGhost} onClick={onClose}>
            cancel
          </button>
          <button
            type="button"
            style={styles.btnPrimary}
            onClick={onSave}
            disabled={saving || loading}
          >
            {saving ? 'saving…' : isNew ? 'create →' : 'save →'}
          </button>
        </div>
      </header>

      {loadError && <div style={styles.error}>! {loadError}</div>}
      {saveError && <div style={styles.error}>! {saveError}</div>}

      {isNew && (
        <label style={styles.overwriteRow}>
          <input
            type="checkbox"
            checked={overwrite}
            onChange={(e) => setOverwrite(e.target.checked)}
          />
          <span>overwrite if id already exists</span>
        </label>
      )}

      <div style={styles.cols}>
        <div style={styles.col}>
          <div style={styles.colHead}>markdown source</div>
          <textarea
            value={markdown}
            onChange={(e) => setMarkdown(e.target.value)}
            spellCheck={false}
            style={styles.textarea}
            placeholder="--- frontmatter ---\nbody…"
          />
        </div>
        <div style={styles.col}>
          <div style={styles.colHead}>
            preview {previewing && <span style={styles.dim}>· rendering…</span>}
          </div>
          <div style={styles.preview}>
            {previewError && (
              <div style={styles.previewError}>preview error: {previewError}</div>
            )}
            {preview?.errors?.length > 0 && (
              <div style={styles.previewError}>
                <strong>errors:</strong>
                <ul style={styles.errList}>
                  {preview.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}
            {fmInfo && (
              <div style={styles.fmCard}>
                <div style={styles.fmTitle}>{fmInfo.title}</div>
                {fmInfo.subtitle && (
                  <div style={styles.fmSub}>{fmInfo.subtitle}</div>
                )}
                <div style={styles.fmMeta}>
                  <span>id: {fmInfo.id}</span>
                  <span>tag: {fmInfo.tag}</span>
                  <span>date: {fmInfo.date}</span>
                  <span>lang: {fmInfo.lang}</span>
                  {fmInfo.read && <span>read: {fmInfo.read}</span>}
                  {fmInfo.status && <span>status: {fmInfo.status}</span>}
                </div>
              </div>
            )}
            {preview?.body && <BlockRenderer blocks={preview.body} />}
            {!preview && !previewError && (
              <div style={styles.muted}>start typing to see preview…</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Cheap block renderer — handles the common block types emitted by the
// markdown_pipeline parser. Covers ~90% of post content; rare/exotic types
// fall through to a JSON dump so authors at least see something useful.
function BlockRenderer({ blocks }) {
  return (
    <div>
      {blocks.map((b, i) => (
        <Block key={i} block={b} />
      ))}
    </div>
  );
}

function Block({ block }) {
  const t = block.type;
  switch (t) {
    case 'heading': {
      const level = Math.min(Math.max(block.level || 2, 1), 6);
      const Tag = `h${level}`;
      return (
        <Tag style={blockStyles.heading}>
          {renderInlines(block.children)}
        </Tag>
      );
    }
    case 'paragraph':
      return <p style={blockStyles.p}>{renderInlines(block.children)}</p>;
    case 'list':
    case 'unordered_list':
    case 'ordered_list': {
      const ordered = block.ordered === true || t === 'ordered_list';
      const Tag = ordered ? 'ol' : 'ul';
      return (
        <Tag style={blockStyles.list}>
          {(block.items || []).map((item, i) => (
            <li key={i}>{renderInlines(item.children || item)}</li>
          ))}
        </Tag>
      );
    }
    case 'code':
    case 'fenced_code':
    case 'block_code':
      return (
        <pre style={blockStyles.code}>
          <code>{block.text || block.raw || ''}</code>
        </pre>
      );
    case 'quote':
    case 'block_quote':
      return (
        <blockquote style={blockStyles.quote}>
          {(block.children || []).map((c, i) => (
            <Block key={i} block={c} />
          ))}
        </blockquote>
      );
    case 'thematic_break':
    case 'hr':
      return <hr style={blockStyles.hr} />;
    case 'image':
      return (
        <img
          src={block.src || block.url}
          alt={block.alt || ''}
          style={blockStyles.img}
        />
      );
    default:
      return (
        <pre style={blockStyles.unknown}>
          {JSON.stringify(block, null, 2)}
        </pre>
      );
  }
}

function renderInlines(children) {
  if (!children) return null;
  if (typeof children === 'string') return children;
  if (!Array.isArray(children)) return String(children);
  return children.map((c, i) => {
    if (typeof c === 'string') return <span key={i}>{c}</span>;
    if (!c || !c.type) return null;
    switch (c.type) {
      case 'text':
        return <span key={i}>{c.text || ''}</span>;
      case 'strong':
        return <strong key={i}>{renderInlines(c.children)}</strong>;
      case 'emphasis':
      case 'em':
        return <em key={i}>{renderInlines(c.children)}</em>;
      case 'codespan':
      case 'code':
        return (
          <code key={i} style={blockStyles.codespan}>
            {c.text || c.raw || ''}
          </code>
        );
      case 'link':
        return (
          <a key={i} href={c.url || c.href} style={blockStyles.link}>
            {renderInlines(c.children) || c.text}
          </a>
        );
      case 'image':
        return (
          <img
            key={i}
            src={c.src || c.url}
            alt={c.alt || ''}
            style={blockStyles.img}
          />
        );
      default:
        return <span key={i}>{c.text || ''}</span>;
    }
  });
}

function jsonish(v) {
  if (v == null) return '""';
  const s = String(v);
  if (/[:#"'\\]|^\s|\s$/.test(s)) return JSON.stringify(s);
  return s;
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 16,
    gap: 12,
  },
  h1: { fontSize: 18, margin: 0, fontWeight: 600, color: 'var(--fg)' },
  lead: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0 0' },
  headerBtns: { display: 'flex', gap: 8 },
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
  btnGhost: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '8px 14px',
    borderRadius: 4,
    fontSize: 12,
    fontFamily: 'inherit',
    cursor: 'pointer',
  },
  overwriteRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 11,
    color: 'var(--fg-3)',
    marginBottom: 12,
  },
  cols: {
    display: 'grid',
    gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
    gap: 14,
    minHeight: 540,
  },
  col: {
    display: 'flex',
    flexDirection: 'column',
    border: '1px solid var(--line)',
    borderRadius: 6,
    background: 'var(--bg-2)',
    overflow: 'hidden',
    minWidth: 0,
  },
  colHead: {
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    padding: '8px 12px',
    borderBottom: '1px solid var(--line)',
    background: 'var(--bg)',
  },
  textarea: {
    flex: 1,
    background: 'var(--bg)',
    border: 0,
    color: 'var(--fg)',
    padding: '12px',
    fontFamily: 'inherit',
    fontSize: 12,
    lineHeight: 1.55,
    outline: 'none',
    resize: 'vertical',
    minHeight: 500,
  },
  preview: {
    flex: 1,
    padding: '14px 16px',
    fontSize: 13,
    color: 'var(--fg-2)',
    overflow: 'auto',
    minHeight: 500,
  },
  previewError: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '8px 10px',
    borderRadius: 4,
    marginBottom: 10,
  },
  errList: { margin: '4px 0 0 16px', padding: 0 },
  fmCard: {
    border: '1px solid var(--line)',
    borderRadius: 4,
    padding: '10px 12px',
    marginBottom: 12,
    background: 'var(--bg)',
  },
  fmTitle: { fontSize: 16, fontWeight: 600, color: 'var(--fg)' },
  fmSub: { fontSize: 12, color: 'var(--fg-3)', marginTop: 2 },
  fmMeta: {
    marginTop: 8,
    display: 'flex',
    flexWrap: 'wrap',
    gap: 10,
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'lowercase',
    letterSpacing: '0.04em',
  },
  muted: { color: 'var(--fg-4)', fontSize: 12 },
  dim: { color: 'var(--fg-4)', fontSize: 10, marginLeft: 6 },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
    marginBottom: 14,
  },
};

const blockStyles = {
  heading: { color: 'var(--fg)', margin: '14px 0 8px' },
  p: { margin: '8px 0', color: 'var(--fg-2)', lineHeight: 1.6 },
  list: { margin: '8px 0', paddingLeft: 22, color: 'var(--fg-2)' },
  code: {
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    padding: '10px 12px',
    fontSize: 11,
    overflow: 'auto',
    borderRadius: 4,
    color: 'var(--fg-2)',
  },
  codespan: {
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    padding: '0 4px',
    fontSize: 11,
    borderRadius: 3,
  },
  quote: {
    borderLeft: '2px solid var(--line-2)',
    margin: '8px 0',
    padding: '0 12px',
    color: 'var(--fg-3)',
  },
  hr: { border: 0, borderTop: '1px dashed var(--line-2)', margin: '14px 0' },
  link: { color: 'var(--accent)' },
  img: { maxWidth: '100%', borderRadius: 4 },
  unknown: {
    background: 'var(--bg)',
    border: '1px dashed var(--line-2)',
    padding: '6px 8px',
    fontSize: 10,
    color: 'var(--fg-4)',
    overflow: 'auto',
    borderRadius: 4,
  },
};
