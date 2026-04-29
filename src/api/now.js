// API client for /api/admin/now.
// NowEntryItem: { id, body_md, listening, reading, is_current, created_at }
// Backend handles is_current exclusivity automatically (verified in
// backend/app/services/now.py).

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

export const apiNow = {
  list() {
    return request('/now');
  },
  // payload: { body_md, listening?, reading?, is_current? }
  create(payload) {
    return request('/now', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  // partial may include any of body_md, listening, reading, is_current.
  patch(entryId, partial) {
    return request(`/now/${entryId}`, {
      method: 'PATCH',
      body: JSON.stringify(partial),
    });
  },
  remove(entryId) {
    return request(`/now/${entryId}`, { method: 'DELETE' });
  },
};

export default apiNow;
