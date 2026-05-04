// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { buildSummonPayload, detectMode } from './payload.js';

function selectNode(el) {
  const range = document.createRange();
  range.selectNodeContents(el);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}

describe('detectMode', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    window.getSelection().removeAllRanges();
  });

  it('returns greet when not on an article', () => {
    expect(detectMode({ inArticle: false, selection: '' })).toBe('greet');
  });

  it('returns summary_react on article with no selection', () => {
    expect(detectMode({ inArticle: true, selection: '' })).toBe('summary_react');
  });

  it('returns selection_qa for prose selection', () => {
    document.body.innerHTML = '<p id="t">hello world</p>';
    selectNode(document.getElementById('t'));
    expect(detectMode({ inArticle: true, selection: 'hello' })).toBe('selection_qa');
  });

  it('returns selection_explain for code selection inside <pre>', () => {
    document.body.innerHTML = '<pre id="c"><code>const x = 1</code></pre>';
    selectNode(document.querySelector('#c code'));
    expect(detectMode({ inArticle: true, selection: 'const x = 1' })).toBe('selection_explain');
  });

  it('returns selection_qa when selection has no live Range', () => {
    expect(detectMode({ inArticle: true, selection: 'whatever' })).toBe('selection_qa');
  });
});

describe('buildSummonPayload', () => {
  let originalLocation;

  beforeEach(() => {
    originalLocation = window.location;
    document.body.innerHTML = '';
    window.getSelection().removeAllRanges();
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true });
  });

  function setPath(path) {
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, pathname: path },
      writable: true,
    });
  }

  it('returns greet payload on home', () => {
    setPath('/');
    expect(buildSummonPayload()).toEqual({ mode: 'greet' });
  });

  it('returns summary_react when on article with no selection', () => {
    setPath('/p/hello-world');
    expect(buildSummonPayload()).toEqual({ post_id: 'hello-world', mode: 'summary_react' });
  });

  it('returns selection_qa with truncated selection on article with prose selection', () => {
    setPath('/p/hello');
    document.body.innerHTML = '<p id="t">' + 'a'.repeat(700) + '</p>';
    selectNode(document.getElementById('t'));
    const payload = buildSummonPayload(500);
    expect(payload.post_id).toBe('hello');
    expect(payload.mode).toBe('selection_qa');
    expect(payload.selection.length).toBe(500);
  });

  it('returns selection_explain with selection in <pre><code>', () => {
    setPath('/p/post');
    document.body.innerHTML = '<pre><code id="c">function foo() {}</code></pre>';
    selectNode(document.getElementById('c'));
    const payload = buildSummonPayload();
    expect(payload.mode).toBe('selection_explain');
    expect(payload.post_id).toBe('post');
  });

  it('drops selections below 5 chars (still returns summary_react)', () => {
    setPath('/p/post');
    document.body.innerHTML = '<p id="t">hi</p>';
    selectNode(document.getElementById('t'));
    expect(buildSummonPayload()).toEqual({ post_id: 'post', mode: 'summary_react' });
  });

  it('uses free_chat mode when message is provided on home', () => {
    setPath('/');
    expect(buildSummonPayload({ message: 'hello pet' })).toEqual({
      mode: 'free_chat',
      message: 'hello pet',
    });
  });

  it('keeps post, selection, intent, and client context with message', () => {
    setPath('/p/post');
    document.body.innerHTML = '<pre><code id="c">const cleanup = true</code></pre>';
    selectNode(document.getElementById('c'));
    const payload = buildSummonPayload({
      message: 'why cleanup?',
      intent: 'ask_selection',
      clientContext: { page_type: 'post', read_progress: 50, ignored: 'client-only' },
    });
    expect(payload).toMatchObject({
      post_id: 'post',
      mode: 'free_chat',
      message: 'why cleanup?',
      intent: 'ask_selection',
      client_context: { page_type: 'post', read_progress: 50, ignored: 'client-only' },
    });
    expect(payload.selection).toContain('cleanup');
  });

  it('allows explicit smart modes to override message default', () => {
    setPath('/p/post');
    const payload = buildSummonPayload({ message: 'done', mode: 'article_finished' });
    expect(payload.mode).toBe('article_finished');
    expect(payload.message).toBe('done');
  });
});
