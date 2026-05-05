// Cursor-aware string insertion for the Posts editor's "insert image"
// flow. Pure functions so they can be unit-tested without React.

/**
 * Insert `text` into `source` at the [start..end] cursor selection.
 * Returns { value, cursor } where cursor points just past the inserted
 * text. start/end can refer to the same position (no selection).
 */
export function insertAt(source, start, end, text) {
  const s = source ?? '';
  const a = clamp(Math.min(start, end), 0, s.length);
  const b = clamp(Math.max(start, end), 0, s.length);
  const value = s.slice(0, a) + text + s.slice(b);
  return { value, cursor: a + text.length };
}

/**
 * Build the markdown image directive for a media item. Falls back to a
 * sensible alt when none is provided. Always emits a single trailing
 * newline so consecutive insertions remain block-separated.
 */
export function buildImageMarkdown(item) {
  if (!item) return '';
  const alt = (item.alt || item.filename || '').trim();
  const path = item.url || (item.storage_path ? `/media/${item.storage_path}` : '');
  if (!path) return '';
  return `![${alt}](${path})\n`;
}

function clamp(n, lo, hi) {
  if (Number.isNaN(n)) return lo;
  return Math.min(hi, Math.max(lo, n));
}
