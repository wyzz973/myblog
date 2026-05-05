// Admin integrations API client.
import { adminRequest } from './admin.js';

function req(path, opts = {}) {
  return adminRequest(path, opts);
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
  getProvider(name) {
    return req(`/integrations/${encodeURIComponent(name)}`);
  },
  putProvider(name, { token, model }) {
    return req(`/integrations/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify({ token, model: model || null }),
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
