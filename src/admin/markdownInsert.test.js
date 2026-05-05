import { describe, it, expect } from 'vitest';
import { insertAt, buildImageMarkdown } from './markdownInsert.js';

describe('insertAt', () => {
  it('inserts at a caret (no selection)', () => {
    const out = insertAt('hello world', 5, 5, ' there');
    expect(out.value).toBe('hello there world');
    expect(out.cursor).toBe(11); // just past "hello there"
  });

  it('replaces a selection', () => {
    const out = insertAt('hello world', 6, 11, 'there');
    expect(out.value).toBe('hello there');
    expect(out.cursor).toBe(11);
  });

  it('handles a reversed selection (end < start)', () => {
    const out = insertAt('abcdef', 4, 1, 'X');
    expect(out.value).toBe('aXef');
    expect(out.cursor).toBe(2);
  });

  it('clamps positions out of range', () => {
    const out = insertAt('abc', -10, 999, 'Z');
    expect(out.value).toBe('Z');
    expect(out.cursor).toBe(1);
  });

  it('treats null source as empty', () => {
    const out = insertAt(null, 0, 0, 'hi');
    expect(out.value).toBe('hi');
    expect(out.cursor).toBe(2);
  });
});

describe('buildImageMarkdown', () => {
  it('uses alt when present', () => {
    const md = buildImageMarkdown({
      filename: 'pic.png',
      alt: 'A nice picture',
      url: '/media/abc/pic.png',
    });
    expect(md).toBe('![A nice picture](/media/abc/pic.png)\n');
  });

  it('falls back to filename when alt is missing', () => {
    const md = buildImageMarkdown({ filename: 'logo.svg', url: '/media/x/logo.svg' });
    expect(md).toBe('![logo.svg](/media/x/logo.svg)\n');
  });

  it('falls back to /media/<storage_path> when url is missing', () => {
    const md = buildImageMarkdown({
      filename: 'a.png',
      storage_path: 'a/b/c.png',
    });
    expect(md).toBe('![a.png](/media/a/b/c.png)\n');
  });

  it('returns empty string when no path is resolvable', () => {
    expect(buildImageMarkdown({ filename: 'x.png' })).toBe('');
    expect(buildImageMarkdown(null)).toBe('');
  });
});
