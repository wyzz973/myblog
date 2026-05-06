import { useState } from 'react';
import { apiAccount } from '../../api/account.js';

export default function Account() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <TfaSection />
      <MagicLinkSection />
      <EmailSection />
      <PasswordSection />
    </div>
  );
}

// --- 2FA ---------------------------------------------------------------------

function TfaSection() {
  // Phases: idle → setup-pending (qr shown) → enabled (after enable) → disabling
  const [phase, setPhase] = useState('idle');
  const [setup, setSetup] = useState(null); // { secret, otpauth_uri, qr_svg }
  const [code, setCode] = useState('');
  const [recovery, setRecovery] = useState(null); // string[]
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Disable form
  const [disableCode, setDisableCode] = useState('');

  // Regenerate
  const [regenCode, setRegenCode] = useState('');

  async function onSetup() {
    setError(null);
    setBusy(true);
    try {
      const res = await apiAccount.setupTfa();
      setSetup(res);
      setPhase('setup-pending');
    } catch (err) {
      setError(err?.detail || err?.message || '设置失败');
    } finally {
      setBusy(false);
    }
  }

  async function onEnable(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await apiAccount.enableTfa(code.trim());
      setRecovery(res?.recovery_codes || []);
      setPhase('enabled');
      setCode('');
      setSetup(null);
    } catch (err) {
      setError(err?.detail || err?.message || '启用失败');
    } finally {
      setBusy(false);
    }
  }

  async function onDisable(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await apiAccount.disableTfa(disableCode.trim());
      setPhase('idle');
      setRecovery(null);
      setDisableCode('');
    } catch (err) {
      setError(err?.detail || err?.message || '停用失败');
    } finally {
      setBusy(false);
    }
  }

  async function onRegenerate(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await apiAccount.regenerateRecovery(regenCode.trim());
      setRecovery(res?.recovery_codes || []);
      setRegenCode('');
    } catch (err) {
      setError(err?.detail || err?.message || '重新生成失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="两步验证" subtitle="使用认证器应用生成 TOTP 验证码">
      {phase === 'idle' && (
        <div style={styles.row}>
          <span style={styles.muted}>当前账号未启用两步验证。</span>
          <button type="button" onClick={onSetup} disabled={busy} style={styles.btnPrimary}>
            {busy ? '启动中...' : '设置两步验证'}
          </button>
        </div>
      )}

      {phase === 'setup-pending' && setup && (
        <div style={styles.tfaSetup}>
          <div style={styles.qrShell}>
            {/* qr_svg is server-rendered SVG markup for the otpauth URI. */}
            <div
              style={styles.qrFrame}
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: setup.qr_svg }}
            />
          </div>
          <div style={styles.tfaSetupRight}>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              使用认证器扫描二维码，或手动输入下面的密钥：
            </div>
            <code style={styles.secretBox}>{setup.secret}</code>
            <form onSubmit={onEnable} style={styles.form} noValidate>
              <label style={styles.label}>
                <span style={styles.labelText}>6 位验证码</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="123456"
                  style={styles.input}
                  required
                />
              </label>
              {error && <div style={styles.error}>! {error}</div>}
              <div style={styles.actions}>
                <button type="submit" disabled={busy || code.length !== 6} style={styles.btnPrimary}>
                  {busy ? '验证中...' : '验证并启用'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPhase('idle');
                    setSetup(null);
                    setCode('');
                    setError(null);
                  }}
                  style={styles.btnSecondary}
                >
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {phase === 'enabled' && (
        <div style={styles.col}>
          <div style={styles.statusOk}>
            <span style={{ ...styles.statusDot, background: 'var(--accent)' }} />
            两步验证已启用。
          </div>

          {recovery && recovery.length > 0 && (
            <div style={styles.recoveryBox}>
              <div style={styles.warn}>
                请立即保存这些恢复码，每个恢复码只能使用一次。
              </div>
              <div style={styles.recoveryGrid}>
                {recovery.map((c) => (
                  <code key={c} style={styles.recoveryCode}>{c}</code>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setRecovery(null)}
                style={styles.btnSecondary}
              >
                隐藏
              </button>
            </div>
          )}

          <div style={styles.subSection}>
            <div style={styles.subTitle}>重新生成恢复码</div>
            <form onSubmit={onRegenerate} style={styles.form} noValidate>
              <label style={styles.label}>
                <span style={styles.labelText}>当前 6 位验证码</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  value={regenCode}
                  onChange={(e) => setRegenCode(e.target.value.replace(/\D/g, ''))}
                  style={styles.input}
                  required
                />
              </label>
              <div style={styles.actions}>
                <button
                  type="submit"
                  disabled={busy || regenCode.length !== 6}
                  style={styles.btnSecondary}
                >
                  {busy ? '处理中...' : '重新生成'}
                </button>
              </div>
            </form>
          </div>

          <div style={styles.subSection}>
            <div style={{ ...styles.subTitle, color: 'var(--danger)' }}>停用两步验证</div>
            <form onSubmit={onDisable} style={styles.form} noValidate>
              <label style={styles.label}>
                <span style={styles.labelText}>当前 6 位验证码</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  value={disableCode}
                  onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ''))}
                  style={styles.input}
                  required
                />
              </label>
              <div style={styles.actions}>
                <button
                  type="submit"
                  disabled={busy || disableCode.length !== 6}
                  style={styles.btnDanger}
                >
                  {busy ? '停用中...' : '停用两步验证'}
                </button>
              </div>
            </form>
          </div>
          {error && <div style={styles.error}>! {error}</div>}
        </div>
      )}
    </Card>
  );
}

