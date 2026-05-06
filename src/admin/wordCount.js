// Frontend word count + reading-time estimator. Mirrors the backend's
// markdown_pipeline.compute_derived (services/markdown_pipeline.py) so
// the admin's live counter matches what the post will end up with after
// save: words = ASCII word matches, cjk = single-char CJK matches, total
// = words + cjk, read = max(1, ceil(total / 240)) minutes.
//
// We strip the YAML frontmatter and a few markdown syntax tokens before
// counting so block fences / list bullets don't inflate the number.

const WORD_RE = /[A-Za-z0-9_]+/g;
const CJK_RE = /[一-鿿]/g;

export function stripFrontmatter(md) {
  if (typeof md !== 'string') return '';
  const m = md.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!m) return md;
  return md.slice(m[0].length);
}

// Cheap markdown → plaintext. We don't need a real parser; the goal is
// to drop fence markers, list bullets, link syntax wrappers, image alt
// brackets and table pipes so they don't add fake words.
export function mdToPlain(md) {
  if (typeof md !== 'string') return '';
  let s = md;
  // fenced code blocks: keep the inner text (counts toward words)
  s = s.replace(/```[a-z0-9_-]*\r?\n/gi, '\n').replace(/```/g, '');
  // images: ![alt](url) → alt
  s = s.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1');
  // links: [text](url) → text
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  // setext / atx headings markers
  s = s.replace(/^#{1,6}\s+/gm, '');
  // list bullets / quote / hr
  s = s.replace(/^\s*([-*+>]|\d+\.)\s+/gm, '');
  // emphasis / inline code wrappers (keep the chars between)
  s = s.replace(/[*_`~]/g, '');
  // table pipes
  s = s.replace(/\|/g, ' ');
  return s;
}

export function countWords(markdown) {
  const plain = mdToPlain(stripFrontmatter(markdown));
  const words = (plain.match(WORD_RE) || []).length;
  const cjk = (plain.match(CJK_RE) || []).length;
  return words + cjk;
}

export function readingMinutes(count) {
  if (!Number.isFinite(count) || count < 1) return 1;
  return Math.max(1, Math.ceil(count / 240));
}
