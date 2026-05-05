import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api } from './client.js';

function jsonRes(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => 'application/json' },
    json: async () => body,
  };
}

beforeEach(() => {
  vi.useRealTimers();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api.posts.like', () => {
  it('POSTs to /api/posts/:id/like and returns the parsed body', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      jsonRes({ likes: 7, was_new: true }),
    );
    vi.stubGlobal('fetch', fetchSpy);

    const result = await api.posts.like('vps');
    expect(result).toEqual({ likes: 7, was_new: true });

    const [url, opts] = fetchSpy.mock.calls[0];
    expect(url).toBe('/api/posts/vps/like');
    expect(opts.method).toBe('POST');
  });

  it('throws on non-2xx so caller can fall back to the optimistic UI', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(jsonRes({ detail: 'rate limited' }, 429));
    vi.stubGlobal('fetch', fetchSpy);
    await expect(api.posts.like('vps')).rejects.toThrow();
  });
});

describe('api.posts.detail surfaces likes from server', () => {
  it('parses likes when the backend includes it', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      jsonRes({ id: 'vps', n: '012', title: 't', tag: 'devtools', date: '2026-04-25', read: '5 min', lang: 'en', summary: null, subtitle: null, tldr: null, body: [], word_count: 1000, likes: 42 }),
    );
    vi.stubGlobal('fetch', fetchSpy);
    const result = await api.posts.detail('vps');
    expect(result.likes).toBe(42);
  });
});
