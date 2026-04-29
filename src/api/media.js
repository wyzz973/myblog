// Admin media library API.
// Pattern after `src/api/admin.js`: bearer-aware fetch, /api/admin prefix,
// throw on non-2xx. Multipart bodies must NOT set Content-Type — let the
// browser pick the boundary.

import { getToken } from './admin.js';

const BASE = import.meta.env.VITE_API_BASE_URL || '';

async function mediaRequest(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  // Only set JSON content-type when caller explicitly asked for JSON body.
  if (opts.body && typeof opts.body === 'string' && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
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

// Build an absolute URL for a MediaItem.url like "/media/<storage_path>".
// The backend may live at a different origin than the SPA in production.
export function mediaUrl(item) {
  if (!item) return '';
  const u = typeof item === 'string' ? item : item.url;
  if (!u) return '';
  if (/^https?:\/\//i.test(u)) return u;
  return `${BASE}${u}`;
}

export const apiMedia = {
  list({ limit, offset } = {}) {
    const params = new URLSearchParams();
    if (limit != null) params.set('limit', String(limit));
    if (offset != null) params.set('offset', String(offset));
    const q = params.toString();
    return mediaRequest(`/media${q ? `?${q}` : ''}`);
  },

  get(id) {
    return mediaRequest(`/media/${id}`);
  },

  upload(files) {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    return mediaRequest('/media', {
      method: 'POST',
      body: fd,
      // No Content-Type: browser sets multipart boundary.
    });
  },

  patch(id, patch) {
    return mediaRequest(`/media/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },

  remove(id) {
    return mediaRequest(`/media/${id}`, { method: 'DELETE' });
  },
};

export default apiMedia;
