import { describe, it, expect } from 'vitest';
import {
  buildQueryFromState,
  buildStateFromQuery,
  intParser,
  statesEqual,
} from './searchParamsState.js';

const SCHEMA = [
  { key: 'status', defaultValue: 'all' },
  { key: 'q', defaultValue: '' },
  { key: 'page', defaultValue: 1, parse: intParser(1, 1) },
  { key: 'pageSize', defaultValue: 20, parse: intParser(1, 20) },
];

describe('buildQueryFromState', () => {
  it('omits values equal to default', () => {
    const params = buildQueryFromState(
      { status: 'all', q: '', page: 1, pageSize: 20 },
      SCHEMA,
    );
    expect(params.toString()).toBe('');
  });

  it('writes only non-default fields', () => {
    const params = buildQueryFromState(
      { status: 'draft', q: '', page: 3, pageSize: 20 },
      SCHEMA,
    );
    const s = params.toString();
    expect(s).toContain('status=draft');
    expect(s).toContain('page=3');
    expect(s).not.toContain('pageSize');
    expect(s).not.toContain('q=');
  });

  it('preserves spaces in q via URLSearchParams encoding', () => {
    const params = buildQueryFromState(
      { status: 'all', q: 'hello world', page: 1, pageSize: 20 },
      SCHEMA,
    );
    expect(params.get('q')).toBe('hello world');
    expect(params.toString()).toContain('q=hello+world');
  });
});

describe('buildStateFromQuery', () => {
  it('returns defaults for an empty query', () => {
    expect(buildStateFromQuery('', SCHEMA)).toEqual({
      status: 'all',
      q: '',
      page: 1,
      pageSize: 20,
    });
  });

  it('parses integers via parse fn', () => {
    expect(buildStateFromQuery('page=4&pageSize=50', SCHEMA)).toEqual({
      status: 'all',
      q: '',
      page: 4,
      pageSize: 50,
    });
  });

  it('falls back to default on garbage int', () => {
    expect(buildStateFromQuery('page=abc', SCHEMA)).toEqual({
      status: 'all',
      q: '',
      page: 1,
      pageSize: 20,
    });
  });

  it('round-trips through buildQueryFromState', () => {
    const state = { status: 'published', q: 'rust', page: 2, pageSize: 50 };
    const params = buildQueryFromState(state, SCHEMA);
    const back = buildStateFromQuery(params, SCHEMA);
    expect(back).toEqual(state);
  });
});

describe('intParser', () => {
  it('accepts positive integers', () => {
    expect(intParser()('7')).toBe(7);
  });
  it('rejects below min', () => {
    expect(intParser(2, 5)('1')).toBe(5);
  });
  it('rejects NaN', () => {
    expect(intParser()('abc')).toBe(1);
  });
});

describe('statesEqual', () => {
  it('true when every schema field matches', () => {
    expect(
      statesEqual(
        { status: 'all', q: '', page: 1, pageSize: 20 },
        { status: 'all', q: '', page: 1, pageSize: 20 },
        SCHEMA,
      ),
    ).toBe(true);
  });
  it('false on any divergence', () => {
    expect(
      statesEqual(
        { status: 'all', q: '', page: 1, pageSize: 20 },
        { status: 'draft', q: '', page: 1, pageSize: 20 },
        SCHEMA,
      ),
    ).toBe(false);
  });
});
