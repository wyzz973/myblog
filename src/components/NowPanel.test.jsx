import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

// Mock the hooks module before NowPanel imports it.
vi.mock('../api/hooks.js', () => ({ useNow: vi.fn() }));
import { useNow } from '../api/hooks.js';
import NowPanel from './NowPanel.jsx';

afterEach(() => cleanup());

describe('NowPanel', () => {
  it('renders nothing while loading', () => {
    useNow.mockReturnValue({ data: null, error: null, loading: true });
    const { container } = render(<NowPanel />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing on error', () => {
    useNow.mockReturnValue({ data: null, error: new Error('x'), loading: false });
    const { container } = render(<NowPanel />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when no current entry', () => {
    useNow.mockReturnValue({
      data: { current: null, history: [] },
      error: null,
      loading: false,
    });
    const { container } = render(<NowPanel />);
    expect(container.firstChild).toBeNull();
  });

  it('renders body markdown + listening + reading when current exists', () => {
    useNow.mockReturnValue({
      data: {
        current: {
          id: 1,
          body_md: 'today is **good**',
          listening: 'song',
          reading: 'book',
          is_current: true,
          created_at: new Date().toISOString(),
        },
        history: [],
      },
      error: null,
      loading: false,
    });
    render(<NowPanel />);
    expect(screen.getByTestId('now-panel')).toBeTruthy();
    // Markdown rendered to HTML
    const body = screen.getByTestId('now-panel').querySelector('.now-body');
    expect(body.innerHTML).toContain('<strong>good</strong>');
    expect(screen.getByText('song')).toBeTruthy();
    expect(screen.getByText('book')).toBeTruthy();
  });

  it('omits the meta strip when listening + reading are empty', () => {
    useNow.mockReturnValue({
      data: {
        current: {
          id: 1,
          body_md: 'minimal',
          listening: null,
          reading: null,
          is_current: true,
          created_at: new Date().toISOString(),
        },
        history: [],
      },
      error: null,
      loading: false,
    });
    const { container } = render(<NowPanel />);
    expect(container.querySelector('.now-meta')).toBeNull();
  });
});
