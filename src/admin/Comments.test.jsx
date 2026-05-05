import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Comments from './Comments.jsx';
import UIProvider from './ui/UIProvider.jsx';

vi.mock('../api/comments.js', () => ({
  commentsApi: {
    list: vi.fn(),
    patch: vi.fn(),
    remove: vi.fn(),
    bulk: vi.fn(),
  },
}));

import { commentsApi } from '../api/comments.js';

const SAMPLE = [
  {
    id: 1, post_id: 'vps', post_title: 'VPS notes', parent_id: null,
    who: 'alice', email_hash: 'abc', body: 'first',
    status: 'pending', flag: false, actor: 'public',
    created_at: new Date().toISOString(),
  },
  {
    id: 2, post_id: 'vps', post_title: 'VPS notes', parent_id: null,
    who: 'bob', email_hash: 'def', body: 'second',
    status: 'pending', flag: false, actor: 'public',
    created_at: new Date().toISOString(),
  },
  {
    id: 3, post_id: 'other', post_title: 'Other post', parent_id: null,
    who: 'carol', email_hash: 'ghi', body: 'third',
    status: 'pending', flag: false, actor: 'public',
    created_at: new Date().toISOString(),
  },
];

function renderWithProvider(ui) {
  return render(<UIProvider>{ui}</UIProvider>);
}

async function clickConfirmOk() {
  const ok = await screen.findByTestId('confirm-ok');
  fireEvent.click(ok);
}

async function clickConfirmCancel() {
  const cancel = await screen.findByTestId('confirm-cancel');
  fireEvent.click(cancel);
}

beforeEach(() => {
  vi.clearAllMocks();
  commentsApi.list.mockResolvedValue([...SAMPLE]);
});

describe('Comments bulk + filter', () => {
  it('passes post_id to commentsApi.list when post filter is set', async () => {
    renderWithProvider(<Comments />);
    await waitFor(() => screen.getByTestId('comment-1'));
    fireEvent.change(screen.getByTestId('post-filter'), { target: { value: 'vps' } });
    await waitFor(() =>
      expect(commentsApi.list).toHaveBeenLastCalledWith({
        status: 'pending',
        post_id: 'vps',
      }),
    );
  });

  it('select-all selects every visible row, bulk bar appears, bulk approve calls api.bulk', async () => {
    commentsApi.bulk.mockResolvedValue({ affected: 3, action: 'approve' });
    renderWithProvider(<Comments />);
    await waitFor(() => screen.getByTestId('comment-1'));
    fireEvent.click(screen.getByTestId('select-all'));
    expect(screen.getByTestId('bulk-bar')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('bulk-approve'));
    await clickConfirmOk();
    await waitFor(() =>
      expect(commentsApi.bulk).toHaveBeenCalledWith('approve', [1, 2, 3]),
    );
  });

  it('toggling a single row puts only that id into the bulk action', async () => {
    commentsApi.bulk.mockResolvedValue({ affected: 1, action: 'spam' });
    renderWithProvider(<Comments />);
    await waitFor(() => screen.getByTestId('comment-2'));
    fireEvent.click(screen.getByTestId('select-2'));
    fireEvent.click(screen.getByText('批量标垃圾'));
    await clickConfirmOk();
    await waitFor(() =>
      expect(commentsApi.bulk).toHaveBeenCalledWith('spam', [2]),
    );
  });

  it('cancel in confirm aborts the bulk call', async () => {
    renderWithProvider(<Comments />);
    await waitFor(() => screen.getByTestId('comment-1'));
    fireEvent.click(screen.getByTestId('select-1'));
    fireEvent.click(screen.getByText('批量删除'));
    await clickConfirmCancel();
    expect(commentsApi.bulk).not.toHaveBeenCalled();
  });

  it('clearing the post filter restores list with no post_id', async () => {
    renderWithProvider(<Comments />);
    await waitFor(() => screen.getByTestId('comment-1'));
    fireEvent.change(screen.getByTestId('post-filter'), { target: { value: 'vps' } });
    await waitFor(() =>
      expect(commentsApi.list).toHaveBeenLastCalledWith({ status: 'pending', post_id: 'vps' }),
    );
    fireEvent.click(screen.getByText('清除'));
    await waitFor(() =>
      expect(commentsApi.list).toHaveBeenLastCalledWith({ status: 'pending', post_id: undefined }),
    );
  });
});
