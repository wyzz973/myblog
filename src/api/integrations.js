// Admin integrations API client (GitHub + Anthropic).

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

export const apiIntegrations = {
  getGithub() {
    return req('/integrations/github');
  },
  putGithub({ username, token }) {
    return req('/integrations/github', {
      method: 'PUT',
      body: JSON.stringify({ username, token }),
    });
  },
  syncGithub() {
    return req('/integrations/github/sync', { method: 'POST' });
  },
  getAnthropic() {
    return req('/integrations/anthropic');
  },
  putAnthropic({ api_key, model }) {
    return req('/integrations/anthropic', {
      method: 'PUT',
      body: JSON.stringify({ api_key, model: model || null }),
    });
  },
  // Task 27a: probe a candidate config without persisting it.
  // Body shape varies by provider. Returns { ok: bool, error: string|null }.
  //   anthropic: { api_key, model? }
  //   github:    { username, token }
  //   <openai-compat>: { token, model? }   // zhipu / qwen / doubao / deepseek
  test(name, body) {
    return req(`/integrations/${encodeURIComponent(name)}/test`, {
      method: 'POST',
      body: JSON.stringify(body || {}),
    });
  },
};

export default apiIntegrations;
