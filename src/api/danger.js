// Admin danger-zone API client (export, import, delete-site, status).
//
// The schemas live in backend/app/schemas/danger.py:
//   ExportRequest      { password }
//   DeleteSiteRequest  { password, handle }
//   ScheduleDeleteResponse, DangerStatusResponse, ImportResponse, etc.

const BASE = import.meta.env.VITE_API_BASE_URL || '';
const TOKEN_KEY = 'myblog.admin.token';

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

async function req(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (!headers['Content-Type'] && !(opts.body instanceof FormData)) {
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

export const apiDanger = {
  status() {
    return req('/danger/status');
  },
  listExports() {
    return req('/danger/exports');
  },
  getExport(jobId) {
    return req(`/danger/export/${encodeURIComponent(jobId)}`);
  },
  requestExport(password) {
    return req('/danger/export', {
      method: 'POST',
      body: JSON.stringify({ password }),
    });
  },
  // Returns the relative URL for download — used as href on an anchor so the
  // browser handles the file save. Bearer token must be sent though, so we
  // do a fetch + blob URL handoff instead.
  async downloadExport(jobId) {
    const token = getToken();
    const r = await fetch(`${BASE}/api/admin/danger/export/${encodeURIComponent(jobId)}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
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
    return r.blob();
  },
  scheduleDelete({ password, handle }) {
    return req('/danger/delete-site', {
      method: 'POST',
      body: JSON.stringify({ password, handle }),
    });
  },
  cancelDelete() {
    return req('/danger/delete-site/cancel', { method: 'POST' });
  },
  importSite({ file, password }) {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('password', password);
    return req('/danger/import', { method: 'POST', body: fd });
  },
};

export default apiDanger;
