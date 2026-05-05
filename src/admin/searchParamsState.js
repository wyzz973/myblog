// Pure helpers for declarative querystring round-tripping.
// Pages use the `useSyncedSearchParams` hook (in useSyncedSearchParams.js)
// which delegates encoding / decoding here.

// Field schema:
//   { key: 'status', defaultValue: 'all', parse?: (v)=>any, serialize?: (v)=>string }
// `parse` runs on the URL string before storing into state; `serialize`
// runs on state before writing to the URL. If a value equals
// `defaultValue` it is *omitted* from the URL — keeps URLs clean.

export function buildQueryFromState(state, schema) {
  const params = new URLSearchParams();
  for (const f of schema) {
    const v = state[f.key];
    if (v === undefined || v === null || v === '') continue;
    if (Object.is(v, f.defaultValue)) continue;
    const out = f.serialize ? f.serialize(v) : String(v);
    if (out === '' || out === undefined || out === null) continue;
    params.set(f.key, out);
  }
  return params;
}

export function buildStateFromQuery(query, schema) {
  const params = query instanceof URLSearchParams
    ? query
    : new URLSearchParams(query || '');
  const out = {};
  for (const f of schema) {
    const raw = params.get(f.key);
    if (raw === null || raw === '') {
      out[f.key] = f.defaultValue;
    } else {
      try {
        out[f.key] = f.parse ? f.parse(raw) : raw;
      } catch {
        out[f.key] = f.defaultValue;
      }
    }
  }
  return out;
}

// True iff state would serialize to the same query string as `current`,
// useful for skipping no-op history pushes.
export function statesEqual(a, b, schema) {
  for (const f of schema) {
    if (!Object.is(a[f.key], b[f.key])) return false;
  }
  return true;
}

// Common parsers / serializers — small enough to inline, but DRY when
// many pages share the same shape.
export const intParser = (min = 1, fallback = 1) => (v) => {
  const n = parseInt(v, 10);
  if (Number.isNaN(n) || n < min) return fallback;
  return n;
};
