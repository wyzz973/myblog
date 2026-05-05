import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Inbox from './Inbox.jsx';

vi.mock('../api/comments.js', () => ({
  commentsApi: { list: vi.fn() },
}));
vi.mock('../api/pet.js', () => ({
  apiPet: { listConversations: vi.fn() },
}));
vi.mock('../api/activity.js', () => ({
  activityApi: { list: vi.fn() },
}));

import { commentsApi } from '../api/comments.js';
import { apiPet } from '../api/pet.js';
import { activityApi } from '../api/activity.js';

beforeEach(() => {
  vi.clearAllMocks();
});

function renderInbox() {
  return render(
    <MemoryRouter>
      <Inbox />
    </MemoryRouter>,
  );
}

describe('Inbox page', () => {
  it('renders three sections from three endpoints', async () => {
    commentsApi.list.mockResolvedValueOnce([
      {
        id: 1, post_id: 'vps', post_title: 'VPS', who: 'alice',
        body: 'hi there', created_at: new Date().toISOString(),
      },
    ]);
    apiPet.listConversations.mockResolvedValueOnce({
      items: [
        {
          visitor_hash: 'abcdef0123', species: 'cat', message_count: 5,
          last_msg_at: new Date().toISOString(), last_reply_preview: 'hello',
        },
      ],
    });
    activityApi.list.mockResolvedValueOnce([
      {
        id: 99, type: 'auth.login.fail', actor: 'me@example.com',
        meta: { ip: '127.0.0.1', reason: 'password' },
        created_at: new Date().toISOString(),
      },
    ]);
    renderInbox();
    await waitFor(() => screen.getByTestId('inbox-comments'));
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText(/abcdef0123/)).toBeInTheDocument();
    expect(screen.getByText('auth.login.fail')).toBeInTheDocument();
  });

  it('shows empty placeholders when an endpoint returns []', async () => {
    commentsApi.list.mockResolvedValueOnce([]);
    apiPet.listConversations.mockResolvedValueOnce({ items: [] });
    activityApi.list.mockResolvedValueOnce([]);
    renderInbox();
    await waitFor(() => screen.getByTestId('inbox-comments'));
    expect(screen.getByText('[ 暂无 pending 评论 ]')).toBeInTheDocument();
    expect(screen.getByText('[ 暂无对话 ]')).toBeInTheDocument();
    expect(screen.getByText('[ 暂无登录事件 ]')).toBeInTheDocument();
  });

  it('marks all read clears the new-count badge', async () => {
    commentsApi.list.mockResolvedValueOnce([
      { id: 1, who: 'alice', body: 'x', created_at: new Date().toISOString(), post_id: 'vps' },
    ]);
    apiPet.listConversations.mockResolvedValueOnce({ items: [] });
    activityApi.list.mockResolvedValueOnce([]);
    renderInbox();
    await waitFor(() => screen.getByTestId('inbox-comments'));
    // At first the new comment is fresher than last_seen
    const badge = screen.getByTestId('inbox-new-count');
    expect(badge.textContent).toMatch(/新/);
    fireEvent.click(screen.getByTestId('mark-all-read'));
    await waitFor(() => expect(badge.textContent).toBe('已全部查看'));
  });

  it('renders a left accent stripe on rows newer than last_seen', async () => {
    // No localStorage write — readLastSeen falls back to 0, so all rows
    // with a real timestamp count as new.
    commentsApi.list.mockResolvedValueOnce([
      { id: 7, who: 'bob', body: 'recent', created_at: new Date().toISOString(), post_id: 'vps' },
    ]);
    apiPet.listConversations.mockResolvedValueOnce({ items: [] });
    activityApi.list.mockResolvedValueOnce([]);
    renderInbox();
    await waitFor(() => screen.getByText('bob'));
    // The row's parent div carries the data-isnew flag we wired.
    const newRows = document.querySelectorAll('[data-isnew=true]');
    expect(newRows.length).toBeGreaterThan(0);
  });

  it('continues rendering when one endpoint fails (graceful degradation)', async () => {
    commentsApi.list.mockResolvedValueOnce([
      { id: 1, who: 'alice', body: 'x', created_at: new Date().toISOString(), post_id: 'vps' },
    ]);
    apiPet.listConversations.mockRejectedValueOnce(Object.assign(new Error('500'), { detail: 'pet down' }));
    activityApi.list.mockResolvedValueOnce([]);
    renderInbox();
    await waitFor(() => screen.getByText('alice'));
    // Pet section still mounts but with empty placeholder.
    expect(screen.getByText('[ 暂无对话 ]')).toBeInTheDocument();
  });
});
