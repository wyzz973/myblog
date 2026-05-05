// API client for the comments admin namespace.

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

export const commentsApi = {
  // status: "pending" | "approved" | "spam" | undefined (=all)
  list({ status, post_id, limit = 100, offset = 0 } = {}) {
    return adminRequest(`/comments${qs({ status, post_id, limit, offset })}`);
  },
  patch(id, payload) {
    return adminRequest(`/comments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  remove(id) {
    return adminRequest(`/comments/${id}`, { method: 'DELETE' });
  },
  // Bulk moderation: action ∈ approve|spam|pending|delete.
  // Returns {affected, action}.
  bulk(action, ids) {
    return adminRequest(`/comments/bulk`, {
      method: 'POST',
      body: JSON.stringify({ action, ids }),
    });
  },
};

export default commentsApi;
