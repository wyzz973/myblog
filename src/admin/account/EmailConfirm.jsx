// /admin/account/email-confirm?token=xxx — Task 28c step 2.
//
// This page is reachable from the link in the confirmation email. It
// auto-submits the token via POST /api/admin/account/email/confirm and
// shows the resulting state (success / expired / invalid). No session is
// required — the token is the auth, so the user can confirm from any
// browser even if they're logged out.

import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiAccount } from '../../api/account.js';

export default function EmailConfirm() {
  const [params] = useSearchParams();
  const token = params.get('token');
  const [state, setState] = useState('pending');
  const [email, setEmail] = useState(null);
  const [error, setError] = useState(null);
  // The confirm call mutates server state (consumes the one-shot token).
  // React StrictMode runs effects twice in dev → without a guard the second
  // run would see the row already consumed and report "invalid or expired
  // token" even though the first run succeeded. The ref keys the call to
  // the token value so a fresh navigation with a new token still fires.
  const calledForToken = useRef(null);

  useEffect(() => {
    if (!token) {
      setState('error');
      setError('链接缺少 token 参数');
      return undefined;
    }
    if (calledForToken.current === token) return undefined;
    calledForToken.current = token;
    // We deliberately do NOT short-circuit the .then on unmount: in dev
    // React StrictMode mounts → unmounts → remounts on first render. With
    // an `alive` guard the first mount's promise would resolve into a
    // dead closure and the page would be stuck on "正在确认…" forever.
    // The ref above ensures we only fire one call per token; the result
    // updates state regardless of which mount instance is still around.
    apiAccount.confirmEmailChange(token)
      .then((res) => {
        setEmail(res.email);
        setState('success');
      })
      .catch((e) => {
        setError(e?.detail || e?.message || '确认失败');
        setState('error');
      });
    return undefined;
  }, [token]);

  return (
    <div style={styles.shell} data-testid="email-confirm-page">
      <h1 style={styles.h1}>确认邮箱变更</h1>

      {state === 'pending' && (
        <div style={styles.muted} data-testid="email-confirm-pending">正在确认…</div>
      )}

      {state === 'success' && (
        <div data-testid="email-confirm-success">
          <p style={styles.p}>
            已将管理员邮箱切换到 <strong>{email}</strong>。
          </p>
          <p style={styles.muted}>下次登录请使用新邮箱。</p>
          <Link to="/admin" style={styles.btn}>前往登录</Link>
        </div>
      )}

      {state === 'error' && (
        <div data-testid="email-confirm-error" style={styles.error} role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

const styles = {
  shell: {
    maxWidth: 480,
    margin: '64px auto',
    padding: '24px 28px',
    background: 'var(--bg-2)',
    border: '1px solid var(--line)',
    borderRadius: 6,
    fontFamily: 'inherit',
  },
  h1: { fontSize: 16, color: 'var(--fg)', margin: 0, marginBottom: 12 },
  p: { fontSize: 13, color: 'var(--fg-2)', margin: '8px 0' },
  muted: { fontSize: 12, color: 'var(--fg-3)', margin: '4px 0' },
  btn: {
    display: 'inline-block',
    marginTop: 12,
    padding: '7px 14px',
    background: 'var(--accent)',
    color: '#0a0b0d',
    fontWeight: 600,
    fontSize: 12,
    textDecoration: 'none',
    borderRadius: 4,
  },
  error: {
    padding: '8px 10px',
    border: '1px solid var(--danger)',
    color: 'var(--danger)',
    background: 'var(--bg)',
    borderRadius: 4,
    fontSize: 12,
  },
};
