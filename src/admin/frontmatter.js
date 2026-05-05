// Lightweight frontmatter helpers for the post editor's GUI ↔ YAML sync.
//
// Backend uses PyYAML for full parsing. The editor only needs a small
// scalar-line subset that backend can re-read: `key: value`, with an
// optional double-quoted value (so a colon in the title still parses).
// Booleans (`true`/`false`) and bare numbers/dates pass through.

const FENCE = /^---\s*$/;

// Recognized field types — used by the GUI strip and by setFmField to
// pick the right serialization. Anything not listed here is round-tripped
// as a raw string and left alone by the GUI.
export const KNOWN_FIELDS = {
  // identity / display
  id: 'string',
  n: 'quoted_string',
  title: 'string',
  subtitle: 'string',
  tag: 'string',
  date: 'string',
  lang: 'string',
  read: 'string',
  summary: 'string',
  tldr: 'string',
  // lifecycle (Task 3 surface)
  status: 'string',
  scheduled_at: 'string',
  featured: 'boolean',
  private: 'boolean',
  comments_enabled: 'boolean',
};

export const STATUS_VALUES = ['draft', 'published', 'scheduled'];

function quoteIfNeeded(s) {
  // Mirror the backend-friendly heuristic: quote whenever the value
  // contains a colon, hash, quote, backslash, or has leading/trailing
  // whitespace. Otherwise pass through bare.
  const str = String(s);
  if (/[:#"'\\]|^\s|\s$/.test(str)) return JSON.stringify(str);
  return str;
}

function unquoteScalar(raw) {
  const v = raw.trim();
  if (v.length >= 2 && ((v[0] === '"' && v[v.length - 1] === '"') ||
                        (v[0] === "'" && v[v.length - 1] === "'"))) {
    try {
      return JSON.parse(v.replace(/^'|'$/g, '"'));
    } catch {
      return v.slice(1, -1);
    }
  }
  return v;
}

function coerceValue(name, raw) {
  const t = KNOWN_FIELDS[name];
  if (t === 'boolean') {
    const s = unquoteScalar(raw).toLowerCase();
    if (s === 'true') return true;
    if (s === 'false') return false;
    return Boolean(s);
  }
  // strings (incl. quoted_string) flow as strings
  return unquoteScalar(raw);
}

function serializeLine(name, value) {
  const t = KNOWN_FIELDS[name] || 'string';
  if (value == null || value === '') return null;
  if (t === 'boolean') {
    return value === true ? `${name}: true` : null; // omit when false
  }
  if (t === 'quoted_string') {
    return `${name}: "${String(value).replace(/"/g, '\\"')}"`;
  }
  return `${name}: ${quoteIfNeeded(value)}`;
}

// Parse markdown into { fm: {known fields}, raw: [original lines], body }
// `raw` keeps the unrecognized lines so we don't drop user-added keys.
export function parseFrontmatter(md) {
  const text = md ?? '';
  const lines = text.split('\n');
  if (lines.length === 0 || !FENCE.test(lines[0])) {
    return { fm: {}, raw: [], body: text, hasFm: false };
  }
  let end = -1;
  for (let i = 1; i < lines.length; i += 1) {
    if (FENCE.test(lines[i])) {
      end = i;
      break;
    }
  }
  if (end === -1) return { fm: {}, raw: [], body: text, hasFm: false };

  const fm = {};
  const raw = [];
  for (let i = 1; i < end; i += 1) {
    const line = lines[i];
    const m = line.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$/);
    if (m) {
      const [, name, rest] = m;
      if (name in KNOWN_FIELDS) {
        fm[name] = coerceValue(name, rest);
      } else {
        raw.push(line);
      }
    } else {
      raw.push(line);
    }
  }
  // Body — strip exactly one leading blank that separates `---` from prose.
  let body = lines.slice(end + 1).join('\n');
  if (body.startsWith('\n')) body = body.slice(1);
  return { fm, raw, body, hasFm: true };
}

// Build a markdown string from a fm object, an array of unrecognized raw
// lines, and the body. Order of known fields is fixed (deterministic
// round-trip); raw lines come last in their original order.
const FIELD_ORDER = [
  'id',
  'n',
  'title',
  'subtitle',
  'tag',
  'date',
  'lang',
  'read',
  'summary',
  'tldr',
  'status',
  'scheduled_at',
  'featured',
  'private',
  'comments_enabled',
];

export function serializeFrontmatter(fm, raw, body) {
  const lines = ['---'];
  for (const name of FIELD_ORDER) {
    if (!(name in fm)) continue;
    const line = serializeLine(name, fm[name]);
    if (line !== null) lines.push(line);
  }
  for (const r of raw || []) lines.push(r);
  lines.push('---');
  // Single blank line between fence and body — required by the backend
  // ingest pipeline, dropped historically by a careless `.filter(Boolean)`.
  return `${lines.join('\n')}\n\n${body || ''}`;
}

// Convenience: read the current markdown, set one known field, return
// the new markdown. Setting a boolean to false removes the line; setting
// a string to '' or null also removes it.
export function setFmField(md, name, value) {
  const { fm, raw, body } = parseFrontmatter(md);
  const next = { ...fm };
  if (
    value === '' ||
    value == null ||
    (KNOWN_FIELDS[name] === 'boolean' && value === false)
  ) {
    delete next[name];
  } else {
    next[name] = value;
  }
  return serializeFrontmatter(next, raw, body);
}
