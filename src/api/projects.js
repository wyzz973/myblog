// API client for /api/admin/projects.
// Project key is the human-readable `name` (string), not a numeric id.

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

export const apiProjects = {
  list() {
    return request('/projects');
  },
  create(payload) {
    return request('/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
  patch(name, partial) {
    return request(`/projects/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      body: JSON.stringify(partial),
    });
  },
  remove(name) {
    return request(`/projects/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
  },
  // Backend reorder endpoint expects body `{ ids: string[] }` even though the
  // values are project names — verified in backend/app/routers/admin/projects.py.
  reorder(names) {
    return request('/projects/order', {
      method: 'PUT',
      body: JSON.stringify({ ids: names }),
    });
  },
};

export default apiProjects;
