// Bearer-aware fetch wrapper for the admin namespace.
// Reads the JWT access token from localStorage on every request so the
// caller does not have to thread it through React state explicitly.
//
// On 401, this layer transparently calls /auth/refresh once (using the
// httpOnly refresh cookie the backend set at login). If the refresh
// succeeds, the original request is retried with the new access token.
// If the refresh fails, the registered onUnauthorized callback runs so
// the UI can clear state and bounce to the login screen.

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

// JWT exp claim → ms since epoch, or null if unparseable. Used by
// AuthContext to schedule a proactive refresh well before the token dies.
export function jwtExpiresAt(token) {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    // base64url → base64 → utf-8 string
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
    const json = JSON.parse(
      typeof atob === 'function'
        ? atob(padded)
        : Buffer.from(padded, 'base64').toString('utf-8'),
    );
    return typeof json.exp === 'number' ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

let _onUnauthorized = null;

// AuthContext registers a callback fired when refresh fails. Plain
// function call rather than an event so the call site is explicit.
export function setOnUnauthorized(cb) {
  _onUnauthorized = typeof cb === 'function' ? cb : null;
}

// One in-flight /auth/refresh at a time. Concurrent 401s coalesce on the
// same promise so we don't trigger refresh-token rotation twice.
let _refreshing = null;

export function tryRefresh() {
  if (_refreshing) return _refreshing;
  _refreshing = (async () => {
    try {
      const r = await fetch(`${BASE}/api/admin/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!r.ok) return null;
      const data = await r.json().catch(() => null);
      if (!data?.access) return null;
      setToken(data.access);
      return data;
    } catch {
      return null;
    }
  })();
  // Reset the module-level guard once this attempt settles so a later
  // 401 triggers a fresh refresh instead of replaying the cached result.
  _refreshing.finally(() => {
    _refreshing = null;
  });
  return _refreshing;
}

// Test-only escape hatch: clears the in-flight guard so test isolation
// doesn't depend on settle-order of a prior test's pending promise.
export function __resetForTests() {
  _refreshing = null;
  _onUnauthorized = null;
  clearToken();
}

async function fetchWithAuth(path, opts) {
  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(`${BASE}/api/admin${path}`, {
    ...opts,
    headers,
    credentials: 'include',
  });
}

export async function adminRequest(path, opts = {}) {
  let r = await fetchWithAuth(path, opts);

  // 401 on a non-auth endpoint → try one refresh + retry. Refresh
  // endpoints themselves don't get a retry (no recursion).
  if (r.status === 401 && !path.startsWith('/auth/')) {
    const refreshed = await tryRefresh();
    if (refreshed?.access) {
      r = await fetchWithAuth(path, opts);
    } else {
      // Refresh exhausted — clear state and let the UI react.
      clearToken();
      _onUnauthorized?.();
    }
  }

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

  refresh() {
    return tryRefresh();
  },

  // ---- Dashboard ----------------------------------------------------------
  dashboard() {
    return adminRequest('/dashboard');
  },
};

export default apiAdmin;
