import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ActivityLog from './ActivityLog.jsx';

vi.mock('../api/activity.js', () => ({
  activityApi: {
    list: vi.fn(),
    recent: vi.fn(),
  },
}));

import { activityApi } from '../api/activity.js';

const SAMPLE = [
  {
    id: 1,
    type: 'auth.login.success',
    actor: 'me@example.com',
    target: null,
    meta: { ip: '127.0.0.1' },
    created_at: new Date(Date.now() - 60_000).toISOString(),
  },
  {
    id: 2,
    type: 'post.updated',
    actor: 'me@example.com',
    target: 'vps',
    meta: { fields: ['status', 'featured'] },
    created_at: new Date(Date.now() - 600_000).toISOString(),
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ActivityLog />
    </MemoryRouter>,
  );
}

describe('ActivityLog page', () => {
  it('lists items and renders meta on row click', async () => {
    activityApi.list.mockResolvedValueOnce(SAMPLE);
    renderPage();
    await waitFor(() => screen.getByTestId('row-1'));
    // Type appears both in the chip filter and the row cell — accept either.
    expect(screen.getAllByText('auth.login.success').length).toBeGreaterThan(0);
    expect(screen.getAllByText('post.updated').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByTestId('row-2'));
    await waitFor(() => screen.getByText(/"fields"/));
  });

  it('renders chips for seen types and re-fetches on filter pick', async () => {
    activityApi.list
      .mockResolvedValueOnce(SAMPLE)
      .mockResolvedValueOnce([SAMPLE[1]]);
    renderPage();
    await waitFor(() => screen.getByTestId('chip-post.updated'));
    fireEvent.click(screen.getByTestId('chip-post.updated'));
    await waitFor(() =>
      expect(activityApi.list).toHaveBeenLastCalledWith({
        types: ['post.updated'],
        limit: 50,
        offset: 0,
      }),
    );
  });

  it('shows empty state when no items', async () => {
    activityApi.list.mockResolvedValueOnce([]);
    renderPage();
    await waitFor(() => screen.getByText('[ 暂无事件 ]'));
  });

  it('paginates via 加载更多 when result is full page', async () => {
    const big = Array.from({ length: 50 }, (_, i) => ({
      id: i + 1,
      type: 'post.updated',
      actor: 'me',
      target: `p-${i}`,
      meta: {},
      created_at: new Date().toISOString(),
    }));
    activityApi.list.mockResolvedValueOnce(big).mockResolvedValueOnce([SAMPLE[0]]);
    renderPage();
    await waitFor(() => screen.getByText('加载更多'));
    fireEvent.click(screen.getByText('加载更多'));
    await waitFor(() =>
      expect(activityApi.list).toHaveBeenLastCalledWith({
        types: undefined,
        limit: 50,
        offset: 50,
      }),
    );
  });
});
