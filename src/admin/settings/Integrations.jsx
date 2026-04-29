import { useEffect, useState } from 'react';
import { apiIntegrations } from '../../api/integrations.js';

export default function Integrations() {
  return (
    <div style={styles.grid}>
      <GithubCard />
      <AnthropicCard />
    </div>
  );
}

function GithubCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState(null);

  const [username, setUsername] = useState('');
  const [token, setToken] = useState('');

  useEffect(() => {
    let mounted = true;
    apiIntegrations
      .getGithub()
      .then((res) => {
        if (!mounted) return;
        setData(res);
        setUsername(res?.username || '');
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

  async function onSave(e) {
    e.preventDefault();
    setNotice(null);
    setError(null);
    setSaving(true);
    try {
      const res = await apiIntegrations.putGithub({
        username: username.trim(),
        token,
      });
      setData(res);
      setToken('');
      setNotice('Saved + first sync triggered.');
    } catch (err) {
      setError(err?.detail || err?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }

  async function onSync() {
    setNotice(null);
    setError(null);
    setSyncing(true);
    try {
      await apiIntegrations.syncGithub();
      const fresh = await apiIntegrations.getGithub();
      setData(fresh);
      setNotice('Sync complete.');
    } catch (err) {
      setError(err?.detail || err?.message || 'sync failed');
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Card title="GitHub" subtitle="contribution graph + repos">
      {loading && <div style={styles.muted}>loading…</div>}
      {!loading && (
        <>
          <StatusRow
            connected={Boolean(data?.username)}
            status={data?.last_status}
            lastAt={data?.last_synced_at}
            error={data?.last_error}
          />
          <form onSubmit={onSave} style={styles.form} noValidate>
            <label style={styles.label}>
              <span style={styles.labelText}>username</span>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="octocat"
                style={styles.input}
                required
              />
            </label>
            <label style={styles.label}>
              <span style={styles.labelText}>personal access token</span>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={data?.username ? '•••••••• (re-enter to update)' : 'ghp_…'}
                style={styles.input}
                autoComplete="new-password"
                required
              />
            </label>
            {notice && <div style={styles.notice}>{notice}</div>}
            {error && <div style={styles.error}>! {error}</div>}
            <div style={styles.actions}>
              <button type="submit" disabled={saving || !token} style={styles.btnPrimary}>
                {saving ? 'saving…' : 'save'}
              </button>
              <button
                type="button"
                onClick={onSync}
                disabled={syncing || !data?.username}
                style={styles.btnSecondary}
              >
                {syncing ? 'syncing…' : 'sync now'}
              </button>
            </div>
          </form>
        </>
      )}
    </Card>
  );
}

function AnthropicCard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');

  useEffect(() => {
    let mounted = true;
    apiIntegrations
      .getAnthropic()
      .then((res) => {
        if (!mounted) return;
        setData(res);
        setModel(res?.model || '');
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

  async function onSave(e) {
    e.preventDefault();
    setNotice(null);
    setError(null);
    setSaving(true);
    try {
      const res = await apiIntegrations.putAnthropic({
        api_key: apiKey,
        model: model.trim() || null,
      });
      setData(res);
      setApiKey('');
      setNotice('Saved + verified.');
    } catch (err) {
      setError(err?.detail || err?.message || 'save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Anthropic" subtitle="LLM for Pet conversations">
      {loading && <div style={styles.muted}>loading…</div>}
      {!loading && (
        <>
          <StatusRow
            connected={Boolean(data?.model || data?.last_status === 'ok')}
            status={data?.last_status}
            error={data?.last_error}
          />
          <form onSubmit={onSave} style={styles.form} noValidate>
            <label style={styles.label}>
              <span style={styles.labelText}>api key</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={data?.model ? '•••••••• (re-enter to update)' : 'sk-ant-…'}
                style={styles.input}
                autoComplete="new-password"
                required
              />
            </label>
            <label style={styles.label}>
              <span style={styles.labelText}>model (optional)</span>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="claude-haiku-4-5-20251001"
                style={styles.input}
              />
            </label>
            {notice && <div style={styles.notice}>{notice}</div>}
            {error && <div style={styles.error}>! {error}</div>}
            <div style={styles.actions}>
              <button type="submit" disabled={saving || !apiKey} style={styles.btnPrimary}>
                {saving ? 'saving…' : 'save'}
              </button>
            </div>
          </form>
        </>
      )}
    </Card>
  );
}

function Card({ title, subtitle, children }) {
  return (
    <section style={styles.card}>
      <div style={styles.cardHead}>
        <div style={styles.cardTitle}>{title}</div>
        {subtitle && <div style={styles.cardSubtitle}>{subtitle}</div>}
      </div>
      <div style={styles.cardBody}>{children}</div>
    </section>
  );
}

function StatusRow({ connected, status, lastAt, error }) {
  const color = error
    ? 'var(--danger)'
    : connected
    ? 'var(--accent)'
    : 'var(--fg-4)';
  const label = error ? 'error' : connected ? 'connected' : 'not connected';
  return (
    <div style={styles.statusRow}>
      <span style={{ ...styles.statusDot, background: color, boxShadow: `0 0 6px ${color}` }} />
      <span style={{ color: 'var(--fg-2)' }}>{label}</span>
      {status && (
        <span style={styles.statusMeta}>
          status: <span style={{ color: 'var(--fg-2)' }}>{status}</span>
        </span>
      )}
      {lastAt && (
        <span style={styles.statusMeta}>
          last sync: <span style={{ color: 'var(--fg-2)' }}>{fmtDate(lastAt)}</span>
        </span>
      )}
      {error && <span style={styles.statusErr}>{error}</span>}
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
    gap: 14,
  },
  card: {
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    padding: '14px 16px',
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
  cardBody: { display: 'flex', flexDirection: 'column', gap: 12 },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap',
    fontSize: 11,
    color: 'var(--fg-3)',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
  },
  statusMeta: { color: 'var(--fg-4)' },
  statusErr: { color: 'var(--danger)' },
  form: { display: 'flex', flexDirection: 'column', gap: 10 },
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
};
