import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  JUMP_MAP,
  SHORTCUT_GROUPS,
  resolveJump,
  shouldIgnoreEvent,
} from './keyboardShortcuts.js';

function makeEvent({ tag = 'BODY', type, ctrl, meta, alt, contentEditable } = {}) {
  const target =
    tag === 'BODY'
      ? document.body
      : Object.assign(document.createElement(tag.toLowerCase()), {
          ...(type ? { type } : {}),
        });
  if (contentEditable) {
    target.setAttribute('contenteditable', 'true');
    Object.defineProperty(target, 'isContentEditable', { value: true });
  }
  return {
    target,
    metaKey: !!meta,
    ctrlKey: !!ctrl,
    altKey: !!alt,
  };
}

describe('keyboardShortcuts.JUMP_MAP', () => {
  it('contains all expected nav letters', () => {
    expect(Object.keys(JUMP_MAP).sort()).toEqual(
      ['a', 'c', 'd', 'e', 'i', 'm', 'n', 'p', 's', 't'],
    );
  });

  it('every entry has a route and a label', () => {
    Object.values(JUMP_MAP).forEach((v) => {
      expect(v.to.startsWith('/admin/')).toBe(true);
      expect(v.label.length).toBeGreaterThan(0);
    });
  });
});

describe('SHORTCUT_GROUPS', () => {
  it('exposes 全局 / 跳转 / 列表页 groups', () => {
    const scopes = SHORTCUT_GROUPS.map((g) => g.scope);
    expect(scopes).toContain('全局');
    expect(scopes.find((s) => s.includes('跳转'))).toBeTruthy();
    expect(scopes.find((s) => s.includes('列表页'))).toBeTruthy();
  });

  it('jump group enumerates all JUMP_MAP entries', () => {
    const jumpGroup = SHORTCUT_GROUPS.find((g) => g.scope.includes('跳转'));
    expect(jumpGroup.items.length).toBe(Object.keys(JUMP_MAP).length);
  });
});

describe('resolveJump', () => {
  it('returns the entry for a valid letter, case-insensitively', () => {
    expect(resolveJump('p').to).toBe('/admin/posts');
    expect(resolveJump('P').to).toBe('/admin/posts');
  });
  it('returns null for unknown letters', () => {
    expect(resolveJump('z')).toBeNull();
    expect(resolveJump('')).toBeNull();
    expect(resolveJump(null)).toBeNull();
  });
});

describe('shouldIgnoreEvent', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('ignores when modifier keys are held', () => {
    expect(shouldIgnoreEvent(makeEvent({ meta: true }))).toBe(true);
    expect(shouldIgnoreEvent(makeEvent({ ctrl: true }))).toBe(true);
    expect(shouldIgnoreEvent(makeEvent({ alt: true }))).toBe(true);
  });

  it('ignores when typing in textarea / text input', () => {
    expect(shouldIgnoreEvent(makeEvent({ tag: 'TEXTAREA' }))).toBe(true);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'INPUT', type: 'text' }))).toBe(true);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'INPUT', type: 'search' }))).toBe(true);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'SELECT' }))).toBe(true);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'DIV', contentEditable: true }))).toBe(true);
  });

  it('does NOT ignore for checkbox / button / body', () => {
    expect(shouldIgnoreEvent(makeEvent({ tag: 'INPUT', type: 'checkbox' }))).toBe(false);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'BUTTON' }))).toBe(false);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'BODY' }))).toBe(false);
  });

  it('ignores when palette is open', () => {
    const palette = document.createElement('div');
    palette.setAttribute('data-testid', 'admin-palette');
    document.body.appendChild(palette);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'BODY' }))).toBe(true);
  });

  it('ignores when a [data-shortcut-suppress=true] surface is mounted', () => {
    const modal = document.createElement('div');
    modal.setAttribute('data-shortcut-suppress', 'true');
    document.body.appendChild(modal);
    expect(shouldIgnoreEvent(makeEvent({ tag: 'BODY' }))).toBe(true);
  });
});
