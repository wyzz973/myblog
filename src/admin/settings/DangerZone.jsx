import { useEffect, useRef, useState } from 'react';
import { apiDanger } from '../../api/danger.js';

export default function DangerZone() {
  const [status, setStatus] = useState(null);
  const [statusErr, setStatusErr] = useState(null);
  const [statusLoading, setStatusLoading] = useState(true);

  async function refreshStatus() {
    try {
      const s = await apiDanger.status();
      setStatus(s);
      setStatusErr(null);
    } catch (err) {
      setStatusErr(err?.detail || err?.message || 'failed to load status');
    } finally {
      setStatusLoading(false);
    }
  }

  useEffect(() => {
    refreshStatus();
  }, []);

  return (
    <div style={styles.shell}>
      <header style={styles.banner}>
        <span style={styles.bannerDot} />
        <div>
          <div style={styles.bannerTitle}>Danger Zone</div>
          <div style={styles.bannerSub}>
            Destructive actions. Most operations require your account password and
            are rate-limited (1/hour by IP).
          </div>
        </div>
      </header>

      {statusLoading && <div style={styles.muted}>loading status…</div>}
      {statusErr && !statusLoading && (
        <div style={styles.error}>error: {statusErr}</div>
      )}

      <ExportSection />
      <ImportSection />
      <DeleteSection
        status={status}
        onChange={refreshStatus}
      />
    </div>
  );
}

// --- Export ------------------------------------------------------------------

