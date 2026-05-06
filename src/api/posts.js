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
  // Task 30: bulk upload of .md files. Multipart body, omits the
  // application/json Content-Type so the browser picks the boundary.
  // Returns the response body for 201/207/422 (per-file results live
  // there); throws only for genuine errors (auth, network).
  async bulkUpload(files, { overwrite = false } = {}) {
    const fd = new FormData();
    for (const f of files) fd.append('files', f, f.name);
    const token = getToken();
    const url = `${BASE}/api/admin/posts/upload${qs({ overwrite })}`;
    const r = await fetch(url, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    // 201 (all ok) / 207 (partial) / 422 (all failed) all carry the
    // structured per-file results in the body.
    if (r.status === 201 || r.status === 207 || r.status === 422) {
      return r.json();
    }
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
  },
  // Task 49: ask the backend for the next 3-digit `n` so the editor can
  // pre-fill the new-post template without colliding with an existing row.
  nextN() {
    return adminRequest('/posts/next-n');
  },
  // Task 42: download every post as a single tar archive — round-trips
  // through bulkUpload for full backup/restore.
  async downloadTar() {
    const token = getToken();
    const r = await fetch(`${BASE}/api/admin/posts.tar`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!r.ok) {
      const detail = await r.text().catch(() => `${r.status}`);
      const err = new Error(`${r.status} ${detail}`);
      err.status = r.status;
      throw err;
    }
    const blob = await r.blob();
    const cd = r.headers.get('content-disposition') || '';
    const m = cd.match(/filename="([^"]+)"/);
    const filename = m ? m[1] : 'posts.tar';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return { filename };
  },
};

export default postsApi;
