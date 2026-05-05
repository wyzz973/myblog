import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import VisitorProfileSidebar from './VisitorProfileSidebar.jsx';

vi.mock('../../api/pet.js', () => ({
  apiPet: {
    patchProfile: vi.fn(),
  },
}));

import { apiPet } from '../../api/pet.js';

const FULL = {
  visitor_hash: 'abc123def456',
  species: 'cat',
  locale: 'zh-CN',
  preferred_language: 'zh',
  interest_tags: ['backend', 'devtools'],
  recent_post_ids: ['vps', 'auth'],
  interaction_count: 42,
  last_seen_at: new Date(Date.now() - 60000).toISOString(),
  last_interaction_at: new Date(Date.now() - 120000).toISOString(),
  style_summary: 'concise, code-curious',
  memory_summary: 'asked about VPS providers last visit',
  proactive_muted_until: new Date(Date.now() + 3600000).toISOString(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

function renderSidebar(profile, onMutated = vi.fn()) {
  return render(
    <MemoryRouter>
      <VisitorProfileSidebar
        profile={profile}
        visitorHash="abc123def456"
        onMutated={onMutated}
      />
    </MemoryRouter>,
  );
}

describe('VisitorProfileSidebar', () => {
  it('renders an empty placeholder when profile is null', () => {
    renderSidebar(null);
    expect(screen.getByText(/尚未生成档案/)).toBeInTheDocument();
  });

  it('renders all fields including chips and recent post links', () => {
    renderSidebar(FULL);
    expect(screen.getByText('cat')).toBeInTheDocument();
    expect(screen.getByText('zh-CN')).toBeInTheDocument();
    expect(screen.getByText('zh')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('backend')).toBeInTheDocument();
    expect(screen.getByText('devtools')).toBeInTheDocument();
    expect(screen.getByText('/p/vps')).toBeInTheDocument();
    expect(screen.getByText('/p/auth')).toBeInTheDocument();
    expect(screen.getByText('concise, code-curious')).toBeInTheDocument();
  });

  it('shows unmute button only when proactive_muted_until is in the future', () => {
    const past = { ...FULL, proactive_muted_until: new Date(Date.now() - 60000).toISOString() };
    renderSidebar(past);
    expect(screen.queryByTestId('unmute-btn')).toBeNull();

    renderSidebar(FULL);
    expect(screen.getByTestId('unmute-btn')).toBeInTheDocument();
  });

  it('clicking unmute calls patchProfile and triggers onMutated', async () => {
    apiPet.patchProfile.mockResolvedValueOnce({ ok: true });
    const onMutated = vi.fn();
    renderSidebar(FULL, onMutated);
    fireEvent.click(screen.getByTestId('unmute-btn'));
    await waitFor(() =>
      expect(apiPet.patchProfile).toHaveBeenCalledWith('abc123def456', 'unmute'),
    );
    await waitFor(() => expect(onMutated).toHaveBeenCalled());
  });

  it('reset is gated by a confirm step before calling patchProfile', async () => {
    apiPet.patchProfile.mockResolvedValueOnce({ ok: true });
    const onMutated = vi.fn();
    renderSidebar(FULL, onMutated);
    fireEvent.click(screen.getByTestId('reset-profile-btn'));
    expect(screen.getByTestId('reset-confirm-btn')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('reset-confirm-btn'));
    await waitFor(() =>
      expect(apiPet.patchProfile).toHaveBeenCalledWith('abc123def456', 'reset'),
    );
    await waitFor(() => expect(onMutated).toHaveBeenCalled());
  });
});
