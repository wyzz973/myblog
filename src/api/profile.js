// Admin author-profile API (the public-facing identity, not the user account).

const BASE = import.meta.env.VITE_API_BASE_URL || '';
const TOKEN_KEY = 'myblog.admin.token';

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function profileRequest(path, opts = {}) {
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
      /* ignore */
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

export const apiProfile = {
  // Author profile (ProfileIn / ProfilePayload — see backend/app/routers/admin/site.py).
  get() {
    return profileRequest('/profile');
  },
  put(payload) {
    return profileRequest('/profile', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  // Used by the avatar picker — bearer-authed media listing.
  listImages() {
    return profileRequest('/media');
  },
  // Session info: the *account* email + tfa flag for the signed-in admin.
  // No PUT — backend currently has no account-email-update or password-
  // change endpoint, so the corresponding UI is read-only / deferred.
  session() {
    return profileRequest('/session');
  },
};

export default apiProfile;
