import { useEffect, useState } from 'react';
import { apiTokens } from '../../api/apiTokens.js';
import { useConfirm } from '../ui/UIProvider.jsx';

export default function ApiTokens() {
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [name, setName] = useState('');
  const [scope, setScope] = useState('read');
  const [creating, setCreating] = useState(false);

  const [secret, setSecret] = useState(null); // ApiTokenCreateResponse on success
  const [revokingId, setRevokingId] = useState(null);
  const [usageOpenId, setUsageOpenId] = useState(null); // id of expanded usage row
  const [usageRows, setUsageRows] = useState({});       // id → list[ApiTokenUsageItem] | null while loading
  const [usageError, setUsageError] = useState({});      // id → string (error detail)
  const confirm = useConfirm();

  async function refresh() {
    setLoading(true);
    try {
      const list = await apiTokens.list();
      setRows(list);
      setError(null);
    } catch (err) {
      setError(err?.detail || err?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    apiTokens
      .list()
      .then((list) => {
        if (!mounted) return;
        setRows(list);
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

  async function onCreate(e) {
    e.preventDefault();
    setError(null);
    setCreating(true);
    try {
      const res = await apiTokens.create({ name: name.trim(), scope });
      setSecret(res);
      setName('');
      setScope('read');
      await refresh();
    } catch (err) {
      setError(err?.detail || err?.message || 'create failed');
    } finally {
      setCreating(false);
    }
  }

  async function toggleUsage(id) {
    if (usageOpenId === id) {
      setUsageOpenId(null);
      return;
    }
    setUsageOpenId(id);
    if (usageRows[id]) return; // cached
    setUsageRows((prev) => ({ ...prev, [id]: null }));
    setUsageError((prev) => ({ ...prev, [id]: null }));
    try {
      const list = await apiTokens.usage(id, 50);
      setUsageRows((prev) => ({ ...prev, [id]: list }));
    } catch (err) {
      setUsageError((prev) => ({
        ...prev,
        [id]: err?.detail || err?.message || 'failed to load usage',
      }));
      setUsageRows((prev) => ({ ...prev, [id]: [] }));
    }
  }

  async function onRevoke(id) {
    const ok = await confirm({
      title: '吊销 token',
      message: `确定吊销 token #${id} 吗？此操作不可撤销。`,
      confirmLabel: '吊销',
      destructive: true,
    });
    if (!ok) return;
    setRevokingId(id);
    setError(null);
    try {
      await apiTokens.remove(id);
      await refresh();
    } catch (err) {
      setError(err?.detail || err?.message || 'revoke failed');
    } finally {
      setRevokingId(null);
    }
  }

  return (
    <div>
      <section style={styles.card}>
        <div style={styles.cardHead}>
          <div style={styles.cardTitle}>Existing tokens</div>
        </div>
        <div style={styles.cardBody}>
          {loading && <div style={styles.muted}>loading…</div>}
          {error && !loading && <div style={styles.error}>error: {error}</div>}
          {!loading && rows && rows.length === 0 && (
            <div style={styles.muted}>no tokens yet.</div>
          )}
          {!loading && rows && rows.length > 0 && (
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>名称</th>
                  <th style={styles.th}>权限</th>
                  <th style={styles.th}>创建时间</th>
                  <th style={styles.th}>最近使用</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>调用次数</th>
                  <th style={styles.th}>状态</th>
                  <th style={styles.th} />
                </tr>
              </thead>
              <tbody>
                {rows.flatMap((t) => {
                  const revoked = Boolean(t.revoked_at);
                  const isOpen = usageOpenId === t.id;
                  const usageList = usageRows[t.id];
                  const tokenRow = (
                    <tr key={`row-${t.id}`}>
                      <td style={styles.td}>{t.name}</td>
                      <td style={styles.td}>
                        <span style={{ ...styles.badge, ...(t.scope === 'write' ? styles.badgeWrite : styles.badgeRead) }}>
                          {t.scope}
                        </span>
                      </td>
                      <td style={styles.td}>{fmtDate(t.created_at)}</td>
                      <td style={styles.td}>{t.last_used_at ? fmtDate(t.last_used_at) : '—'}</td>
                      <td
                        style={{ ...styles.td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}
                        data-testid={`api-token-usage-${t.id}`}
                      >
                        {Number(t.usage_count || 0).toLocaleString()}
                      </td>
                      <td style={styles.td}>
                        {revoked ? (
                          <span style={{ color: 'var(--fg-4)' }}>已吊销</span>
                        ) : (
                          <span style={{ color: 'var(--accent)' }}>活动</span>
                        )}
                      </td>
                      <td style={{ ...styles.td, textAlign: 'right' }}>
                        <button
                          type="button"
                          onClick={() => toggleUsage(t.id)}
                          style={styles.btnSecondary}
                          data-testid={`api-token-usage-toggle-${t.id}`}
                          aria-expanded={isOpen}
                        >
                          {isOpen ? '收起' : '查看记录'}
                        </button>
                        {!revoked && (
                          <button
                            type="button"
                            onClick={() => onRevoke(t.id)}
                            disabled={revokingId === t.id}
                            style={{ ...styles.btnDanger, marginLeft: 6 }}
                          >
                            {revokingId === t.id ? 'revoking…' : 'revoke'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                  if (!isOpen) return [tokenRow];
                  return [
                    tokenRow,
                    <tr key={`usage-${t.id}`}>
                      <td colSpan={7} style={styles.usageCell} data-testid={`api-token-usage-panel-${t.id}`}>
                        {usageList === null && <div style={styles.muted}>loading…</div>}
                        {usageList && usageError[t.id] && (
                          <div style={styles.error}>{usageError[t.id]}</div>
                        )}
                        {usageList && !usageError[t.id] && usageList.length === 0 && (
                          <div style={styles.muted}>该 token 还没有任何调用记录。</div>
                        )}
                        {usageList && usageList.length > 0 && (
                          <table style={styles.usageTable}>
                            <thead>
                              <tr>
                                <th style={styles.th}>时间</th>
                                <th style={styles.th}>方法</th>
                                <th style={styles.th}>路径</th>
                              </tr>
                            </thead>
                            <tbody>
                              {usageList.map((u, i) => (
                                <tr key={i} data-testid={`api-token-usage-row-${t.id}-${i}`}>
                                  <td style={styles.td}>{fmtDate(u.used_at)}</td>
                                  <td style={styles.td}><code>{u.method}</code></td>
                                  <td style={styles.td}><code>{u.path}</code></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>,
                  ];
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section style={styles.card}>
        <div style={styles.cardHead}>
          <div style={styles.cardTitle}>+ create token</div>
        </div>
        <div style={styles.cardBody}>
          <form onSubmit={onCreate} style={styles.form} noValidate>
            <label style={styles.label}>
              <span style={styles.labelText}>name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="ci-deploy"
                style={styles.input}
                required
              />
            </label>
            <label style={styles.label}>
              <span style={styles.labelText}>scope</span>
              <select
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                style={styles.input}
              >
                <option value="read">read</option>
                <option value="write">write</option>
              </select>
            </label>
            <div style={styles.actions}>
              <button type="submit" disabled={creating || !name.trim()} style={styles.btnPrimary}>
                {creating ? 'creating…' : 'create'}
              </button>
            </div>
          </form>
        </div>
      </section>

      {secret && <SecretModal secret={secret} onClose={() => setSecret(null)} />}
    </div>
  );
}

function SecretModal({ secret, onClose }) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(secret.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard might be unavailable in non-https — user can copy manually */
    }
  }

  return (
    <div style={styles.modalShell} role="dialog" aria-modal="true">
      <div style={styles.modal}>
        <div style={styles.modalHead}>
          <span style={styles.modalTitle}>Token created</span>
          <button type="button" onClick={onClose} style={styles.modalClose}>
            ×
          </button>
        </div>
        <div style={styles.modalBody}>
          <div style={styles.warn}>
            ! This is the ONLY time the secret will be shown. Copy it now.
          </div>
          <div style={styles.kv}>
            <span style={styles.kvKey}>name</span>
            <span style={styles.kvVal}>{secret.name}</span>
          </div>
          <div style={styles.kv}>
            <span style={styles.kvKey}>scope</span>
            <span style={styles.kvVal}>{secret.scope}</span>
          </div>
          <div style={styles.tokenBox}>
            <code style={styles.tokenCode}>{secret.token}</code>
          </div>
          <div style={styles.actions}>
            <button type="button" onClick={onCopy} style={styles.btnPrimary}>
              {copied ? 'copied ✓' : 'copy token'}
            </button>
            <button type="button" onClick={onClose} style={styles.btnSecondary}>
              done
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

const styles = {
  card: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '14px 16px',
    marginBottom: 14,
  },
  cardHead: {
    display: 'flex',
    alignItems: 'center',
    paddingBottom: 8,
    marginBottom: 10,
    borderBottom: '1px dashed var(--line)',
  },
  cardTitle: { fontSize: 13, color: 'var(--fg)', fontWeight: 600 },
  cardBody: {},
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
  badge: {
    fontSize: 10,
    padding: '2px 6px',
    borderRadius: 3,
    border: '1px solid var(--line-2)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  badgeRead: {
    color: 'var(--fg-3)',
  },
  badgeWrite: {
    color: 'var(--accent)',
    borderColor: 'color-mix(in oklab, var(--accent) 40%, transparent)',
  },
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
  actions: { display: 'flex', gap: 8, marginTop: 4 },
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
    background: 'transparent',
    color: 'var(--danger)',
    border: '1px solid var(--danger)',
    padding: '5px 10px',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 11,
    fontFamily: 'inherit',
  },
  muted: { color: 'var(--fg-3)', fontSize: 12 },
  usageCell: {
    background: 'var(--bg)',
    borderBottom: '1px solid var(--line)',
    padding: '8px 12px',
  },
  usageTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 11,
    color: 'var(--fg-2)',
  },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '8px 10px',
    borderRadius: 4,
  },
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
    border: '1px solid var(--accent)',
    borderRadius: 6,
    width: '100%',
    maxWidth: 520,
    boxShadow: '0 0 24px var(--accent-glow)',
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
    gap: 10,
    padding: '14px',
  },
  warn: {
    fontSize: 11,
    color: '#0a0b0d',
    background: 'var(--accent)',
    padding: '8px 10px',
    borderRadius: 4,
    fontWeight: 600,
  },
  kv: { display: 'flex', gap: 10, fontSize: 11 },
  kvKey: { color: 'var(--fg-4)', width: 60 },
  kvVal: { color: 'var(--fg-2)' },
  tokenBox: {
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 4,
    padding: '10px 12px',
    overflowX: 'auto',
  },
  tokenCode: {
    fontFamily: 'inherit',
    fontSize: 12,
    color: 'var(--accent)',
    wordBreak: 'break-all',
    whiteSpace: 'pre-wrap',
  },
};
