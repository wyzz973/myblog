const POST_RE = /^\/p\/([^/]+)/;

/**
 * Determine which prompt mode applies to the current summon.
 * - greet: not on an article page
 * - summary_react: on article, no selection
 * - selection_explain: selection sits inside <pre>/<code>
 * - selection_qa: selection in plain prose
 */
export function detectMode({ inArticle, selection }) {
  if (!inArticle) return 'greet';
  if (!selection) return 'summary_react';
  const sel = typeof window !== 'undefined' ? window.getSelection?.() : null;
  if (!sel || sel.rangeCount === 0) return 'selection_qa';
  const ancestor = sel.getRangeAt(0).commonAncestorContainer;
  const inCode = ancestor.nodeType === 1
    ? ancestor.closest?.('pre, code') !== null
    : ancestor.parentElement?.closest?.('pre, code') !== null;
  return inCode ? 'selection_explain' : 'selection_qa';
}

/**
 * Inspect URL + current selection and return the payload to send to /api/pet/summon.
 * - On home: { mode: 'greet' }
 * - On article without selection: { post_id, mode: 'summary_react' }
 * - On article with selection >= 5 chars: { post_id, selection, mode: 'selection_explain' | 'selection_qa' }
 */
export function buildSummonPayload(options = 500) {
  const opts = typeof options === 'number' ? { maxSelectionChars: options } : (options || {});
  const maxChars = opts.maxSelectionChars ?? opts.maxChars ?? 500;
  const maxMessageChars = opts.maxMessageChars ?? 500;
  const m = window.location.pathname.match(POST_RE);
  const inArticle = m !== null;
  const sel = (window.getSelection?.()?.toString() || '').trim();
  const hasSelection = sel.length >= 5;
  const detectedMode = detectMode({ inArticle, selection: hasSelection ? sel : '' });
  const message = (opts.message || '').trim().slice(0, maxMessageChars);
  const mode = opts.mode || (message ? 'free_chat' : detectedMode);
  const payload = { mode };
  if (message) payload.message = message;
  if (opts.intent) payload.intent = opts.intent;
  if (opts.clientContext) payload.client_context = opts.clientContext;
  if (!inArticle) return payload;
  const post_id = decodeURIComponent(m[1]);
  payload.post_id = post_id;
  if (hasSelection) {
    payload.selection = sel.slice(0, maxChars);
  }
  return payload;
}
