import { describe, it, expect } from 'vitest';
import {
  parseFrontmatter,
  serializeFrontmatter,
  setFmField,
} from './frontmatter.js';

describe('parseFrontmatter', () => {
  it('reads scalar fields and body', () => {
    const md = `---
id: vps
n: "012"
title: VPS notes
status: published
featured: true
---

Hello body.`;
    const r = parseFrontmatter(md);
    expect(r.hasFm).toBe(true);
    expect(r.fm.id).toBe('vps');
    expect(r.fm.n).toBe('012');
    expect(r.fm.title).toBe('VPS notes');
    expect(r.fm.status).toBe('published');
    expect(r.fm.featured).toBe(true);
    expect(r.body.startsWith('Hello body.')).toBe(true);
  });

  it('returns empty fm when there is no frontmatter', () => {
    const r = parseFrontmatter('Just body, no fm');
    expect(r.hasFm).toBe(false);
    expect(r.fm).toEqual({});
    expect(r.body).toBe('Just body, no fm');
  });

  it('keeps unknown fields in raw[]', () => {
    const md = `---
id: x
custom_key: hello
---

body`;
    const r = parseFrontmatter(md);
    expect(r.fm.id).toBe('x');
    expect(r.raw).toContain('custom_key: hello');
  });
});

describe('serializeFrontmatter', () => {
  it('emits a line per known field, body separated by a blank line', () => {
    const out = serializeFrontmatter(
      { id: 'x', status: 'draft', featured: true },
      [],
      'body content',
    );
    expect(out).toBe('---\nid: x\nstatus: draft\nfeatured: true\n---\n\nbody content');
  });

  it('omits a boolean field when false', () => {
    const out = serializeFrontmatter({ id: 'x', featured: false }, [], 'b');
    expect(out).not.toMatch(/featured/);
  });

  it('quotes a value containing a colon', () => {
    const out = serializeFrontmatter({ id: 'x', title: 'foo: bar' }, [], '');
    expect(out).toMatch(/title: "foo: bar"/);
  });

  it('round-trips through parse → serialize without dropping fields', () => {
    const original = `---
id: vps
title: "v: ps"
tag: infra
date: 2026-04-25
lang: en
status: published
featured: true
private: true
---

body here`;
    const { fm, raw, body } = parseFrontmatter(original);
    const re = serializeFrontmatter(fm, raw, body);
    const parsed = parseFrontmatter(re);
    expect(parsed.fm.id).toBe('vps');
    expect(parsed.fm.title).toBe('v: ps');
    expect(parsed.fm.status).toBe('published');
    expect(parsed.fm.featured).toBe(true);
    expect(parsed.fm.private).toBe(true);
    expect(parsed.body).toBe('body here');
  });
});

describe('setFmField', () => {
  const md = `---
id: x
status: draft
---

body`;

  it('flips status from draft to published', () => {
    const out = setFmField(md, 'status', 'published');
    expect(out).toMatch(/status: published/);
    expect(out).not.toMatch(/status: draft/);
  });

  it('adds scheduled_at when missing', () => {
    const out = setFmField(md, 'scheduled_at', '2026-12-01T10:00');
    // ISO timestamps may be quoted by the colon heuristic — accept either form.
    expect(out).toMatch(/scheduled_at: "?2026-12-01T10:00"?/);
  });

  it('removes a boolean field when set to false', () => {
    const withFlag = setFmField(md, 'featured', true);
    expect(withFlag).toMatch(/featured: true/);
    const cleared = setFmField(withFlag, 'featured', false);
    expect(cleared).not.toMatch(/featured/);
  });

  it('preserves the body as-is', () => {
    const out = setFmField(md, 'featured', true);
    expect(out.endsWith('\n\nbody')).toBe(true);
  });
});
