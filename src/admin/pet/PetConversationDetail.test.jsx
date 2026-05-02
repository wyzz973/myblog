import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PetConversationDetail from './PetConversationDetail.jsx';

vi.mock('../../api/pet.js', () => ({
  apiPet: {
    getConversation: vi.fn(),
    deleteConversation: vi.fn(),
  },
}));

const FIXTURE = {
  items: [
    {
      id: 1, visitor_hash: 'abc', species: 'cat', mode: 'greet',
      post_id: null, title: null, tag_slug: null, summary: null, selection: null,
      system_prompt: 'you are cat', prior_turns: [],
      reply: 'meow hi', source: 'zhipu',
      created_at: '2026-05-02T13:00:00Z',
    },
    {
      id: 2, visitor_hash: 'abc', species: 'cat', mode: 'summary_react',
      post_id: 'hello', title: 'Hello', tag_slug: 'devtools',
      summary: 'a summary', selection: null,
      system_prompt: 'you are cat', prior_turns: [],
      reply: 'interesting article', source: 'zhipu',
      created_at: '2026-05-02T13:01:00Z',
    },
  ],
  next_cursor: null,
};

beforeEach(async () => {
  vi.clearAllMocks();
  const { apiPet } = await import('../../api/pet.js');
  apiPet.getConversation.mockResolvedValue(FIXTURE);
  apiPet.deleteConversation.mockResolvedValue(null);
});

describe('PetConversationDetail', () => {
  it('renders messages oldest first', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/pet/conversations/abc']}>
        <Routes>
          <Route path="/admin/pet/conversations/:visitorHash" element={<PetConversationDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/meow hi/));
    const replies = screen.getAllByTestId('reply-text');
    expect(replies[0]).toHaveTextContent('meow hi');
    expect(replies[1]).toHaveTextContent('interesting article');
  });

  it('delete button prompts confirm and calls api', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { apiPet } = await import('../../api/pet.js');
    render(
      <MemoryRouter initialEntries={['/admin/pet/conversations/abc']}>
        <Routes>
          <Route path="/admin/pet/conversations/:visitorHash" element={<PetConversationDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/meow hi/));
    fireEvent.click(screen.getByText(/delete all/i));
    expect(confirmSpy).toHaveBeenCalled();
    expect(apiPet.deleteConversation).toHaveBeenCalledWith('abc');
    confirmSpy.mockRestore();
  });
});
