// Bearer-aware fetch wrapper for the admin namespace.
// Reads the JWT access token from localStorage on every request so the
// caller does not have to thread it through React state explicitly.

const BASE = import.meta.env.VITE_API_BASE_URL || '';
export const TOKEN_KEY = 'myblog.admin.token';

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(tok) {
  try {
    if (tok) localStorage.setItem(TOKEN_KEY, tok);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore storage errors */
  }
}

export function clearToken() {
  setToken(null);
}

async function adminRequest(path, opts = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const r = await fetch(`${BASE}/api/admin${path}`, {
    ...opts,
    headers,
  });

  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = await r.json();
      detail = body.detail || detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    const err = new Error(`${r.status} ${detail}`);
    err.status = r.status;
    err.detail = detail;
    throw err;
  }
  if (r.status === 204) return null;
  // Some endpoints (file downloads) might not be JSON; for now admin returns JSON.
  const ct = r.headers.get('content-type') || '';
  if (!ct.includes('application/json')) return r;
  return r.json();
}

export const apiAdmin = {
  // ---- Auth ---------------------------------------------------------------
  login(email, password) {
    return adminRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  verifyTfa(challenge, code) {
    return adminRequest('/auth/2fa', {
      method: 'POST',
      body: JSON.stringify({ challenge, code }),
    });
  },

  // ---- Dashboard ----------------------------------------------------------
  dashboard() {
    return adminRequest('/dashboard');
  },
};

export default apiAdmin;
