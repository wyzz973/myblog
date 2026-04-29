// API client for the tags admin namespace.

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

export const tagsApi = {
  list() {
    return adminRequest('/tags');
  },
  create(payload) {
    return adminRequest('/tags', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  patch(id, payload) {
    return adminRequest(`/tags/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },
  remove(id) {
    return adminRequest(`/tags/${id}`, { method: 'DELETE' });
  },
  reorder(ids) {
    return adminRequest('/tags/order', {
      method: 'PUT',
      body: JSON.stringify({ ids }),
    });
  },
};

export default tagsApi;
