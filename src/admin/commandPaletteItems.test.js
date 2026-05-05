import { describe, it, expect, vi } from 'vitest';
import {
  buildPaletteItems,
  filterPaletteItems,
  groupBySection,
} from './commandPaletteItems.js';

const NAV = [
  {
    n: '01',
    label: '运营中枢',
    items: [
      { to: '/admin/dashboard', label: '仪表盘' },
      { to: '/admin/inbox', label: '收件箱' },
    ],
  },
  {
    n: '02',
    label: '内容',
    items: [
      { to: '/admin/posts', label: '文章' },
      { to: '/admin/media', label: '媒体' },
    ],
  },
];

const POSTS = [
  { id: 'vps', title: 'VPS 折腾记', tag: 'devops' },
  { id: 'react', title: 'React 心智模型', tag: 'frontend' },
];

function makeRunners() {
  return {
    go: vi.fn(),
    newPost: vi.fn(),
    openPost: vi.fn(),
    copyToken: vi.fn(),
    openPublic: vi.fn(),
    logout: vi.fn(),
  };
}

describe('buildPaletteItems', () => {
  it('puts nav, cmd, post items in that order', () => {
    const runners = makeRunners();
    const items = buildPaletteItems({ navGroups: NAV, posts: POSTS, runners });
    const types = items.map((i) => i.type);
    expect(types.indexOf('nav')).toBe(0);
    expect(types.lastIndexOf('nav')).toBeLessThan(types.indexOf('cmd'));
    expect(types.lastIndexOf('cmd')).toBeLessThan(types.indexOf('post'));
  });

  it('hides the current path from the nav section', () => {
    const items = buildPaletteItems({
      navGroups: NAV,
      posts: [],
      runners: makeRunners(),
      currentPath: '/admin/dashboard',
    });
    const labels = items.filter((i) => i.type === 'nav').map((i) => i.label);
    expect(labels).not.toContain('仪表盘');
    expect(labels).toContain('收件箱');
  });

  it('every nav item carries its group number + label as sub', () => {
    const items = buildPaletteItems({
      navGroups: NAV,
      posts: [],
      runners: makeRunners(),
    });
    const inbox = items.find((i) => i.label === '收件箱');
    expect(inbox.sub).toBe('01 · 运营中枢');
  });

  it('post items show id + tag in sub', () => {
    const items = buildPaletteItems({
      navGroups: [],
      posts: POSTS,
      runners: makeRunners(),
    });
    const post = items.find((i) => i.type === 'post' && i.label === 'VPS 折腾记');
    expect(post.sub).toBe('id: vps · devops');
  });

  it('runs the right runner on activation', () => {
    const runners = makeRunners();
    const items = buildPaletteItems({ navGroups: NAV, posts: POSTS, runners });
    const inbox = items.find((i) => i.label === '收件箱');
    inbox.run();
    expect(runners.go).toHaveBeenCalledWith('/admin/inbox');

    const newPost = items.find((i) => i.label === '新建文章');
    newPost.run();
    expect(runners.newPost).toHaveBeenCalledTimes(1);

    const post = items.find((i) => i.type === 'post');
    post.run();
    expect(runners.openPost).toHaveBeenCalledWith('vps');
  });
});

describe('filterPaletteItems', () => {
  const runners = makeRunners();
  const items = buildPaletteItems({ navGroups: NAV, posts: POSTS, runners });

  it('returns all items for empty query', () => {
    expect(filterPaletteItems(items, '').length).toBe(items.length);
  });

  it('matches labels case-insensitively', () => {
    const r = filterPaletteItems(items, 'VPS');
    expect(r.some((i) => i.label === 'VPS 折腾记')).toBe(true);
  });

  it('matches sub strings (id / group label)', () => {
    const r = filterPaletteItems(items, '内容');
    expect(r.every((i) => i.sub?.includes('内容') || i.label.includes('内容'))).toBe(true);
    expect(r.length).toBeGreaterThanOrEqual(2); // 文章 + 媒体
  });

  it('returns empty array when nothing matches', () => {
    expect(filterPaletteItems(items, 'zzzzznever').length).toBe(0);
  });
});

describe('groupBySection', () => {
  it('groups items by type and preserves global indexes', () => {
    const runners = makeRunners();
    const items = buildPaletteItems({ navGroups: NAV, posts: POSTS, runners });
    const grouped = groupBySection(items);
    expect(grouped.nav.length + grouped.cmd.length + grouped.post.length).toBe(items.length);
    grouped.nav.forEach(({ idx }, i) => expect(idx).toBe(i));
    const firstCmd = grouped.cmd[0];
    expect(firstCmd.idx).toBe(grouped.nav.length);
  });
});
