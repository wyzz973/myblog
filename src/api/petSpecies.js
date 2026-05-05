// API client for /api/admin/pet/species (Task 21d).
// The catalogue itself; sits next to apiPet (which manages PetConfig — site
// behavior knobs). Public read at /api/pet/species is consumed by the
// frontend bootstrap path in 21e and lives in api/client.js, not here.

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
      /* non-JSON error body */
    }
    const err = new Error(`${r.status} ${detail}`);
    err.status = r.status;
    err.detail = detail;
    throw err;
  }
  if (r.status === 204) return null;
  return r.json();
}

export const apiPetSpecies = {
  list() {
    return request('/pet/species');
  },
  create(body) {
    return request('/pet/species', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },
  patch(id, partial) {
    return request(`/pet/species/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(partial),
    });
  },
  delete(id) {
    return request(`/pet/species/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  },
};

export default apiPetSpecies;
