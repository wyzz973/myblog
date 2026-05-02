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
export function buildSummonPayload(maxChars = 500) {
  const m = window.location.pathname.match(POST_RE);
  const inArticle = m !== null;
  const sel = (window.getSelection?.()?.toString() || '').trim();
  const hasSelection = sel.length >= 5;
  const mode = detectMode({ inArticle, selection: hasSelection ? sel : '' });
  if (!inArticle) return { mode };
  const post_id = decodeURIComponent(m[1]);
  if (hasSelection) {
    return { post_id, selection: sel.slice(0, maxChars), mode };
  }
  return { post_id, mode };
}
