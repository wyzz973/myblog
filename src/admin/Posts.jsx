import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { postsApi } from '../api/posts.js';
import PostEditor from './PostEditor.jsx';
import { shouldIgnoreEvent } from './keyboardShortcuts.js';
import useSyncedSearchParams from './useSyncedSearchParams.js';
import { intParser } from './searchParamsState.js';
import { useConfirm, useToast } from './ui/UIProvider.jsx';
import SectionHead from './ui/SectionHead.jsx';

const STATUS_FILTERS = [
  { key: 'all', label: 'all' },
  { key: 'published', label: 'published' },
  { key: 'draft', label: 'draft' },
  { key: 'scheduled', label: 'scheduled' },
];

const PAGE_SIZE_OPTIONS = [20, 50, 100];

// querystring schema — kept module-level so the hook's deps stay stable.
const URL_SCHEMA = [
  { key: 'status', defaultValue: 'all' },
  { key: 'q', defaultValue: '' },
  { key: 'page', defaultValue: 1, parse: intParser(1, 1) },
  { key: 'pageSize', defaultValue: 20, parse: intParser(1, 20) },
];

export default function Posts() {
  const [filters, setFilters] = useSyncedSearchParams(URL_SCHEMA);
  const { status: statusFilter, q, page, pageSize } = filters;
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // null | "__new__" | id
  const [reloadTick, setReloadTick] = useState(0);
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const [bulkOpen, setBulkOpen] = useState(false);
  const rowRefs = useRef([]);

  const reload = useCallback(() => setReloadTick((t) => t + 1), []);

  // Side-door for ⌘K: the command palette navigates here with
  // `state.editPost` set to either an id or "__new__". We pop it once and
  // clear the state so a Back/Forward doesn't re-open the editor.
  // Preserve the current querystring so URL-synced filters survive.
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const want = location.state?.editPost;
    if (!want) return;
    setEditing(want);
    navigate(
      { pathname: location.pathname, search: location.search },
      { replace: true, state: null },
    );
  }, [location, navigate]);

  useEffect(() => {
    if (editing !== null) return;
    let mounted = true;
    setLoading(true);
    postsApi
      .list({
        status: statusFilter === 'all' ? undefined : statusFilter,
        q: q.trim() || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      })
      .then((res) => {
        if (!mounted) return;
        setItems(res.items || []);
        setTotal(res.total ?? (res.items || []).length);
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
  }, [statusFilter, q, editing, reloadTick, pageSize, page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const onPage = useCallback(
    (n) => setFilters({ page: Math.min(Math.max(1, n), totalPages) }),
    [setFilters, totalPages],
  );

  // Reset row focus whenever the visible item set changes.
  useEffect(() => {
    setFocusedIdx(items.length > 0 ? 0 : -1);
  }, [items]);

  // j/k row navigation, Enter / e edit, n new. Listener detaches while
  // editing (PostEditor is rendered instead) or while a global suppress
  // surface (palette / modal / help) is mounted — `shouldIgnoreEvent`
  // covers both via its DOM probe.
  useEffect(() => {
    if (editing !== null) return undefined;
    function onKey(e) {
      if (shouldIgnoreEvent(e)) return;
      if (e.key === 'j') {
        e.preventDefault();
        setFocusedIdx((i) => Math.min((items.length || 1) - 1, i + 1));
      } else if (e.key === 'k') {
        e.preventDefault();
        setFocusedIdx((i) => Math.max(0, i - 1));
      } else if (e.key === 'Enter' || e.key === 'e') {
        const row = items[focusedIdx];
        if (!row) return;
        e.preventDefault();
        setEditing(row.id);
      } else if (e.key === 'n') {
        e.preventDefault();
        setEditing('__new__');
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [editing, items, focusedIdx]);

  // Scroll the focused row into view if the user moved past the
  // viewport via j/k.
  useEffect(() => {
    const el = rowRefs.current[focusedIdx];
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    }
  }, [focusedIdx]);

  const confirm = useConfirm();
  const toast = useToast();

  async function onDelete(id) {
    const ok = await confirm({
      title: '删除文章',
      message: `确定删除 “${id}” 吗？此操作不可撤销。`,
      confirmLabel: '删除',
      destructive: true,
    });
    if (!ok) return;
    try {
      await postsApi.remove(id);
      toast.success(`已删除 ${id}`);
      reload();
    } catch (err) {
      toast.error(`删除失败：${err?.detail || err?.message || '未知错误'}`);
    }
  }

  if (editing !== null) {
    return (
      <PostEditor
        id={editing === '__new__' ? null : editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          reload();
        }}
      />
    );
  }

  return (
    <div>
      <header style={styles.header}>
        <div style={{ flex: 1 }}>
          <SectionHead
            n="02"
            title="./posts"
            count={loading ? 'loading…' : `${total} entries`}
          />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ExportTarButton />
          <button
            type="button"
            style={styles.btnGhost}
            onClick={() => setBulkOpen(true)}
            data-testid="posts-bulk-upload"
          >
            批量导入
          </button>
          <button
            type="button"
            style={styles.btnPrimary}
            onClick={() => setEditing('__new__')}
          >
            + 新建文章
          </button>
        </div>
      </header>
      {bulkOpen && (
        <BulkUploadModal
          onClose={() => setBulkOpen(false)}
          onDone={() => { setBulkOpen(false); reload(); }}
        />
      )}

      <div style={styles.toolRow}>
        <div style={styles.chips}>
          {STATUS_FILTERS.map((f) => {
            const active = f.key === statusFilter;
            return (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilters({ status: f.key, page: 1 })}
                style={{ ...styles.chip, ...(active ? styles.chipActive : null) }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
        <input
          type="search"
          placeholder="search title / body…"
          value={q}
          onChange={(e) => setFilters({ q: e.target.value, page: 1 })}
          style={styles.search}
        />
      </div>

      {error && <div style={styles.error}>! {error}</div>}

      <div style={styles.kbdHint} data-testid="posts-kbd-hint">
        <kbd style={styles.kbd}>j</kbd> / <kbd style={styles.kbd}>k</kbd> 行间移动 ·{' '}
        <kbd style={styles.kbd}>Enter</kbd> / <kbd style={styles.kbd}>e</kbd> 编辑 ·{' '}
        <kbd style={styles.kbd}>n</kbd> 新建
      </div>

      {!error && (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>序号</th>
                <th style={styles.th}>标题</th>
                <th style={styles.th}>标签</th>
                <th style={styles.th}>日期</th>
                <th style={styles.th}>语言</th>
                <th style={styles.th}>阅读</th>
                <th style={styles.th}>状态</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>点赞</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && !loading && (
                <tr>
                  <td colSpan={9} style={styles.empty}>
                    暂无文章
                  </td>
                </tr>
              )}
              {items.map((p, idx) => (
                <tr
                  key={p.id}
                  ref={(el) => { rowRefs.current[idx] = el; }}
                  data-testid={`post-row-${idx}`}
                  data-focused={idx === focusedIdx ? 'true' : undefined}
                  style={{
                    ...styles.tr,
                    ...(idx === focusedIdx ? styles.trFocused : null),
                  }}
                  onMouseEnter={() => setFocusedIdx(idx)}
                >
                  <td style={styles.tdN}>{p.n || '—'}</td>
                  <td style={styles.tdTitle}>
                    <div style={styles.title}>{p.title}</div>
                    {p.subtitle && (
                      <div style={styles.subtitle}>{p.subtitle}</div>
                    )}
                    <div style={styles.idHint}>
                      id: {p.id}
                      <button
                        type="button"
                        style={styles.idCopyBtn}
                        title="复制 id 到剪贴板"
                        data-testid={`copy-id-${p.id}`}
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            await navigator.clipboard.writeText(p.id);
                            toast.success(`已复制 ${p.id}`);
                          } catch {
                            toast.error('复制失败');
                          }
                        }}
                      >
                        ⧉
                      </button>
                    </div>
                  </td>
                  <td style={styles.td}>
                    <span style={styles.tagPill}>{p.tag}</span>
                  </td>
                  <td style={styles.td}>{p.date}</td>
                  <td style={styles.td}>{p.lang}</td>
                  <td style={styles.td}>{p.read || '—'}</td>
                  <td style={styles.td} data-testid={`status-${p.id}`}>
                    <span style={statusPillStyle(p.status)}>
                      {statusLabel(p.status)}
                    </span>
                  </td>
                  <td
                    style={{ ...styles.td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}
                    data-testid={`likes-${p.id}`}
                  >
                    {typeof p.likes === 'number' ? p.likes : 0}
                  </td>
                  <td style={{ ...styles.td, textAlign: 'right' }}>
                    <a
                      href={`/p/${encodeURIComponent(p.id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={styles.btnGhostLink}
                      title="在新标签页打开公开页"
                      data-testid={`public-link-${p.id}`}
                    >
                      ↗ 公开页
                    </a>
                    <button
                      type="button"
                      style={styles.btnGhost}
                      onClick={() => setEditing(p.id)}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      style={styles.btnDanger}
                      onClick={() => onDelete(p.id)}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!error && total > 0 && (
        <div style={styles.pager}>
          <div style={styles.pagerInfo}>
            page {page} / {totalPages} · showing {items.length} of {total}
          </div>
          <div style={styles.pagerControls}>
            <label style={styles.pagerLabel}>
              <span style={styles.dim}>per page</span>
              <select
                value={pageSize}
                onChange={(e) => setFilters({ pageSize: Number(e.target.value), page: 1 })}
                style={styles.pagerSelect}
              >
                {PAGE_SIZE_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              style={styles.btnGhost}
              onClick={() => onPage(page - 1)}
              disabled={page <= 1 || loading}
            >
              ← prev
            </button>
            <button
              type="button"
              style={styles.btnGhost}
              onClick={() => onPage(page + 1)}
              disabled={page >= totalPages || loading}
            >
              next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Task 51: render the lifecycle status as a small pill. Colors lean on
// existing CSS variables — danger (red) for drafts to make "still hidden"
// pop, accent (theme color) for scheduled/in-flight, ok (green) for
// published. Unknown / null falls back to a neutral grey so the column
// never renders a blank cell.
function statusLabel(status) {
  switch (status) {
    case 'published': return '已发布';
    case 'draft': return '草稿';
    case 'scheduled': return '计划';
    default: return status || '—';
  }
}

function statusPillStyle(status) {
  const base = {
    display: 'inline-block',
    padding: '2px 8px',
    fontSize: 10,
    borderRadius: 3,
    letterSpacing: '0.04em',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
  };
  if (status === 'published') {
    return {
      ...base,
      borderColor: 'color-mix(in oklab, var(--ok, #2b8a3e) 60%, transparent)',
      color: 'var(--ok, #2b8a3e)',
    };
  }
  if (status === 'draft') {
    return {
      ...base,
      borderColor: 'color-mix(in oklab, var(--danger) 50%, transparent)',
      color: 'var(--danger)',
    };
  }
  if (status === 'scheduled') {
    return {
      ...base,
      borderColor: 'color-mix(in oklab, var(--accent, #2563eb) 60%, transparent)',
      color: 'var(--accent, var(--fg-2))',
    };
  }
  return base;
}

const styles = {
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: 18,
    gap: 12,
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
  toolRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
    gap: 12,
  },
  chips: { display: 'flex', gap: 6 },
  chip: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    padding: '4px 12px',
    borderRadius: 999,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
    letterSpacing: '0.04em',
  },
  chipActive: {
    color: 'var(--fg)',
    borderColor: 'color-mix(in oklab, var(--accent) 50%, transparent)',
    background: 'color-mix(in oklab, var(--accent) 14%, transparent)',
  },
  search: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg)',
    padding: '6px 10px',
    fontFamily: 'inherit',
    fontSize: 12,
    borderRadius: 4,
    minWidth: 220,
  },
  tableWrap: {
    border: '1px solid var(--line)',
    borderRadius: 6,
    overflow: 'hidden',
    background: 'var(--bg-2)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 12,
  },
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
  tr: {
    borderBottom: '1px solid var(--line)',
  },
  trFocused: {
    background: 'color-mix(in oklab, var(--accent) 12%, transparent)',
    boxShadow: 'inset 3px 0 0 var(--accent)',
  },
  td: {
    padding: '10px 12px',
    color: 'var(--fg-2)',
    verticalAlign: 'top',
  },
  tdN: {
    padding: '10px 12px',
    color: 'var(--accent)',
    fontVariantNumeric: 'tabular-nums',
    verticalAlign: 'top',
    width: 60,
  },
  tdTitle: {
    padding: '10px 12px',
    verticalAlign: 'top',
    minWidth: 240,
  },
  title: { color: 'var(--fg)', fontWeight: 500 },
  subtitle: { color: 'var(--fg-3)', fontSize: 11, marginTop: 2 },
  kbdHint: {
    fontSize: 11, color: 'var(--fg-4)',
    margin: '0 0 8px', display: 'flex', gap: 6, alignItems: 'center',
  },
  kbd: {
    fontFamily: 'inherit',
    border: '1px solid var(--line-2)', borderRadius: 3,
    padding: '0 6px', fontSize: 10, color: 'var(--fg-3)',
  },
  idHint: { color: 'var(--fg-4)', fontSize: 10, marginTop: 4, display: 'inline-flex', alignItems: 'center', gap: 4 },
  idCopyBtn: {
    background: 'transparent', border: 0, color: 'var(--fg-4)',
    fontSize: 11, padding: '0 4px', cursor: 'pointer', borderRadius: 3,
    fontFamily: 'inherit',
  },
  tagPill: {
    display: 'inline-block',
    padding: '2px 8px',
    fontSize: 10,
    borderRadius: 3,
    border: '1px solid var(--line-2)',
    color: 'var(--fg-3)',
    letterSpacing: '0.04em',
  },
  empty: {
    padding: '40px 12px',
    textAlign: 'center',
    color: 'var(--fg-4)',
    fontSize: 12,
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
  btnGhostLink: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '4px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontFamily: 'inherit',
    cursor: 'pointer',
    marginRight: 6,
    textDecoration: 'none',
    display: 'inline-block',
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
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '10px 12px',
    borderRadius: 4,
    marginBottom: 14,
  },
  pager: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 14,
    fontSize: 11,
    color: 'var(--fg-3)',
  },
  pagerInfo: { letterSpacing: '0.04em' },
  pagerControls: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  pagerLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 11,
    color: 'var(--fg-3)',
    marginRight: 6,
  },
  pagerSelect: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    fontSize: 11,
    fontFamily: 'inherit',
    padding: '3px 6px',
    borderRadius: 4,
  },
  dim: { color: 'var(--fg-4)' },
};

// Task 42: download every post as a tar archive — backup / migration tool.
// Pairs with the bulk-upload import; archive entries round-trip through
// /posts/upload exactly.
function ExportTarButton() {
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  async function onClick() {
    setBusy(true);
    try {
      const { filename } = await postsApi.downloadTar();
      toast.success(`已导出 ${filename}`);
    } catch (e) {
      toast.error(`导出失败：${e?.detail || e?.message || '未知错误'}`);
    } finally {
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      style={styles.btnGhost}
      onClick={onClick}
      disabled={busy}
      data-testid="posts-export-tar"
    >
      {busy ? '导出中…' : '导出 tar'}
    </button>
  );
}

// Task 30: bulk upload of .md files. Drag-drop or file picker; per-file
// row with status icon. Posts the multipart batch via postsApi.bulkUpload
// and renders the structured response (which contains per-file ok/error).
function BulkUploadModal({ onClose, onDone }) {
  const [files, setFiles] = useState([]);
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [overwrite, setOverwrite] = useState(false);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  function pickFiles(list) {
    const accepted = Array.from(list || [])
      .filter((f) => /\.(md|markdown)$/i.test(f.name))
      .slice(0, 20);
    setFiles(accepted);
    setResults(null);
  }

  async function onUpload() {
    if (!files.length) return;
    setBusy(true);
    try {
      const res = await postsApi.bulkUpload(files, { overwrite });
      setResults(res);
    } catch (err) {
      setResults({
        results: files.map((f) => ({
          file: f.name,
          ok: false,
          detail: err?.detail || err?.message || '上传失败',
        })),
        summary: { total: files.length, ok: 0, failed: files.length },
      });
    } finally {
      setBusy(false);
    }
  }

  function close() {
    if (results && results.summary?.ok > 0) onDone?.();
    else onClose?.();
  }

  return (
    <div
      className="palette-bg"
      data-testid="bulk-upload-modal"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div
        style={bulkStyles.shell}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <header style={bulkStyles.head}>
          <span style={bulkStyles.title}>批量导入文章</span>
          <button type="button" onClick={close} style={bulkStyles.closeBtn} aria-label="关闭">×</button>
        </header>
        <div style={bulkStyles.body}>
          <div
            style={{ ...bulkStyles.drop, ...(drag ? bulkStyles.dropActive : null) }}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              pickFiles(e.dataTransfer.files);
            }}
            onClick={() => inputRef.current?.click()}
            data-testid="bulk-upload-drop"
          >
            {files.length === 0
              ? '拖入 .md 文件,或点此选择(最多 20 个)'
              : `已选 ${files.length} 个文件`}
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".md,.markdown"
              onChange={(e) => pickFiles(e.target.files)}
              style={{ display: 'none' }}
            />
          </div>

          {files.length > 0 && (
            <ul style={bulkStyles.fileList} data-testid="bulk-upload-files">
              {files.map((f, i) => {
                const r = results?.results?.find((x) => x.file === f.name);
                return (
                  <li
                    key={`${f.name}-${i}`}
                    style={{
                      ...bulkStyles.fileRow,
                      ...(r ? (r.ok ? bulkStyles.fileOk : bulkStyles.fileErr) : null),
                    }}
                    data-testid={`bulk-file-${i}`}
                    data-status={r ? (r.ok ? 'ok' : 'err') : 'pending'}
                  >
                    <span style={bulkStyles.fileIcon}>
                      {r ? (r.ok ? '✓' : '!') : '·'}
                    </span>
                    <span style={bulkStyles.fileName}>{f.name}</span>
                    <span style={bulkStyles.fileMeta}>
                      {r
                        ? r.ok
                          ? `→ ${r.post?.id}`
                          : (r.detail || `HTTP ${r.status}`)
                        : `${(f.size / 1024).toFixed(1)} KB`}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}

          <label style={bulkStyles.opt}>
            <input
              type="checkbox"
              checked={overwrite}
              onChange={(e) => setOverwrite(e.target.checked)}
            />
            <span>遇到同名 id 时覆盖(否则报 already exists)</span>
          </label>

          {results && (
            <div style={bulkStyles.summary} data-testid="bulk-upload-summary">
              共 {results.summary.total} 个 · 成功 {results.summary.ok} · 失败 {results.summary.failed}
            </div>
          )}
        </div>
        <footer style={bulkStyles.foot}>
          <button type="button" onClick={close} style={styles.btnGhost}>
            {results && results.summary.ok > 0 ? '完成' : '取消'}
          </button>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            onClick={onUpload}
            disabled={busy || !files.length || (results && results.summary.failed === 0)}
            style={styles.btnPrimary}
            data-testid="bulk-upload-submit"
          >
            {busy ? '上传中…' : '开始上传'}
          </button>
        </footer>
      </div>
    </div>
  );
}

const bulkStyles = {
  shell: {
    width: 'min(640px, 92vw)',
    maxHeight: '82vh',
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    borderRadius: 10,
    boxShadow: '0 20px 80px rgba(0,0,0,0.6)',
    display: 'flex',
    flexDirection: 'column',
    fontFamily: "'JetBrains Mono', monospace",
  },
  head: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid var(--line)',
  },
  title: { fontSize: 13, fontWeight: 600, color: 'var(--fg)' },
  closeBtn: {
    background: 'transparent', border: 0, fontSize: 18, color: 'var(--fg-3)',
    cursor: 'pointer', padding: 0, width: 22, height: 22, lineHeight: 1,
  },
  body: { padding: 16, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 10 },
  drop: {
    border: '1px dashed var(--line-2)',
    borderRadius: 6,
    padding: '24px 16px',
    textAlign: 'center',
    color: 'var(--fg-3)',
    fontSize: 12,
    cursor: 'pointer',
    background: 'var(--bg)',
  },
  dropActive: {
    borderColor: 'var(--accent)',
    color: 'var(--fg)',
    background: 'color-mix(in oklab, var(--accent) 8%, transparent)',
  },
  fileList: {
    listStyle: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    maxHeight: 240,
    overflow: 'auto',
  },
  fileRow: {
    display: 'grid',
    gridTemplateColumns: '20px 1fr auto',
    gap: 8,
    alignItems: 'center',
    padding: '6px 10px',
    border: '1px solid var(--line)',
    borderRadius: 4,
    fontSize: 12,
    color: 'var(--fg-2)',
  },
  fileOk: {
    borderColor: 'color-mix(in oklab, var(--accent) 50%, var(--line))',
    background: 'color-mix(in oklab, var(--accent) 6%, transparent)',
  },
  fileErr: {
    borderColor: 'var(--danger, #c44)',
    background: 'color-mix(in oklab, var(--danger, #c44) 6%, transparent)',
  },
  fileIcon: { color: 'var(--accent)', fontWeight: 600, textAlign: 'center' },
  fileName: { fontFamily: 'JetBrains Mono, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  fileMeta: { color: 'var(--fg-4)', fontSize: 11 },
  opt: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--fg-3)' },
  summary: {
    fontSize: 12,
    color: 'var(--fg-2)',
    padding: '8px 12px',
    background: 'var(--bg-3)',
    borderRadius: 4,
  },
  foot: {
    display: 'flex',
    gap: 8,
    padding: '12px 16px',
    borderTop: '1px solid var(--line)',
    background: 'var(--bg-3)',
  },
};
