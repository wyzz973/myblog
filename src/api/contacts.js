// API client for /api/admin/contacts.
// Mirrors the bearer-aware fetch pattern in src/api/admin.js so screens can
// rely on the JWT in localStorage["myblog.admin.token"] without threading
// the token through React state.

import { TOKEN_KEY } from './admin.js';

const BASE = import.meta.env.VITE_API_BASE_URL || '';

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function request(path, opts = {}) {
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

export const apiContacts = {
  list() {
    return request('/contacts');
  },
  create(payload) {
    return request('/contacts', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  patch(cid, partial) {
    return request(`/contacts/${cid}`, {
      method: 'PATCH',
      body: JSON.stringify(partial),
    });
  },
  remove(cid) {
    return request(`/contacts/${cid}`, { method: 'DELETE' });
  },
  // Body shape matches backend exactly: { ids: int[] }.
  reorder(ids) {
    return request('/contacts/order', {
      method: 'PUT',
      body: JSON.stringify({ ids }),
    });
  },
};

export default apiContacts;
