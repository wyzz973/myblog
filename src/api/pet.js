// API client for /api/admin/pet — single-config get/put.
// PetConfig fields (verified in backend/app/schemas/pet.py):
//   model, system_prompt, fallback_lines, rate_limit_per_min,
//   enabled, species ("cat"|"dog"|"rabbit"|"fox"), hat, tint,
//   visitor_can_change.

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

export const apiPet = {
  get() {
    return request('/pet');
  },
  // Backend rejects extra fields (extra="forbid"); send the full PetConfig.
  put(config) {
    return request('/pet', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  },
  fetchDefaults() {
    return request('/pet/defaults');
  },
  resetSection(section) {
    return request(`/pet/reset?section=${encodeURIComponent(section)}`, {
      method: 'POST',
    });
  },
  listConversations(params = {}) {
    const qs = new URLSearchParams();
    if (params.cursor) qs.set('cursor', params.cursor);
    if (params.species) qs.set('species', params.species);
    if (params.since) qs.set('since', params.since);
    if (params.limit) qs.set('limit', String(params.limit));
    const suffix = qs.toString();
    return request(`/pet/conversations${suffix ? '?' + suffix : ''}`);
  },
  getConversation(visitorHash, params = {}) {
    const qs = new URLSearchParams();
    if (params.cursor) qs.set('cursor', String(params.cursor));
    if (params.limit) qs.set('limit', String(params.limit));
    const suffix = qs.toString();
    return request(
      `/pet/conversations/${encodeURIComponent(visitorHash)}${suffix ? '?' + suffix : ''}`,
    );
  },
  deleteConversation(visitorHash) {
    return request(
      `/pet/conversations/${encodeURIComponent(visitorHash)}`,
      { method: 'DELETE' },
    );
  },
  // action ∈ "unmute" | "reset"
  patchProfile(visitorHash, action) {
    return request(
      `/pet/profiles/${encodeURIComponent(visitorHash)}`,
      { method: 'PATCH', body: JSON.stringify({ action }) },
    );
  },
  getUsage() {
    return request('/pet/usage');
  },
};

export default apiPet;