// --- Magic link --------------------------------------------------------------

function MagicLinkSection() {
  const [enabled, setEnabled] = useState(null); // unknown until first toggle
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function onToggle(next) {
    setError(null);
    setBusy(true);
    try {
      const res = await apiAccount.setMagicLink(next);
      setEnabled(Boolean(res?.magic_link_enabled));
    } catch (err) {
      setError(err?.detail || err?.message || '切换失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="邮件登录链接" subtitle="发送一次性登录链接到邮箱">
      <div style={styles.row}>
        <span style={styles.muted}>
          {enabled === null
            ? '点击按钮更新偏好，后端状态为最终准则。'
            : enabled
            ? '邮件登录链接已启用。'
            : '邮件登录链接已停用。'}
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            disabled={busy}
            onClick={() => onToggle(true)}
            style={enabled === true ? styles.btnPrimary : styles.btnSecondary}
          >
            启用
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onToggle(false)}
            style={enabled === false ? styles.btnPrimary : styles.btnSecondary}
          >
            停用
          </button>
        </div>
      </div>
      {error && <div style={styles.error}>! {error}</div>}
    </Card>
  );
}

// --- Password ---------------------------------------------------------------

// Task 28b: rotate the admin login email. Direct write (no magic-link
// confirmation in this revision); on success we ask the owner to log in
// again because the JWT still claims the old email — the access token
// keeps working for now but new logins use the new address.
function EmailSection() {
  const [current, setCurrent] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [sentTo, setSentTo] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setSentTo(null);
    setBusy(true);
    try {
      // Task 28c: use the magic-link request flow. Backend mails a confirm
      // link to the new address; rotation only happens after the user
      // clicks it (validates they own the new mailbox).
      const res = await apiAccount.requestEmailChange(current, newEmail);
      setCurrent('');
      setSentTo(res?.to || newEmail);
      setNewEmail('');
    } catch (err) {
      setError(err?.detail || err?.message || '修改失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="登录邮箱" subtitle="修改用于后台登录的邮箱地址（通过新邮箱里的链接确认）">
      <form
        onSubmit={onSubmit}
        style={{ display: 'grid', gap: 10, maxWidth: 380 }}
        data-testid="email-change-form"
      >
        <label style={styles.label}>
          <span style={styles.labelText}>当前密码</span>
          <input
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            autoComplete="current-password"
            required
            style={styles.input}
            data-testid="email-change-current"
          />
        </label>
        <label style={styles.label}>
          <span style={styles.labelText}>新邮箱</span>
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            required
            style={styles.input}
            placeholder="new@example.com"
            data-testid="email-change-new"
          />
        </label>
        <div>
          <button
            type="submit"
            style={styles.btn}
            disabled={busy}
            data-testid="email-change-submit"
          >
            {busy ? '发送中...' : '发送确认邮件'}
          </button>
        </div>
        {sentTo && (
          <div style={styles.success} data-testid="email-change-sent">
            ✓ 已发送确认链接到 {sentTo}。15 分钟内点开链接才会真正切换邮箱；
            在那之前现有登录仍然可用。
          </div>
        )}
        {error && (
          <div style={styles.error} data-testid="email-change-error">
            ! {error}
          </div>
        )}
      </form>
    </Card>
  );
}

function PasswordSection() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setDone(false);
    if (next.length < 8) {
      setError('新密码至少需要 8 个字符');
      return;
    }
    if (next !== confirm) {
      setError('新密码和确认密码不一致');
      return;
    }
    if (next === current) {
      setError('新密码不能与当前密码相同');
      return;
    }
    setBusy(true);
    try {
      await apiAccount.changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      setDone(true);
    } catch (err) {
      setError(err?.detail || err?.message || '修改失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="密码" subtitle="修改当前账号密码">
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 10, maxWidth: 380 }}>
        <label style={styles.label}>
          <span style={styles.labelText}>当前密码</span>
          <input
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            autoComplete="current-password"
            required
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          <span style={styles.labelText}>新密码</span>
          <input
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          <span style={styles.labelText}>确认新密码</span>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
            style={styles.input}
          />
        </label>
        <div>
          <button type="submit" style={styles.btn} disabled={busy}>
            {busy ? '保存中...' : '修改密码'}
          </button>
        </div>
        {done && <div style={styles.success}>密码已修改</div>}
        {error && <div style={styles.error}>! {error}</div>}
      </form>
    </Card>
  );
}

