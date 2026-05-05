import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Install a deterministic in-memory localStorage before importing admin.js
// (jsdom's default fires a confusing warning and can drop writes).
const _ls = new Map();
const memLocalStorage = {
  getItem: (k) => (_ls.has(k) ? _ls.get(k) : null),
  setItem: (k, v) => { _ls.set(k, String(v)); },
  removeItem: (k) => { _ls.delete(k); },
  clear: () => { _ls.clear(); },
};
Object.defineProperty(globalThis, 'localStorage', {
  value: memLocalStorage,
  configurable: true,
});

const {
  adminRequest,
  jwtExpiresAt,
  setOnUnauthorized,
  setToken,
  getToken,
  clearToken,
  tryRefresh,
  __resetForTests,
} = await import('./admin.js');

function jsonRes(body, status = 200, headers = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (k) => (k.toLowerCase() === 'content-type' ? 'application/json' : headers[k] || null),
    },
    json: async () => body,
  };
}

function jwt({ exp }) {
  // Minimal unsigned JWT: header.payload.signature (signature ignored client-side).
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${b64({ alg: 'none' })}.${b64({ exp })}.sig`;
}

beforeEach(() => {
  __resetForTests();
  vi.useRealTimers();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('jwtExpiresAt', () => {
  it('parses exp claim and returns ms', () => {
    const t = jwt({ exp: 1700000000 });
    expect(jwtExpiresAt(t)).toBe(1700000000 * 1000);
  });
  it('returns null on garbage', () => {
    expect(jwtExpiresAt('not-a-jwt')).toBeNull();
    expect(jwtExpiresAt('a.b')).toBeNull();
    expect(jwtExpiresAt(null)).toBeNull();
  });
});

describe('adminRequest 401 → refresh → retry', () => {
  it('retries the request after a successful refresh', async () => {
    setToken('stale');
    const fetchSpy = vi.fn()
      // First call: original request, 401
      .mockResolvedValueOnce(jsonRes({ detail: 'access expired' }, 401))
      // Second call: /auth/refresh, returns new access
      .mockResolvedValueOnce(jsonRes({ access: 'fresh', token_type: 'bearer', expires_in: 900 }))
      // Third call: retry of original request, 200
      .mockResolvedValueOnce(jsonRes({ ok: true }));
    vi.stubGlobal('fetch', fetchSpy);

    const result = await adminRequest('/dashboard');
    expect(result).toEqual({ ok: true });
    expect(fetchSpy).toHaveBeenCalledTimes(3);
    // After refresh, token is updated.
    expect(getToken()).toBe('fresh');
    // Auth header on retry uses the new token.
    const retryArgs = fetchSpy.mock.calls[2][1];
    expect(retryArgs.headers.Authorization).toBe('Bearer fresh');
  });

  it('calls onUnauthorized when refresh itself fails', async () => {
    setToken('stale');
    const onUnauth = vi.fn();
    setOnUnauthorized(onUnauth);
    const fetchSpy = vi.fn()
      .mockResolvedValueOnce(jsonRes({ detail: 'expired' }, 401)) // original
      .mockResolvedValueOnce(jsonRes({ detail: 'no cookie' }, 401)); // refresh
    vi.stubGlobal('fetch', fetchSpy);

    await expect(adminRequest('/dashboard')).rejects.toThrow();
    expect(onUnauth).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
  });

  it('does NOT retry an /auth/* path', async () => {
    setToken('any');
    const fetchSpy = vi.fn().mockResolvedValueOnce(jsonRes({ detail: 'bad creds' }, 401));
    vi.stubGlobal('fetch', fetchSpy);

    await expect(adminRequest('/auth/login', { method: 'POST' })).rejects.toThrow(/401/);
    // Only the one call — no retry, no refresh attempt.
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('coalesces concurrent 401s into one refresh', async () => {
    setToken('stale');
    let refreshCount = 0;
    const fetchSpy = vi.fn(async (url) => {
      if (typeof url === 'string' && url.includes('/auth/refresh')) {
        refreshCount += 1;
        return jsonRes({ access: 'fresh', token_type: 'bearer', expires_in: 900 });
      }
      // First call to each endpoint returns 401 (token stale); after token rotates, returns 200.
      const tok = getToken();
      if (tok === 'stale') return jsonRes({ detail: 'expired' }, 401);
      return jsonRes({ ok: true, url });
    });
    vi.stubGlobal('fetch', fetchSpy);

    const [a, b] = await Promise.all([
      adminRequest('/dashboard'),
      adminRequest('/posts'),
    ]);
    expect(a.ok).toBe(true);
    expect(b.ok).toBe(true);
    expect(refreshCount).toBe(1);
  });
});

describe('tryRefresh', () => {
  it('returns null on non-200 from refresh endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonRes({ detail: 'no cookie' }, 401)));
    const r = await tryRefresh();
    expect(r).toBeNull();
  });
});
