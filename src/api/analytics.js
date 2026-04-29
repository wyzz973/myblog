// Admin analytics API client.
// Inline bearer-aware fetch wrapper (mirrors src/api/admin.js intentionally
// to keep each module self-contained; no _client.js abstraction).

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

// Range tokens accepted by UI -> days for backend
function rangeToDays(range) {
  if (range === '7d') return 7;
  if (range === '90d') return 90;
  return 30;
}

export const apiAnalytics = {
  bundle(range) {
    const days = rangeToDays(range);
    return req(`/analytics?days=${days}`);
  },
  posts(range) {
    const days = rangeToDays(range);
    return req(`/analytics/posts?days=${days}`);
  },
  tags(range) {
    const days = rangeToDays(range);
    return req(`/analytics/tags?days=${days}`);
  },
};

export default apiAnalytics;
