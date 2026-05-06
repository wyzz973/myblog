import { describe, it, expect, beforeEach } from 'vitest';
import { setDocumentMeta, restoreDocumentMeta } from './documentMeta.js';

beforeEach(() => {
  document.head.innerHTML = '<title>start</title>';
});

describe('documentMeta.setDocumentMeta', () => {
  it('sets title + og:title + twitter:title', () => {
    setDocumentMeta({ title: 'Hello', description: 'World' });
    expect(document.title).toBe('Hello');
    expect(document.querySelector('meta[property="og:title"]').getAttribute('content')).toBe('Hello');
    expect(document.querySelector('meta[name="twitter:title"]').getAttribute('content')).toBe('Hello');
  });
  it('sets og:description / twitter:description / meta description', () => {
    setDocumentMeta({ title: 'A', description: 'B' });
    expect(document.querySelector('meta[property="og:description"]').getAttribute('content')).toBe('B');
    expect(document.querySelector('meta[name="twitter:description"]').getAttribute('content')).toBe('B');
    expect(document.querySelector('meta[name="description"]').getAttribute('content')).toBe('B');
  });
  it('respects type=article / website', () => {
    setDocumentMeta({ title: 'A', description: 'B', type: 'article' });
    expect(document.querySelector('meta[property="og:type"]').getAttribute('content')).toBe('article');
    setDocumentMeta({ title: 'C', description: 'D' });
    expect(document.querySelector('meta[property="og:type"]').getAttribute('content')).toBe('website');
  });
  it('sets og:image / twitter:image only when image is provided', () => {
    setDocumentMeta({ title: 'A', description: 'B' });
    expect(document.querySelector('meta[property="og:image"]')).toBeNull();
    setDocumentMeta({ title: 'A', description: 'B', image: '/cover.png' });
    expect(document.querySelector('meta[property="og:image"]').getAttribute('content')).toBe('/cover.png');
  });
  it('falls back to defaults when fields missing', () => {
    setDocumentMeta({});
    expect(document.title).toBe('myblog');
    expect(document.querySelector('meta[property="og:title"]').getAttribute('content')).toBe('myblog');
  });
});

describe('documentMeta.restoreDocumentMeta', () => {
  it('resets og/twitter meta to defaults', () => {
    const prev = setDocumentMeta({ title: 'page', description: 'desc' });
    restoreDocumentMeta(prev);
    expect(document.querySelector('meta[property="og:title"]').getAttribute('content')).toBe('myblog');
    expect(document.querySelector('meta[name="twitter:description"]').getAttribute('content'))
      .toBe('A self-hosted personal blog.');
  });
});