function ExportSection() {
  const [jobs, setJobs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [password, setPassword] = useState('');
  const [requesting, setRequesting] = useState(false);

  // Active job we're polling
  const [activeId, setActiveId] = useState(null);
  const pollRef = useRef(null);

  async function refresh() {
    try {
      const list = await apiDanger.listExports();
      setJobs(list);
      setError(null);
    } catch (err) {
      setError(err?.detail || err?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  function startPoll(jobId) {
    if (pollRef.current) clearInterval(pollRef.current);
    setActiveId(jobId);
    pollRef.current = setInterval(async () => {
      try {
        const r = await apiDanger.getExport(jobId);
        setJobs((prev) => {
          if (!prev) return prev;
          const idx = prev.findIndex((j) => j.id === jobId);
          if (idx === -1) return [r, ...prev];
          const next = prev.slice();
          next[idx] = r;
          return next;
        });
        if (r.status === 'done' || r.status === 'failed') {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setActiveId(null);
        }
      } catch {
        /* keep polling — transient errors recover */
      }
    }, 2000);
  }

  async function onRequest(e) {
    e.preventDefault();
    setError(null);
    setRequesting(true);
    try {
      const res = await apiDanger.requestExport(password);
      setPassword('');
      await refresh();
      if (res?.job_id) startPoll(res.job_id);
    } catch (err) {
      setError(err?.detail || err?.message || 'export failed');
    } finally {
      setRequesting(false);
    }
  }

  async function onDownload(jobId) {
    try {
      const blob = await apiDanger.downloadExport(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `myblog-export-${jobId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err?.detail || err?.message || 'download failed');
    }
  }

  return (
    <Section title="Export site" subtitle="Build a zip snapshot of all data">
      <form onSubmit={onRequest} style={styles.form} noValidate>
        <label style={styles.label}>
          <span style={styles.labelText}>account password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            style={styles.input}
            autoComplete="current-password"
            required
          />
        </label>
        <div style={styles.actions}>
          <button
            type="submit"
            disabled={requesting || !password}
            style={styles.btnDanger}
          >
            {requesting ? 'requesting…' : 'request export'}
          </button>
        </div>
        {error && <div style={styles.error}>! {error}</div>}
      </form>

      <div style={styles.subTitle}>Recent jobs</div>
      {loading && <div style={styles.muted}>loading…</div>}
      {!loading && (!jobs || jobs.length === 0) && (
        <div style={styles.muted}>no exports yet.</div>
      )}
      {!loading && jobs && jobs.length > 0 && (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>id</th>
              <th style={styles.th}>status</th>
              <th style={styles.th}>requested</th>
              <th style={styles.th}>completed</th>
              <th style={styles.th}>size</th>
              <th style={styles.th} />
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.id}>
                <td style={styles.td}>
                  <code style={styles.codeId} title={j.id}>{j.id.slice(0, 10)}…</code>
                </td>
                <td style={styles.td}>
                  <StatusPill status={j.status} polling={activeId === j.id} />
                </td>
                <td style={styles.td}>{fmtDate(j.created_at)}</td>
                <td style={styles.td}>{j.completed_at ? fmtDate(j.completed_at) : '—'}</td>
                <td style={styles.td}>{j.file_size ? fmtBytes(j.file_size) : '—'}</td>
                <td style={{ ...styles.td, textAlign: 'right' }}>
                  {j.status === 'done' && (
                    <button
                      type="button"
                      onClick={() => onDownload(j.id)}
                      style={styles.btnSecondary}
                    >
                      download
                    </button>
                  )}
                  {j.status === 'failed' && j.error && (
                    <span style={{ color: 'var(--danger)', fontSize: 11 }} title={j.error}>
                      failed
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  );
}

// --- Import ------------------------------------------------------------------

function ImportSection() {
  const [file, setFile] = useState(null);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function actuallyImport() {
    setConfirmOpen(false);
    setError(null);
    setBusy(true);
    try {
      const res = await apiDanger.importSite({ file, password });
      setResult(res);
      setFile(null);
      setPassword('');
    } catch (err) {
      setError(err?.detail || err?.message || 'import failed');
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    if (!file || !password) return;
    setConfirmOpen(true);
  }

  return (
    <Section title="Import site" subtitle="Restore from a zip export — REPLACES current data">
      <form onSubmit={onSubmit} style={styles.form} noValidate>
        <label style={styles.label}>
          <span style={styles.labelText}>export zip</span>
          <input
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            style={styles.fileInput}
            required
          />
        </label>
        <label style={styles.label}>
          <span style={styles.labelText}>account password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            style={styles.input}
            autoComplete="current-password"
            required
          />
        </label>
        <div style={styles.actions}>
          <button
            type="submit"
            disabled={busy || !file || !password}
            style={styles.btnDanger}
          >
            {busy ? 'importing…' : 'import zip'}
          </button>
        </div>
        {error && <div style={styles.error}>! {error}</div>}
        {result && (
          <div style={styles.notice}>
            Import complete — {result.tables_imported} tables, {result.posts_imported} posts,{' '}
            {result.media_imported} media items.
          </div>
        )}
      </form>

      {confirmOpen && (
        <ConfirmModal
          title="Confirm import"
          body="This will replace ALL existing site data with the contents of the zip. This cannot be undone. Proceed?"
          confirmLabel="yes, replace site"
          onConfirm={actuallyImport}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </Section>
  );
}

// --- Delete Site -------------------------------------------------------------

function DeleteSection({ status, onChange }) {
  const [password, setPassword] = useState('');
  const [handle, setHandle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);

  const pendingAt = status?.pending_delete_at;
  const daysRem = status?.days_remaining;

  async function actuallyDelete() {
    setConfirmOpen(false);
    setError(null);
    setBusy(true);
    try {
      await apiDanger.scheduleDelete({ password, handle: handle.trim() });
      setPassword('');
      setHandle('');
      await onChange();
    } catch (err) {
      setError(err?.detail || err?.message || 'delete failed');
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    if (!password || !handle.trim()) return;
    setConfirmOpen(true);
  }

  async function onCancel() {
    setError(null);
    setCancelBusy(true);
    try {
      await apiDanger.cancelDelete();
      await onChange();
    } catch (err) {
      setError(err?.detail || err?.message || 'cancel failed');
    } finally {
      setCancelBusy(false);
    }
  }

  if (pendingAt) {
    return (
      <Section
        title="Delete site"
        subtitle="Site deletion is currently scheduled"
        critical
      >
        <div style={styles.scheduledBox}>
          <div style={styles.scheduledTitle}>! Site deletion scheduled</div>
          <div style={styles.scheduledMeta}>
            scheduled at: <span style={{ color: 'var(--fg)' }}>{fmtDate(pendingAt)}</span>
          </div>
          {daysRem != null && (
            <div style={styles.scheduledMeta}>
              days remaining: <span style={{ color: 'var(--accent)' }}>{daysRem}</span>
            </div>
          )}
          <div style={styles.actions}>
            <button
              type="button"
              onClick={onCancel}
              disabled={cancelBusy}
              style={styles.btnPrimary}
            >
              {cancelBusy ? 'canceling…' : 'cancel deletion'}
            </button>
          </div>
          {error && <div style={styles.error}>! {error}</div>}
        </div>
      </Section>
    );
  }

  return (
    <Section
      title="Delete site"
      subtitle="Schedules permanent deletion after a 7-day grace period"
      critical
    >
      <form onSubmit={onSubmit} style={styles.form} noValidate>
        <label style={styles.label}>
          <span style={styles.labelText}>account password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            style={styles.input}
            autoComplete="current-password"
            required
          />
        </label>
        <label style={styles.label}>
          <span style={styles.labelText}>type your site handle to confirm</span>
          <input
            type="text"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            placeholder="my-site-handle"
            style={styles.input}
            required
          />
        </label>
        <div style={styles.actions}>
          <button
            type="submit"
            disabled={busy || !password || !handle.trim()}
            style={styles.btnDanger}
          >
            {busy ? 'scheduling…' : 'schedule deletion'}
          </button>
        </div>
        {error && <div style={styles.error}>! {error}</div>}
      </form>

      {confirmOpen && (
        <ConfirmModal
          title="Confirm site deletion"
          body={`Schedule deletion of "${handle}"? You'll have 7 days to cancel before data is permanently removed.`}
          confirmLabel="yes, schedule deletion"
          onConfirm={actuallyDelete}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </Section>
  );
}

// --- chrome -----------------------------------------------------------------

function Section({ title, subtitle, critical, children }) {
  return (
    <section
      style={{
        ...styles.card,
        ...(critical ? styles.cardCritical : null),
      }}
    >
      <div style={styles.cardHead}>
        <div style={{ ...styles.cardTitle, ...(critical ? { color: 'var(--danger)' } : null) }}>
          {title}
        </div>
        {subtitle && <div style={styles.cardSubtitle}>{subtitle}</div>}
      </div>
      <div style={styles.cardBody}>{children}</div>
    </section>
  );
}

function StatusPill({ status, polling }) {
  const palette = {
    pending: { bg: 'color-mix(in oklab, var(--fg-3) 20%, transparent)', fg: 'var(--fg-2)' },
    running: { bg: 'color-mix(in oklab, var(--accent) 20%, transparent)', fg: 'var(--accent)' },
    done: { bg: 'color-mix(in oklab, var(--accent) 30%, transparent)', fg: 'var(--accent)' },
    failed: { bg: 'color-mix(in oklab, var(--danger) 20%, transparent)', fg: 'var(--danger)' },
  };
  const c = palette[status] || palette.pending;
  return (
    <span
      style={{
        fontSize: 10,
        padding: '2px 8px',
        borderRadius: 999,
        background: c.bg,
        color: c.fg,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
        fontWeight: 600,
      }}
    >
      {status}{polling ? ' …' : ''}
    </span>
  );
}

function ConfirmModal({ title, body, confirmLabel, onConfirm, onCancel }) {
  return (
    <div style={styles.modalShell} role="dialog" aria-modal="true">
      <div style={styles.modal}>
        <div style={styles.modalHead}>
          <span style={styles.modalTitle}>{title}</span>
          <button type="button" onClick={onCancel} style={styles.modalClose}>×</button>
        </div>
        <div style={styles.modalBody}>
          <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>{body}</div>
          <div style={styles.actions}>
            <button type="button" onClick={onConfirm} style={styles.btnDanger}>
              {confirmLabel}
            </button>
            <button type="button" onClick={onCancel} style={styles.btnSecondary}>
              cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function fmtBytes(n) {
  if (n == null) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

const styles = {
  shell: { display: 'flex', flexDirection: 'column', gap: 14 },
  banner: {
    display: 'flex',
    gap: 12,
    alignItems: 'flex-start',
    padding: '12px 14px',
    border: '1px solid var(--danger)',
    borderRadius: 6,
    background: 'color-mix(in oklab, var(--danger) 8%, transparent)',
  },
  bannerDot: {
    width: 10,
    height: 10,
    borderRadius: 999,
    background: 'var(--danger)',
    boxShadow: '0 0 8px var(--danger)',
    marginTop: 4,
  },
  bannerTitle: {
    fontSize: 13,
    color: 'var(--danger)',
    fontWeight: 700,
    letterSpacing: '0.04em',
  },
  bannerSub: { fontSize: 11, color: 'var(--fg-3)', marginTop: 2 },

  card: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '14px 16px',
  },
  cardCritical: {
    borderColor: 'color-mix(in oklab, var(--danger) 50%, var(--line))',
  },
  cardHead: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 10,
    paddingBottom: 8,
    marginBottom: 10,
    borderBottom: '1px dashed var(--line)',
  },
  cardTitle: { fontSize: 14, color: 'var(--fg)', fontWeight: 600 },
  cardSubtitle: { fontSize: 11, color: 'var(--fg-4)' },
  cardBody: { display: 'flex', flexDirection: 'column', gap: 14 },

  form: { display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 360 },
  label: { display: 'flex', flexDirection: 'column', gap: 4 },
  labelText: {
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
  },
  fileInput: {
    background: 'var(--bg)',
    border: '1px solid var(--line-2)',
    color: 'var(--fg-2)',
    padding: '6px 8px',
    fontFamily: 'inherit',
    fontSize: 11,
    borderRadius: 4,
  },
  actions: { display: 'flex', gap: 8 },
  btnPrimary: {
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '7px 12px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    letterSpacing: '0.04em',
  },
  btnSecondary: {
    background: 'transparent',
    color: 'var(--fg-2)',
    padding: '7px 12px',
    border: '1px solid var(--line-2)',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
  },
  btnDanger: {
    background: 'var(--danger)',
    color: '#fff',
    padding: '7px 12px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
    fontWeight: 600,
    letterSpacing: '0.04em',
  },
  subTitle: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
    marginTop: 4,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 12,
    color: 'var(--fg-2)',
  },
  th: {
    textAlign: 'left',
    padding: '6px 8px',
    fontSize: 10,
    color: 'var(--fg-4)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
    borderBottom: '1px solid var(--line)',
    fontWeight: 500,
  },
  td: {
    padding: '8px',
    borderBottom: '1px solid var(--line)',
    fontVariantNumeric: 'tabular-nums',
  },
  codeId: {
    fontFamily: 'inherit',
    fontSize: 11,
    color: 'var(--fg-3)',
  },
  scheduledBox: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: 12,
    border: '1px solid var(--danger)',
    borderRadius: 4,
    background: 'color-mix(in oklab, var(--danger) 10%, transparent)',
  },
  scheduledTitle: {
    fontSize: 13,
    color: 'var(--danger)',
    fontWeight: 600,
  },
  scheduledMeta: { fontSize: 11, color: 'var(--fg-3)' },

  notice: {
    fontSize: 11,
    color: 'var(--accent)',
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    background: 'color-mix(in oklab, var(--accent) 10%, transparent)',
    padding: '6px 10px',
    borderRadius: 4,
  },
  error: {
    color: 'var(--danger)',
    fontSize: 11,
    border: '1px solid var(--danger)',
    padding: '6px 10px',
    borderRadius: 4,
    background: 'color-mix(in oklab, var(--danger) 10%, transparent)',
  },
  muted: { color: 'var(--fg-3)', fontSize: 12 },

  modalShell: {
    position: 'fixed',
    inset: 0,
    background: 'color-mix(in oklab, #000 70%, transparent)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    zIndex: 50,
  },
  modal: {
    background: 'var(--bg-2)',
    border: '1px solid var(--danger)',
    borderRadius: 6,
    width: '100%',
    maxWidth: 480,
    boxShadow: '0 0 24px color-mix(in oklab, var(--danger) 60%, transparent)',
  },
  modalHead: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 14px',
    borderBottom: '1px solid var(--line)',
  },
  modalTitle: { fontSize: 13, color: 'var(--fg)', fontWeight: 600 },
  modalClose: {
    background: 'transparent',
    border: 0,
    color: 'var(--fg-3)',
    fontSize: 18,
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  modalBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    padding: 14,
  },
};
