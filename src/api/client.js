const BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request(path, opts = {}) {
  const r = await fetch(`${BASE}/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      detail = (await r.json()).detail || detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(`${r.status} ${detail}`);
  }
  if (r.status === 204) return null;
  return r.json();
}

export const api = {
  site: () => request('/site'),
  profile: () => request('/profile'),
  contacts: () => request('/contacts'),
  tags: () => request('/tags'),
  projects: () => request('/projects'),
  contrib: (weeks = 52) => request(`/contrib?weeks=${weeks}`),
  posts: {
    list: (params = {}) => {
      const q = new URLSearchParams(
        Object.fromEntries(
          Object.entries(params).filter(([, v]) => v != null && v !== ''),
        ),
      ).toString();
      return request(`/posts${q ? '?' + q : ''}`);
    },
    detail: (id, { previewToken } = {}) => {
      // Task 67: 当 URL 带 ?preview_token= 时把它转发给后端，让 draft 也能渲染。
      const q = previewToken ? `?preview_token=${encodeURIComponent(previewToken)}` : '';
      return request(`/posts/${id}${q}`);
    },
    like: (id) => request(`/posts/${id}/like`, { method: 'POST' }),
  },
  now: () => request('/now'),
};
