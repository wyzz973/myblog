import { useEffect, useState } from 'react';
import { apiIntegrations } from '../../api/integrations.js';

const PROVIDERS = [
  {
    name: 'zhipu',
    title: '智谱 AI',
    subtitle: '宠物对话备用模型',
    tokenPlaceholder: '请输入智谱 API Key',
    modelPlaceholder: 'glm-4-flash',
    modelRequired: false,
  },
  {
    name: 'qwen',
    title: '通义千问',
    subtitle: 'OpenAI 兼容模型',
    tokenPlaceholder: '请输入 DashScope API Key',
    modelPlaceholder: 'qwen-turbo',
    modelRequired: false,
  },
  {
    name: 'doubao',
    title: '豆包',
    subtitle: '火山方舟 Endpoint ID',
    tokenPlaceholder: '请输入火山方舟 API Key',
    modelPlaceholder: '请输入 Endpoint ID',
    modelRequired: true,
  },
  {
    name: 'deepseek',
    title: 'DeepSeek',
    subtitle: 'OpenAI 兼容模型',
    tokenPlaceholder: '请输入 DeepSeek API Key',
    modelPlaceholder: 'deepseek-v4-flash',
    modelRequired: false,
  },
];

export default function Integrations() {
  return (
    <div style={styles.grid}>
      <GithubCard />
      <AnthropicCard />
      {PROVIDERS.map((provider) => (
        <ProviderCard key={provider.name} provider={provider} />
      ))}
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
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  async function onTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiIntegrations.test('github', { username, token });
      setTestResult(res);
    } catch (err) {
      setTestResult({ ok: false, error: err?.detail || err?.message || '测试失败' });
    } finally {
      setTesting(false);
    }
  }

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
        setError(err?.detail || err?.message || '加载失败');
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
      setNotice('已保存，并已触发首次同步。');
    } catch (err) {
      setError(err?.detail || err?.message || '保存失败');
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
      setNotice('同步完成。');
    } catch (err) {
      setError(err?.detail || err?.message || '同步失败');
    } finally {
      setSyncing(false);
    }
  }

  return (
    <Card title="GitHub" subtitle="贡献图和仓库同步">
      {loading && <div style={styles.muted}>加载中...</div>}
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
              <span style={styles.labelText}>用户名</span>
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
              <span style={styles.labelText}>访问令牌</span>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={data?.username ? '已保存，重新输入可更新' : 'ghp_...'}
                style={styles.input}
                autoComplete="new-password"
                required
              />
            </label>
            {notice && <div style={styles.notice}>{notice}</div>}
            {error && <div style={styles.error}>! {error}</div>}
            {testResult && (
              <div
                style={testResult.ok ? styles.notice : styles.error}
                data-testid="test-github-result"
                data-ok={testResult.ok ? 'true' : 'false'}
              >
                {testResult.ok ? '✓ 连接正常' : `✗ ${testResult.error || '失败'}`}
              </div>
            )}
            <div style={styles.actions}>
              <button type="submit" disabled={saving || !token} style={styles.btnPrimary}>
                {saving ? '保存中...' : '保存'}
              </button>
              <button
                type="button"
                onClick={onTest}
                disabled={testing || !username || !token}
                style={styles.btnSecondary}
                data-testid="test-github"
              >
                {testing ? '测试中...' : '测试连接'}
              </button>
              <button
                type="button"
                onClick={onSync}
                disabled={syncing || !data?.username}
                style={styles.btnSecondary}
              >
                {syncing ? '同步中...' : '立即同步'}
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
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  async function onTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiIntegrations.test('anthropic', {
        api_key: apiKey,
        model: model.trim() || null,
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({ ok: false, error: err?.detail || err?.message || '测试失败' });
    } finally {
      setTesting(false);
    }
  }

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
        setError(err?.detail || err?.message || '加载失败');
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
      setNotice('已保存并验证通过。');
    } catch (err) {
      setError(err?.detail || err?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Anthropic" subtitle="宠物对话主模型">
      {loading && <div style={styles.muted}>加载中...</div>}
      {!loading && (
        <>
          <StatusRow
            connected={Boolean(data?.model || data?.last_status === 'ok')}
            status={data?.last_status}
            error={data?.last_error}
          />
          <form onSubmit={onSave} style={styles.form} noValidate>
            <label style={styles.label}>
              <span style={styles.labelText}>API Key</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={data?.model ? '已保存，重新输入可更新' : 'sk-ant-...'}
                style={styles.input}
                autoComplete="new-password"
                required
              />
            </label>
            <label style={styles.label}>
              <span style={styles.labelText}>模型（可选）</span>
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
            {testResult && (
              <div
                style={testResult.ok ? styles.notice : styles.error}
                data-testid="test-anthropic-result"
                data-ok={testResult.ok ? 'true' : 'false'}
              >
                {testResult.ok ? '✓ 连接正常' : `✗ ${testResult.error || '失败'}`}
              </div>
            )}
            <div style={styles.actions}>
              <button type="submit" disabled={saving || !apiKey} style={styles.btnPrimary}>
                {saving ? '保存中...' : '保存'}
              </button>
              <button
                type="button"
                onClick={onTest}
                disabled={testing || !apiKey}
                style={styles.btnSecondary}
                data-testid="test-anthropic"
              >
                {testing ? '测试中...' : '测试连接'}
              </button>
            </div>
          </form>
        </>
      )}
    </Card>
  );
}

