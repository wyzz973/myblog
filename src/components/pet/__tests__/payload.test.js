import { describe, it, expect, beforeEach } from 'vitest';
import { buildSummonPayload } from '../payload.js';

describe('buildSummonPayload', () => {
  beforeEach(() => {
    // Mock window.location.pathname & window.getSelection
    Object.defineProperty(window, 'location', {
      value: { pathname: '/' }, writable: true,
    });
    window.getSelection = () => ({ toString: () => '' });
  });

  it('returns greet on home', () => {
    expect(buildSummonPayload(500)).toEqual({});
  });

  it('returns comment on article without selection', () => {
    window.location.pathname = '/p/abc123';
    expect(buildSummonPayload(500)).toEqual({ post_id: 'abc123' });
  });

  it('returns explain on article with selection >=5 chars', () => {
    window.location.pathname = '/p/abc123';
    window.getSelection = () => ({ toString: () => 'hello world' });
    expect(buildSummonPayload(500)).toEqual({ post_id: 'abc123', selection: 'hello world' });
  });

  it('truncates selection to maxChars', () => {
    window.location.pathname = '/p/abc';
    window.getSelection = () => ({ toString: () => 'x'.repeat(2000) });
    const out = buildSummonPayload(500);
    expect(out.selection.length).toBe(500);
  });

  it('ignores tiny selections (<5 chars)', () => {
    window.location.pathname = '/p/abc';
    window.getSelection = () => ({ toString: () => 'ab' });
    expect(buildSummonPayload(500)).toEqual({ post_id: 'abc' });
  });
});
