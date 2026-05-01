const POST_RE = /^\/p\/([^/]+)/;

/**
 * Inspect URL + current selection and return the payload to send to /api/pet/summon.
 * - On home: {}
 * - On article without selection: {post_id}
 * - On article with selection >= 5 chars: {post_id, selection: <truncated>}
 */
export function buildSummonPayload(maxChars = 500) {
  const m = window.location.pathname.match(POST_RE);
  if (!m) return {};
  const post_id = decodeURIComponent(m[1]);
  const sel = (window.getSelection?.()?.toString() || '').trim();
  if (sel.length >= 5) {
    return { post_id, selection: sel.slice(0, maxChars) };
  }
  return { post_id };
}
