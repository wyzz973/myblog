// Admin account API client (2FA + magic-link).
//
// Note: there is no /api/admin/account password-change endpoint exposed at
// time of writing — see backend/app/routers/admin/account.py. The Account
// screen surfaces a placeholder for that section.

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
};

export default apiAccount;
