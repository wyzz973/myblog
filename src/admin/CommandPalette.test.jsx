import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import CommandPalette from './CommandPalette.jsx';

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
    items: [{ to: '/admin/posts', label: '文章' }],
  },
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

afterEach(() => cleanup());

describe('CommandPalette', () => {
  it('renders nothing when open=false', () => {
    const runners = makeRunners();
    render(
      <CommandPalette
        open={false}
        onClose={() => {}}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={runners}
      />,
    );
    expect(screen.queryByTestId('admin-palette')).toBeNull();
  });

  it('renders nav and cmd sections when posts have not loaded', () => {
    render(
      <CommandPalette
        open
        onClose={() => {}}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={makeRunners()}
      />,
    );
    expect(screen.getByTestId('admin-palette')).toBeTruthy();
    expect(screen.getByTestId('palette-section-nav')).toBeTruthy();
    expect(screen.getByTestId('palette-section-cmd')).toBeTruthy();
    // post section absent until loadPosts resolves
    expect(screen.queryByTestId('palette-section-post')).toBeNull();
  });

  it('filters items by query', () => {
    render(
      <CommandPalette
        open
        onClose={() => {}}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={makeRunners()}
      />,
    );
    const input = screen.getByTestId('palette-input');
    fireEvent.change(input, { target: { value: '收件' } });
    expect(screen.getByText('收件箱')).toBeTruthy();
    expect(screen.queryByText('文章')).toBeNull();
  });

  it('Enter runs the highlighted item', () => {
    const runners = makeRunners();
    const onClose = vi.fn();
    render(
      <CommandPalette
        open
        onClose={onClose}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={runners}
      />,
    );
    const input = screen.getByTestId('palette-input');
    fireEvent.change(input, { target: { value: '收件' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(runners.go).toHaveBeenCalledWith('/admin/inbox');
    expect(onClose).toHaveBeenCalled();
  });

  it('ArrowDown moves selection then Enter runs the new target', () => {
    const runners = makeRunners();
    render(
      <CommandPalette
        open
        onClose={() => {}}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={runners}
      />,
    );
    const input = screen.getByTestId('palette-input');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    // First nav (after filtering current page out) is 收件箱; after one
    // ArrowDown we should be on 文章.
    expect(runners.go).toHaveBeenCalledWith('/admin/posts');
  });

  it('Escape calls onClose', () => {
    const onClose = vi.fn();
    render(
      <CommandPalette
        open
        onClose={onClose}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={makeRunners()}
      />,
    );
    fireEvent.keyDown(screen.getByTestId('palette-input'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('shows empty placeholder when nothing matches', () => {
    render(
      <CommandPalette
        open
        onClose={() => {}}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={makeRunners()}
      />,
    );
    fireEvent.change(screen.getByTestId('palette-input'), {
      target: { value: 'zzznever' },
    });
    expect(screen.getByText(/没有匹配项/)).toBeTruthy();
  });

  it('loads posts via loadPosts when opened', async () => {
    const loadPosts = vi.fn().mockResolvedValue([
      { id: 'vps', title: 'VPS 折腾记', tag: 'devops' },
    ]);
    render(
      <CommandPalette
        open
        onClose={() => {}}
        navGroups={NAV}
        currentPath="/admin/dashboard"
        runners={makeRunners()}
        loadPosts={loadPosts}
      />,
    );
    await new Promise((r) => setTimeout(r, 0));
    await new Promise((r) => setTimeout(r, 0));
    expect(loadPosts).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('VPS 折腾记')).toBeTruthy();
  });
});
