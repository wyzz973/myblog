import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PetConversations from './PetConversations.jsx';

const listMock = vi.fn();

vi.mock('../../api/pet.js', () => ({
  apiPet: {
    listConversations: (...args) => listMock(...args),
  },
}));

function withRows() {
  listMock.mockReset();
  listMock.mockResolvedValue({
    items: [
      {
        visitor_hash: 'abc',
        species: 'cat',
        last_msg_at: new Date().toISOString(),
        message_count: 3,
        last_reply_preview: 'hello world',
      },
    ],
    next_cursor: null,
  });
}

function withNoRows() {
  listMock.mockReset();
  listMock.mockResolvedValue({ items: [], next_cursor: null });
}

describe('PetConversations', () => {
  it('renders the list grouped by visitor', async () => {
    withRows();
    render(
      <MemoryRouter>
        <PetConversations />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/abc/));
    expect(screen.getByText('cat')).toBeInTheDocument();
    expect(screen.getByText(/3 条消息/)).toBeInTheDocument();
    expect(screen.getByText(/hello world/)).toBeInTheDocument();
  });

  it('shows the no-conversations empty state when items is [] and no filter', async () => {
    withNoRows();
    render(
      <MemoryRouter>
        <PetConversations />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('conv-empty'));
    expect(screen.getByTestId('conv-empty').textContent).toMatch(/尚无访客发起对话/);
  });

  it('switches to the no-match empty state once a hash filter is applied', async () => {
    withNoRows();
    render(
      <MemoryRouter>
        <PetConversations />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByTestId('conv-empty'));
    // Type into the hash filter to flip the empty state's wording.
    fireEvent.change(screen.getByTestId('conv-search'), { target: { value: 'zzzz' } });
    await waitFor(() => {
      const el = screen.getByTestId('conv-empty');
      expect(el.textContent).toMatch(/当前筛选下没有匹配的对话/);
    });
  });
});
