import { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

const RECOVERY_PATTERN = /^[a-z0-9]{4}-[a-z0-9]{4}$/i;
const TOTP_PATTERN = /^\d{6}$/;

export default function Login() {
  const { login, verifyTfa } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || '/admin/dashboard';

  // 'creds' = email + password; 'tfa' = TOTP / recovery challenge.
  const [step, setStep] = useState('creds');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const codeInputRef = useRef(null);

  useEffect(() => {
    if (step === 'tfa') codeInputRef.current?.focus();
  }, [step, useRecovery]);

  async function onSubmitCreds(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const resp = await login(email.trim(), password);
      if (resp?.tfa_required && resp?.challenge) {
        setChallenge(resp.challenge);
        setCode('');
        setUseRecovery(false);
        setStep('tfa');
        return;
      }
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err?.detail || err?.message || 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmitTfa(e) {
    e.preventDefault();
    setError(null);
    const trimmed = code.trim();
    if (useRecovery) {
      if (!RECOVERY_PATTERN.test(trimmed)) {
        setError('Recovery code: xxxx-xxxx (4 + 4 chars)');
        return;
      }
    } else if (!TOTP_PATTERN.test(trimmed)) {
      setError('Authenticator code: 6 digits');
      return;
    }
    setSubmitting(true);
    try {
      await verifyTfa(challenge, trimmed, email.trim());
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err?.detail || err?.message || 'Verification failed');
    } finally {
      setSubmitting(false);
    }
  }

  function backToCreds() {
    setStep('creds');
    setChallenge(null);
    setCode('');
    setUseRecovery(false);
    setError(null);
  }

  function toggleRecovery() {
    setUseRecovery((v) => !v);
    setCode('');
    setError(null);
  }

  return (
    <div style={styles.shell}>
      {step === 'creds' ? (
        <form style={styles.card} onSubmit={onSubmitCreds} noValidate>
          <div style={styles.brand}>
            <span style={styles.brandDot} />
            <span style={styles.brandText}>myblog · admin</span>
          </div>
          <h1 style={styles.title}>Sign in</h1>
          <p style={styles.subtitle}>
            Enter your administrator credentials to continue.
          </p>

          <label style={styles.label}>
            <span style={styles.labelText}>email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
              style={styles.input}
              placeholder="you@example.com"
            />
          </label>
          <label style={styles.label}>
            <span style={styles.labelText}>password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              style={styles.input}
              placeholder="••••••••"
            />
          </label>

          {error && <div style={styles.error}>! {error}</div>}

          <button type="submit" disabled={submitting} style={styles.btn}>
            {submitting ? 'signing in…' : 'sign in →'}
          </button>

          <div style={styles.footer}>
            <a href="/" style={styles.footerLink}>← back to public site</a>
          </div>
        </form>
      ) : (
        <form style={styles.card} onSubmit={onSubmitTfa} noValidate data-testid="tfa-form">
          <div style={styles.brand}>
            <span style={styles.brandDot} />
            <span style={styles.brandText}>myblog · admin · 2fa</span>
          </div>
          <h1 style={styles.title}>two-factor</h1>
          <p style={styles.subtitle}>
            {useRecovery
              ? 'Paste a recovery code (xxxx-xxxx).'
              : 'Enter the 6-digit code from your authenticator app.'}
          </p>

          <label style={styles.label}>
            <span style={styles.labelText}>
              {useRecovery ? 'recovery code' : 'code'}
            </span>
            <input
              ref={codeInputRef}
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoComplete="one-time-code"
              inputMode={useRecovery ? 'text' : 'numeric'}
              maxLength={useRecovery ? 9 : 6}
              required
              style={{ ...styles.input, letterSpacing: '0.4em', textAlign: 'center', fontSize: 16 }}
              placeholder={useRecovery ? 'abcd-efgh' : '••••••'}
            />
          </label>

          {error && <div style={styles.error}>! {error}</div>}

          <button type="submit" disabled={submitting} style={styles.btn}>
            {submitting ? 'verifying…' : 'verify →'}
          </button>

          <div style={styles.linksRow}>
            <button type="button" onClick={toggleRecovery} style={styles.linkBtn}>
              {useRecovery ? 'use authenticator code' : 'use recovery code'}
            </button>
            <button type="button" onClick={backToCreds} style={styles.linkBtn}>
              ← back
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

const styles = {
  shell: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    background: 'var(--bg)',
    color: 'var(--fg)',
    fontFamily: "'JetBrains Mono', ui-monospace, Menlo, monospace",
  },
  card: {
    width: '100%',
    maxWidth: 380,
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 8,
    padding: '28px 28px 22px',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    boxShadow: '0 0 0 1px var(--line) inset',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 12,
    color: 'var(--fg-3)',
    marginBottom: 4,
  },
  brandDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    background: 'var(--accent)',
    boxShadow: '0 0 8px var(--accent-glow)',
  },
  brandText: { letterSpacing: '0.04em' },
  title: {
    fontSize: 22,
    margin: 0,
    fontWeight: 600,
    color: 'var(--fg)',
  },
  subtitle: {
    margin: 0,
    fontSize: 12,
    color: 'var(--fg-3)',
  },
  label: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    marginTop: 4,
  },
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
    padding: '10px 12px',
    fontFamily: 'inherit',
    fontSize: 13,
    borderRadius: 4,
    outline: 'none',
  },
  error: {
    color: 'var(--danger)',
    fontSize: 12,
    border: '1px solid var(--danger)',
    padding: '8px 10px',
    borderRadius: 4,
    background: 'color-mix(in oklab, var(--danger) 10%, transparent)',
  },
  btn: {
    marginTop: 6,
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    padding: '10px 14px',
    border: 0,
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 13,
    letterSpacing: '0.04em',
  },
  footer: {
    marginTop: 8,
    fontSize: 11,
    color: 'var(--fg-3)',
    textAlign: 'center',
  },
  footerLink: {
    color: 'var(--fg-3)',
    textDecoration: 'underline',
  },
  linksRow: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: 8,
    fontSize: 11,
  },
  linkBtn: {
    background: 'none',
    border: 0,
    color: 'var(--fg-3)',
    textDecoration: 'underline',
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 11,
    padding: 0,
  },
};
