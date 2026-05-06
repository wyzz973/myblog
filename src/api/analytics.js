// Admin analytics API client.
// Inline bearer-aware fetch wrapper (mirrors src/api/admin.js intentionally
// to keep each module self-contained; no _client.js abstraction).

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
  return r.json();
}

// Range tokens accepted by UI -> days for backend.
//   '7d' / '30d' / '90d' — fixed presets
//   'since:YYYY-MM-DD'  — custom: derive days = (today_utc - start) + 1
function rangeToDays(range) {
  if (typeof range === 'string' && range.startsWith('since:')) {
    const iso = range.slice('since:'.length);
    const start = new Date(`${iso}T00:00:00Z`);
    if (Number.isNaN(start.getTime())) return 30;
    const todayUtc = new Date();
    todayUtc.setUTCHours(0, 0, 0, 0);
    const ms = todayUtc.getTime() - start.getTime();
    const days = Math.floor(ms / 86400000) + 1;
    if (days < 1) return 1;
    if (days > 365) return 365;
    return days;
  }
  if (range === '7d') return 7;
  if (range === '90d') return 90;
  return 30;
}

export { rangeToDays };

export const apiAnalytics = {
  bundle(range) {
    const days = rangeToDays(range);
    return req(`/analytics?days=${days}`);
  },
  posts(range) {
    const days = rangeToDays(range);
    return req(`/analytics/posts?days=${days}`);
  },
  tags(range) {
    const days = rangeToDays(range);
    return req(`/analytics/tags?days=${days}`);
  },
  // Task 25c: per-post drilldown — daily timeseries for one post.
  postTimeseries(postId, range) {
    const days = rangeToDays(range);
    return req(`/analytics/posts/${encodeURIComponent(postId)}/timeseries?days=${days}`);
  },
  // Task 25a: download per-post hits as CSV. Fetches with the bearer
  // token, then triggers a browser download via an in-memory blob.
  // Returns the suggested filename so callers can surface a toast.
  async downloadPostsCsv(range) {
    const days = rangeToDays(range);
    const token = getToken();
    const r = await fetch(`${BASE}/api/admin/analytics/posts.csv?days=${days}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!r.ok) {
      const detail = await r.text().catch(() => `${r.status}`);
      const err = new Error(`${r.status} ${detail}`);
      err.status = r.status;
      throw err;
    }
    const blob = await r.blob();
    // Server's Content-Disposition: attachment; filename="..."
    const cd = r.headers.get('content-disposition') || '';
    const m = cd.match(/filename="([^"]+)"/);
    const filename = m ? m[1] : `analytics-posts-${days}d.csv`;
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

export default apiAnalytics;
