import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Layout, { pickNavCounters } from './Layout.jsx';

vi.mock('./AuthContext.jsx', () => ({
  useAuth: () => ({
    email: 'me@example.com',
    logout: vi.fn(),
  }),
}));

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/admin/*" element={<div>OUTLET</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('Layout sidebar IA', () => {
  it('renders six numbered groups', () => {
    renderAt('/admin/dashboard');
    for (const n of ['01', '02', '03', '04', '05', '06']) {
      const head = screen.getByTestId(`nav-group-${n}`);
      expect(head).toBeInTheDocument();
      // First child div is the heading row; assert it contains the number.
      expect(head.textContent).toContain(n);
    }
    // Group labels (the workflow shape we proposed in PRD §5.2).
    expect(screen.getAllByText('运营中枢').length).toBeGreaterThan(0);
    expect(screen.getAllByText('内容').length).toBeGreaterThan(0);
    expect(screen.getAllByText('观察').length).toBeGreaterThan(0);
    expect(screen.getAllByText('首页与品牌').length).toBeGreaterThan(0);
    expect(screen.getAllByText('宠物').length).toBeGreaterThan(0);
    expect(screen.getAllByText('系统').length).toBeGreaterThan(0);
  });

  it('keeps every existing route reachable from the sidebar', () => {
    renderAt('/admin/dashboard');
    const expected = [
      '仪表盘', '收件箱', '文章', '标签', '媒体', '近况', '项目',
      '数据分析', '评论',
      '站点身份', '联系方式', '主题',
      '宠物助手', '设置',
    ];
    for (const label of expected) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it('renders breadcrumb with group · group-name and leaf for /admin/posts', () => {
    renderAt('/admin/posts');
    const crumb = screen.getByTestId('breadcrumb');
    expect(crumb.textContent).toContain('admin');
    expect(crumb.textContent).toContain('02');
    expect(crumb.textContent).toContain('内容');
    expect(crumb.textContent).toContain('文章');
  });

  it('resolves a sub-path like /admin/posts/__new__ back to its group', () => {
    renderAt('/admin/posts/__new__');
    const crumb = screen.getByTestId('breadcrumb');
    expect(crumb.textContent).toContain('02');
    expect(crumb.textContent).toContain('文章');
  });

  it('renders only the ~/admin shell when path is unknown', () => {
    renderAt('/admin/unknown-route');
    const crumb = screen.getByTestId('breadcrumb');
    // No leaf appended for unmatched pages.
    expect(crumb.textContent).not.toContain('文章');
  });
});

// Task 48: per-route badge counters derived from /api/admin/dashboard.
describe('pickNavCounters', () => {
  it('maps comments.pending and posts.draft from a real dashboard payload', () => {
    const payload = {
      hits: {}, likes: {},
      comments: { total: 100, pending: 7 },
      posts: { published: 12, draft: 3, scheduled: 1 },
      media: { count: 4 },
    };
    const counters = pickNavCounters(payload);
    expect(counters['/admin/comments']).toBe(7);
    expect(counters['/admin/posts']).toBe(3);
  });

  it('returns zeros (not undefined) when the payload is missing fields', () => {
    const counters = pickNavCounters({});
    expect(counters['/admin/comments']).toBe(0);
    expect(counters['/admin/posts']).toBe(0);
  });

  it('returns an empty object for null/undefined input', () => {
    expect(pickNavCounters(null)).toEqual({});
    expect(pickNavCounters(undefined)).toEqual({});
  });

  it('does not surface inventory-only fields as counters', () => {
    const payload = {
      comments: { total: 100, pending: 0 },
      posts: { published: 12, draft: 0 },
      media: { count: 99 },
    };
    const counters = pickNavCounters(payload);
    // No keys for media / published — only the actionable ones (zero is fine).
    expect(Object.keys(counters).sort()).toEqual(['/admin/comments', '/admin/posts']);
  });
});
