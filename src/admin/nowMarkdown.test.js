import { describe, it, expect } from 'vitest';
import { renderNowMarkdown } from './nowMarkdown.js';

describe('renderNowMarkdown', () => {
  it('returns empty string for empty input', () => {
    expect(renderNowMarkdown('')).toBe('');
    expect(renderNowMarkdown(null)).toBe('');
  });

  it('renders a paragraph', () => {
    expect(renderNowMarkdown('hello world')).toBe('<p>hello world</p>');
  });

  it('renders bold and italic', () => {
    const out = renderNowMarkdown('this is **bold** and *italic*');
    expect(out).toContain('<strong>bold</strong>');
    expect(out).toContain('<em>italic</em>');
  });

  it('renders inline code', () => {
    expect(renderNowMarkdown('use `npm install`')).toContain('<code>npm install</code>');
  });

  it('renders a list with - markers', () => {
    const out = renderNowMarkdown('- one\n- two');
    expect(out).toContain('<ul>');
    expect(out).toContain('<li>one</li>');
    expect(out).toContain('<li>two</li>');
  });

  it('separates paragraphs by blank lines', () => {
    const out = renderNowMarkdown('first\n\nsecond');
    expect(out).toContain('<p>first</p>');
    expect(out).toContain('<p>second</p>');
  });

  it('escapes HTML in raw input', () => {
    const out = renderNowMarkdown('<script>alert(1)</script>');
    expect(out).not.toContain('<script>');
    expect(out).toContain('&lt;script&gt;');
  });

  it('linkifies bare http URLs', () => {
    const out = renderNowMarkdown('see https://example.com please');
    expect(out).toContain('<a href="https://example.com"');
    expect(out).toContain('target="_blank"');
  });

  it('list followed by paragraph', () => {
    const out = renderNowMarkdown('- one\n\nafter');
    expect(out).toMatch(/<ul>.*<\/ul>\s*<p>after<\/p>/s);
  });
});
