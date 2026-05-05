import { useEffect, useMemo, useRef, useState } from 'react';
import { postsApi } from '../api/posts.js';
import {
  parseFrontmatter,
  serializeFrontmatter,
  setFmField,
  STATUS_VALUES,
} from './frontmatter.js';
import MediaPicker from './MediaPicker.jsx';
import { buildImageMarkdown, insertAt } from './markdownInsert.js';
import { clearDraft, draftIsNewerThan, loadDraft, saveDraft } from './draftStore.js';

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

  const textareaRef = useRef(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  // Autosave + recovery state.
  // `draftCandidate` is non-null only on initial load when a stale
  // localStorage draft was newer than the server copy — the UI shows a
  // banner with 恢复 / 丢弃 buttons. After the user picks one, we
  // clear it and proceed normally.
  const [draftCandidate, setDraftCandidate] = useState(null);
  const [draftSavedAt, setDraftSavedAt] = useState(null);
  const autosaveRef = useRef(null);
  const dirtyRef = useRef(false);

  const draftKey = isNew ? '__new__' : id;

  function insertImage(item) {
    const md = buildImageMarkdown(item);
    if (!md) return;
    const ta = textareaRef.current;
    const start = ta?.selectionStart ?? markdown.length;
    const end = ta?.selectionEnd ?? markdown.length;
    const { value, cursor } = insertAt(markdown, start, end, md);
    dirtyRef.current = true;
    setMarkdown(value);
    setPickerOpen(false);
    // Restore caret just past the inserted directive on next paint.
    requestAnimationFrame(() => {
      const t = textareaRef.current;
      if (!t) return;
      t.focus();
      t.setSelectionRange(cursor, cursor);
    });
  }

  // ⌘ / Ctrl + I opens the picker. Bound to the textarea element to
  // avoid swallowing the global browser shortcut elsewhere on the page.
  function onTextareaKeyDown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'i') {
      e.preventDefault();
      setPickerOpen(true);
    }
  }

  useEffect(() => {
    if (isNew) {
      // For a brand-new post, surface a banner if a previous "__new__"
      // draft was left behind by an earlier session.
      const draft = loadDraft('__new__');
      if (draft && draft.markdown !== NEW_POST_TEMPLATE) {
        setDraftCandidate(draft);
      }
      return;
    }
    let mounted = true;
    setLoading(true);
    postsApi
      .get(id)
      .then((p) => {
        if (!mounted) return;
        // Build the initial markdown from the canonical fields. Lifecycle
        // fields (status / scheduled_at / featured / private /
        // comments_enabled) are surfaced in GUI controls; they round-trip
        // through frontmatter the same as everything else.
        const fm = {
          id: p.id,
          n: p.n,
          title: p.title,
          subtitle: p.subtitle,
          tag: p.tag,
          date: p.date,
          lang: p.lang,
          read: p.read,
          summary: p.summary,
          tldr: p.tldr,
          status: p.status,
          scheduled_at: p.scheduled_at,
          featured: p.featured,
          private: p.private,
          comments_enabled: p.comments_enabled,
        };
        // Drop nulls and falsy booleans — serializer filters them, but
        // dropping here keeps the live state object compact.
        Object.keys(fm).forEach((k) => {
          if (fm[k] == null) delete fm[k];
        });
        const initial = serializeFrontmatter(fm, [], p.body_md ?? '');
        setMarkdown(initial);
        setLoadError(null);
        // Recovery check: did a previous session leave behind a draft
        // that's newer than the server's last write? If so, surface it
        // — the user picks 恢复 (replace markdown with draft) or 丢弃
        // (clear localStorage and stay with server).
        const draft = loadDraft(id);
        const serverTs = p.updated_at || p.date || null;
        if (
          draft
          && draft.markdown !== initial
          && draftIsNewerThan(draft, serverTs)
        ) {
          setDraftCandidate(draft);
        }
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

  // Autosave loop: write the current markdown to localStorage every ~5s
  // when the editor is dirty. Reset on successful save.
  useEffect(() => {
    if (loading) return undefined;
    if (autosaveRef.current) clearTimeout(autosaveRef.current);
    autosaveRef.current = setTimeout(() => {
      if (!dirtyRef.current) return;
      const ts = Date.now();
      saveDraft(draftKey, markdown, ts);
      setDraftSavedAt(ts);
    }, 5000);
    return () => {
      if (autosaveRef.current) clearTimeout(autosaveRef.current);
    };
  }, [markdown, loading, draftKey]);

  function recoverDraft() {
    if (!draftCandidate) return;
    setMarkdown(draftCandidate.markdown);
    setDraftCandidate(null);
    setDraftSavedAt(draftCandidate.savedAt);
  }

  function discardDraft() {
    clearDraft(draftKey);
    setDraftCandidate(null);
    setDraftSavedAt(null);
  }

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

  // Derived GUI state — single source of truth is the markdown text.
  const fm = useMemo(() => parseFrontmatter(markdown).fm, [markdown]);

  function updateField(name, value) {
    dirtyRef.current = true;
    setMarkdown((prev) => setFmField(prev, name, value));
  }

  // datetime-local needs `YYYY-MM-DDTHH:MM`. Backend round-trips full ISO,
  // so accept both shapes when populating the input.
  const scheduledLocal = useMemo(() => {
    const v = fm.scheduled_at;
    if (!v) return '';
    const d = new Date(v);
    if (Number.isNaN(d.getTime())) return v;
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }, [fm.scheduled_at]);

  async function onSave() {
    setSaving(true);
    setSaveError(null);
    try {
      // Validate scheduled posts before round-tripping through the
      // backend so the user gets a fast, specific error.
      if (fm.status === 'scheduled') {
        if (!fm.scheduled_at) {
          throw new Error('scheduled posts need a scheduled_at date');
        }
        const at = new Date(fm.scheduled_at).getTime();
        if (Number.isNaN(at)) throw new Error('scheduled_at is not a valid date');
        if (at <= Date.now()) throw new Error('scheduled_at must be in the future');
      }
      if (isNew) {
        await postsApi.create(markdown, { overwrite });
      } else {
        await postsApi.patch(originalId, markdown);
      }
      // Successful save → flush the autosave snapshot. Subsequent edits
      // will start a fresh draft.
      clearDraft(draftKey);
      dirtyRef.current = false;
      setDraftSavedAt(null);
      onSaved?.();
    } catch (err) {
      setSaveError(err?.detail || err?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }

  const fmInfo = preview?.frontmatter || null;

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

      {draftCandidate && (
        <div style={styles.draftBanner} data-testid="draft-banner">
          <span style={styles.draftBannerText}>
            发现未保存的草稿（{fmtAgo(draftCandidate.savedAt)}）。
          </span>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            onClick={recoverDraft}
            style={styles.draftBtnPrimary}
            data-testid="draft-recover"
          >
            恢复
          </button>
          <button
            type="button"
            onClick={discardDraft}
            style={styles.draftBtnGhost}
            data-testid="draft-discard"
          >
            丢弃
          </button>
        </div>
      )}

      {draftSavedAt && !draftCandidate && (
        <div style={styles.draftStatus} data-testid="draft-status">
          已自动保存 · {fmtAgo(draftSavedAt)}
        </div>
      )}

      <div style={styles.fieldsStrip} data-testid="post-fields-strip">
        <label style={styles.fieldGroup}>
          <span style={styles.fieldLabel}>status</span>
          <select
            value={fm.status || ''}
            onChange={(e) => updateField('status', e.target.value)}
            style={styles.select}
            data-testid="status-select"
          >
            {!fm.status && <option value="">—</option>}
            {STATUS_VALUES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        {fm.status === 'scheduled' && (
          <label style={styles.fieldGroup}>
            <span style={styles.fieldLabel}>scheduled_at</span>
            <input
              type="datetime-local"
              value={scheduledLocal}
              onChange={(e) => updateField('scheduled_at', e.target.value)}
              style={styles.dateInput}
              data-testid="scheduled-at-input"
            />
          </label>
        )}

        <ToggleField
          name="featured"
          checked={fm.featured === true}
          onChange={(v) => updateField('featured', v)}
        />
        <ToggleField
          name="private"
          checked={fm.private === true}
          onChange={(v) => updateField('private', v)}
        />
        <ToggleField
          name="comments_enabled"
          checked={fm.comments_enabled !== false}
          onChange={(v) => updateField('comments_enabled', v ? null : false)}
          // comments_enabled defaults to true; we represent the "off" state
          // explicitly, the "on" state implicitly (omitted line).
          tristate
        />
      </div>

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
          <div style={styles.colHead}>
            <span>markdown source</span>
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              style={styles.colHeadBtn}
              title="从媒体库插入图片 (⌘ I)"
              data-testid="insert-image-btn"
            >
              插入图片
            </button>
          </div>
          <textarea
            ref={textareaRef}
            value={markdown}
            onChange={(e) => {
              dirtyRef.current = true;
              setMarkdown(e.target.value);
            }}
            onKeyDown={onTextareaKeyDown}
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

      <MediaPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={insertImage}
        title="插入图片"
      />
    </div>
  );
}

function fmtAgo(ts) {
  if (!ts) return '刚刚';
  const ms = Date.now() - ts;
  if (ms < 0 || ms < 60_000) return '刚刚';
  const m = Math.floor(ms / 60_000);
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  return `${Math.floor(h / 24)} 天前`;
}

function ToggleField({ name, checked, onChange }) {
  return (
    <label style={styles.fieldGroup} data-testid={`toggle-${name}`}>
      <span style={styles.fieldLabel}>{name}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={styles.toggle}
      />
    </label>
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
  draftBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 12px',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    background: 'color-mix(in oklab, var(--accent) 12%, transparent)',
    borderRadius: 4,
    marginBottom: 12,
    fontSize: 11,
    color: 'var(--fg)',
  },
  draftBannerText: { color: 'var(--fg-2)' },
  draftBtnPrimary: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    border: 0,
    padding: '4px 12px',
    borderRadius: 3,
    fontFamily: 'inherit',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
  },
  draftBtnGhost: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '4px 12px',
    borderRadius: 3,
    fontFamily: 'inherit',
    fontSize: 11,
    cursor: 'pointer',
  },
  draftStatus: {
    fontSize: 10,
    color: 'var(--fg-4)',
    marginBottom: 10,
    fontStyle: 'italic',
  },
  fieldsStrip: {
    display: 'flex',
    gap: 16,
    flexWrap: 'wrap',
    alignItems: 'center',
    padding: '10px 12px',
    border: '1px solid var(--line)',
    borderRadius: 4,
    background: 'var(--bg-2)',
    marginBottom: 12,
  },
  fieldGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 11,
    color: 'var(--fg-3)',
  },
  fieldLabel: {
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
  },
  select: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '4px 8px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 3,
    outline: 'none',
  },
  dateInput: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '4px 8px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 3,
    outline: 'none',
  },
  toggle: {
    cursor: 'pointer',
    accentColor: 'var(--accent)',
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
    padding: '6px 12px',
    borderBottom: '1px solid var(--line)',
    background: 'var(--bg)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    minHeight: 28,
  },
  colHeadBtn: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '3px 9px',
    borderRadius: 3,
    fontSize: 10,
    fontFamily: 'inherit',
    letterSpacing: '0.04em',
    cursor: 'pointer',
    textTransform: 'none',
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
