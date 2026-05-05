import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PetConversations from './PetConversations.jsx';

vi.mock('../../api/pet.js', () => ({
  apiPet: {
    listConversations: vi.fn(async () => ({
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
    })),
  },
}));

describe('PetConversations', () => {
  it('renders the list grouped by visitor', async () => {
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
});
