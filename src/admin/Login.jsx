import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.jsx';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || '/admin/dashboard';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err?.detail || err?.message || 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={styles.shell}>
      <form style={styles.card} onSubmit={onSubmit} noValidate>
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
};
