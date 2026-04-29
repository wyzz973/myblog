import { useState } from 'react';
import { apiAccount } from '../../api/account.js';

export default function Account() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <TfaSection />
      <MagicLinkSection />
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
      setError(err?.detail || err?.message || 'setup failed');
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
      setError(err?.detail || err?.message || 'enable failed');
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
      setError(err?.detail || err?.message || 'disable failed');
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
      setError(err?.detail || err?.message || 'regenerate failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Two-factor authentication" subtitle="TOTP via authenticator app">
      {phase === 'idle' && (
        <div style={styles.row}>
          <span style={styles.muted}>2FA is not active for this account.</span>
          <button type="button" onClick={onSetup} disabled={busy} style={styles.btnPrimary}>
            {busy ? 'starting…' : 'set up 2FA'}
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
              Scan the QR with your authenticator, or enter the secret manually:
            </div>
            <code style={styles.secretBox}>{setup.secret}</code>
            <form onSubmit={onEnable} style={styles.form} noValidate>
              <label style={styles.label}>
                <span style={styles.labelText}>6-digit code</span>
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
                  {busy ? 'verifying…' : 'verify + enable'}
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
                  cancel
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
            2FA is enabled.
          </div>

          {recovery && recovery.length > 0 && (
            <div style={styles.recoveryBox}>
              <div style={styles.warn}>
                ! Save these recovery codes now — each can only be used once.
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
                hide
              </button>
            </div>
          )}

          <div style={styles.subSection}>
            <div style={styles.subTitle}>Regenerate recovery codes</div>
            <form onSubmit={onRegenerate} style={styles.form} noValidate>
              <label style={styles.label}>
                <span style={styles.labelText}>current 6-digit code</span>
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
                  {busy ? 'working…' : 'regenerate'}
                </button>
              </div>
            </form>
          </div>

          <div style={styles.subSection}>
            <div style={{ ...styles.subTitle, color: 'var(--danger)' }}>Disable 2FA</div>
            <form onSubmit={onDisable} style={styles.form} noValidate>
              <label style={styles.label}>
                <span style={styles.labelText}>current 6-digit code</span>
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
                  {busy ? 'disabling…' : 'disable 2FA'}
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
      setError(err?.detail || err?.message || 'toggle failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Magic-link login" subtitle="Email a one-time login link">
      <div style={styles.row}>
        <span style={styles.muted}>
          {enabled === null
            ? 'Toggle to update preference. Server-side state is the source of truth.'
            : enabled
            ? 'Magic-link login is enabled.'
            : 'Magic-link login is disabled.'}
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            disabled={busy}
            onClick={() => onToggle(true)}
            style={enabled === true ? styles.btnPrimary : styles.btnSecondary}
          >
            enable
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onToggle(false)}
            style={enabled === false ? styles.btnPrimary : styles.btnSecondary}
          >
            disable
          </button>
        </div>
      </div>
      {error && <div style={styles.error}>! {error}</div>}
    </Card>
  );
}

// --- Password ---------------------------------------------------------------

function PasswordSection() {
  return (
    <Card title="Password" subtitle="Account password">
      <div style={styles.muted}>
        The admin API does not currently expose a password-change endpoint.
        Reset via your seed/CLI workflow until a route is added.
      </div>
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
};