function ProviderCard({ provider }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState(null);

  const [token, setToken] = useState('');
  const [model, setModel] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  async function onTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiIntegrations.test(provider.name, {
        token,
        model: model.trim() || null,
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({ ok: false, error: err?.detail || err?.message || '测试失败' });
    } finally {
      setTesting(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    apiIntegrations
      .getProvider(provider.name)
      .then((res) => {
        if (!mounted) return;
        setData(res);
        setModel(res?.model || '');
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.detail || err?.message || '加载失败');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [provider.name]);

  async function onSave(e) {
    e.preventDefault();
    setNotice(null);
    setError(null);
    setSaving(true);
    try {
      const res = await apiIntegrations.putProvider(provider.name, {
        token,
        model: model.trim() || null,
      });
      setData(res);
      setToken('');
      setModel(res?.model || model);
      setNotice('已保存并验证通过。');
    } catch (err) {
      setError(err?.detail || err?.message || '保存失败');
    } finally {
      setSaving(false);
    }
  }

  const missingRequiredModel = provider.modelRequired && !model.trim();

  return (
    <Card title={provider.title} subtitle={provider.subtitle}>
      {loading && <div style={styles.muted}>加载中...</div>}
      {!loading && (
        <>
          <StatusRow
            connected={Boolean(data?.configured)}
            status={data?.last_status}
            lastAt={data?.last_synced_at}
            error={data?.last_error}
          />
          <form onSubmit={onSave} style={styles.form} noValidate>
            <label style={styles.label}>
              <span style={styles.labelText}>API Key</span>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={data?.configured ? '已保存，重新输入可更新' : provider.tokenPlaceholder}
                style={styles.input}
                autoComplete="new-password"
                required
              />
            </label>
            <label style={styles.label}>
              <span style={styles.labelText}>{provider.modelRequired ? '模型 / Endpoint ID' : '模型（可选）'}</span>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={provider.modelPlaceholder}
                style={styles.input}
                required={provider.modelRequired}
              />
            </label>
            {provider.modelRequired && (
              <div style={styles.hint}>豆包需要填写火山方舟 Endpoint ID，不能使用默认模型。</div>
            )}
            {notice && <div style={styles.notice}>{notice}</div>}
            {error && <div style={styles.error}>! {error}</div>}
            {testResult && (
              <div
                style={testResult.ok ? styles.notice : styles.error}
                data-testid={`test-${provider.name}-result`}
                data-ok={testResult.ok ? 'true' : 'false'}
              >
                {testResult.ok ? '✓ 连接正常' : `✗ ${testResult.error || '失败'}`}
              </div>
            )}
            <div style={styles.actions}>
              <button
                type="submit"
                disabled={saving || !token || missingRequiredModel}
                style={styles.btnPrimary}
              >
                {saving ? '保存中...' : '保存并验证'}
              </button>
              <button
                type="button"
                onClick={onTest}
                disabled={testing || !token || missingRequiredModel}
                style={styles.btnSecondary}
                data-testid={`test-${provider.name}`}
              >
                {testing ? '测试中...' : '测试连接'}
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
  const label = error ? '异常' : connected ? '已配置' : '未配置';
  return (
    <div style={styles.statusRow}>
      <span style={{ ...styles.statusDot, background: color, boxShadow: `0 0 6px ${color}` }} />
      <span style={{ color: 'var(--fg-2)' }}>{label}</span>
      {status && (
        <span style={styles.statusMeta}>
          状态: <span style={{ color: 'var(--fg-2)' }}>{status}</span>
        </span>
      )}
      {lastAt && (
        <span style={styles.statusMeta}>
          上次同步: <span style={{ color: 'var(--fg-2)' }}>{fmtDate(lastAt)}</span>
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
  hint: { color: 'var(--fg-4)', fontSize: 11, lineHeight: 1.6 },
  muted: { color: 'var(--fg-3)', fontSize: 12 },
};
