// Admin site & theme settings API.
// Same bearer-aware pattern as src/api/admin.js, kept inline so each lane is
// self-contained.

const BASE = import.meta.env.VITE_API_BASE_URL || '';
const TOKEN_KEY = 'myblog.admin.token';

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function siteRequest(path, opts = {}) {
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

export const apiSite = {
  getSite() {
    return siteRequest('/site');
  },
  putSite(payload) {
    return siteRequest('/site', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
  getTheme() {
    return siteRequest('/theme');
  },
  putTheme(payload) {
    return siteRequest('/theme', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  },
};

export default apiSite;