// --- chrome ----------------------------------------------------------------

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

const styles = {
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
  row: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    flexWrap: 'wrap',
  },
  col: { display: 'flex', flexDirection: 'column', gap: 12 },
  subSection: {
    paddingTop: 10,
    borderTop: '1px dashed var(--line)',
  },
  subTitle: {
    fontSize: 11,
    color: 'var(--fg-3)',
    textTransform: 'lowercase',
    letterSpacing: '0.06em',
    marginBottom: 8,
  },
  tfaSetup: {
    display: 'grid',
    gridTemplateColumns: '160px 1fr',
    gap: 16,
    alignItems: 'flex-start',
  },
  qrShell: { background: '#fff', padding: 8, borderRadius: 4 },
  qrFrame: { width: 144, height: 144, display: 'block' },
  tfaSetupRight: { display: 'flex', flexDirection: 'column', gap: 10 },
  secretBox: {
    background: 'var(--bg)',
    border: '1px solid var(--line)',
    borderRadius: 4,
    padding: '8px 10px',
    fontSize: 11,
    color: 'var(--accent)',
    wordBreak: 'break-all',
    fontFamily: 'inherit',
  },
  statusOk: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 12,
    color: 'var(--fg-2)',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    boxShadow: '0 0 6px var(--accent-glow)',
  },
  recoveryBox: {
    border: '1px solid var(--line)',
    borderRadius: 4,
    padding: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    background: 'var(--bg)',
  },
  recoveryGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
    gap: 6,
  },
  recoveryCode: {
    fontSize: 11,
    color: 'var(--accent)',
    background: 'var(--bg-2)',
    border: '1px solid var(--line-2)',
    padding: '4px 8px',
    borderRadius: 3,
    textAlign: 'center',
    fontFamily: 'inherit',
  },
  form: { display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 280 },
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
    background: 'transparent',
    color: 'var(--danger)',
    border: '1px solid var(--danger)',
    padding: '7px 12px',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontFamily: 'inherit',
  },
  warn: {
    fontSize: 11,
    color: '#0a0b0d',
    background: 'var(--accent)',
    padding: '8px 10px',
    borderRadius: 4,
    fontWeight: 600,
  },
  muted: { color: 'var(--fg-3)', fontSize: 12 },
  error: {
    color: 'var(--danger)',
    fontSize: 11,
    border: '1px solid var(--danger)',
    padding: '6px 10px',
    borderRadius: 4,
    background: 'color-mix(in oklab, var(--danger) 10%, transparent)',
  },
  success: {
    color: 'var(--accent)',
    fontSize: 11,
    border: '1px solid color-mix(in oklab, var(--accent) 40%, transparent)',
    padding: '6px 10px',
    borderRadius: 4,
    background: 'color-mix(in oklab, var(--accent) 8%, transparent)',
  },
};
