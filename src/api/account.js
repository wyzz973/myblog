// Admin account API client (password + 2FA + magic-link).

const BASE = import.meta.env.VITE_API_BASE_URL || '';
const TOKEN_KEY = 'myblog.admin.token';

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function req(path, opts = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(`${BASE}/api/admin${path}`, { ...opts, headers });
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = await r.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON */
    }
    const err = new Error(`${r.status} ${detail}`);
    err.status = r.status;
    err.detail = detail;
    throw err;
  }
  if (r.status === 204) return null;
  return r.json();
}

export const apiAccount = {
  // POST → { secret, otpauth_uri, qr_svg }
  setupTfa() {
    return req('/account/2fa/setup', { method: 'POST' });
  },
  // POST { code } → { recovery_codes: [...] }
  enableTfa(code) {
    return req('/account/2fa/enable', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
  },
  // DELETE { current_code } → 204
  disableTfa(currentCode) {
    return req('/account/2fa', {
      method: 'DELETE',
      body: JSON.stringify({ current_code: currentCode }),
    });
  },
  // POST { current_code } → { recovery_codes }
  regenerateRecovery(currentCode) {
    return req('/account/2fa/recovery-codes/regenerate', {
      method: 'POST',
      body: JSON.stringify({ current_code: currentCode }),
    });
  },
  // PATCH { enabled } → { magic_link_enabled }
  setMagicLink(enabled) {
    return req('/account/magic-link', {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    });
  },
  // POST { current_password, new_password } → 204
  changePassword(currentPassword, newPassword) {
    return req('/account/password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
  },
  // Task 28a/b: rotate the admin email. POST { current_password, new_email }
  // → { email }. Backend writes the new email + emits an event log row.
  // Caller should re-login (the JWT still holds the old email claim;
  // /admin/dashboard etc. work but every fresh login sees the new email).
  changeEmail(currentPassword, newEmail) {
    return req('/account/email', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_email: newEmail,
      }),
    });
  },
  // Task 28c step 1: send a magic confirm link to the NEW email.
  // POST { current_password, new_email } → { sent: true, to }.
  // Old login keeps working until step 2 confirms.
  requestEmailChange(currentPassword, newEmail) {
    return req('/account/email/request', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_email: newEmail,
      }),
    });
  },
  // Task 28c step 2: consume the one-shot token and rotate.
  // No bearer required — the token IS the auth.
  async confirmEmailChange(token) {
    const r = await fetch(`${BASE}/api/admin/account/email/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });
    if (!r.ok) {
      let detail = `${r.status}`;
      try { const body = await r.json(); detail = body.detail || detail; } catch { /* non-JSON */ }
      const err = new Error(`${r.status} ${detail}`);
      err.status = r.status;
      err.detail = detail;
      throw err;
    }
    return r.json();
  },
};

export default apiAccount;
