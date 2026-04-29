// API client for the posts admin namespace.
// Uses the same bearer-aware shape as src/api/admin.js (token from localStorage).

const BASE = import.meta.env.VITE_API_BASE_URL || '';
const TOKEN_KEY = 'myblog.admin.token';

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function adminRequest(path, opts = {}) {
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
  const ct = r.headers.get('content-type') || '';
  if (!ct.includes('application/json')) return r;
  return r.json();
}

function qs(params) {
  const usp = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') usp.append(k, String(v));
  });
  const s = usp.toString();
  return s ? `?${s}` : '';
}

export const postsApi = {
  list({ status, tag, q, limit = 50, offset = 0 } = {}) {
    return adminRequest(`/posts${qs({ status, tag, q, limit, offset })}`);
  },
  get(id) {
    return adminRequest(`/posts/${encodeURIComponent(id)}`);
  },
  create(markdown, { overwrite = false } = {}) {
    return adminRequest(`/posts${qs({ overwrite })}`, {
      method: 'POST',
      body: JSON.stringify({ markdown }),
    });
  },
  patch(id, markdown) {
    return adminRequest(`/posts/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ markdown }),
    });
  },
  remove(id) {
    return adminRequest(`/posts/${encodeURIComponent(id)}`, { method: 'DELETE' });
  },
  renderPreview(markdown) {
    return adminRequest(`/posts/render-preview`, {
      method: 'POST',
      body: JSON.stringify({ markdown }),
    });
  },
};

export default postsApi;
