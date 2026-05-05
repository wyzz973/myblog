import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SiteIdentity from './SiteIdentity.jsx';

vi.mock('../api/profile.js', () => ({
  apiProfile: {
    get: vi.fn(),
    put: vi.fn(),
    listImages: vi.fn(async () => []),
    session: vi.fn(async () => ({ email: 'me@example.com', tfa_enabled: false })),
  },
}));
vi.mock('../api/site.js', () => ({
  apiSite: {
    getSite: vi.fn(),
    putSite: vi.fn(),
    getTheme: vi.fn(),
    putTheme: vi.fn(),
  },
}));
vi.mock('../api/media.js', () => ({
  mediaUrl: vi.fn((m) => `/media/${m}`),
}));

import { apiProfile } from '../api/profile.js';
import { apiSite } from '../api/site.js';

const PROFILE = {
  name: '汪洋',
  name_en: 'Wang Yang',
  role: '',
  bio: 'old bio',
  location: '',
  pronouns: '',
  avatar_id: null,
  avatar_path: null,
  typing_line: 'building things…',
  stack_chips: ['typescript', 'python'],
};

const SITE = {
  handle: 'wangyang',
  tagline: 'old tagline',
  email: 'me@example.com',
  github: 'wyzz973',
  footer_note: '© 2026',
  default_theme: 'dark',
  launched_at: '2026-01-01',
  // theme fields are not in scope for SiteIdentity but backend may include
  // them — we ignore in patch building so they don't show up in PUT bodies.
  accent_color: 'oklch(82% 0.17 152)',
};

beforeEach(() => {
  vi.clearAllMocks();
  apiProfile.get.mockResolvedValue({ ...PROFILE });
  apiSite.getSite.mockResolvedValue({ ...SITE });
  apiProfile.put.mockImplementation(async (patch) => ({ ...PROFILE, ...patch }));
  apiSite.putSite.mockImplementation(async (patch) => ({ ...SITE, ...patch }));
});

describe('SiteIdentity', () => {
  it('loads both endpoints and renders one merged form', async () => {
    render(<SiteIdentity />);
    await waitFor(() => screen.getByTestId('site-identity'));
    expect(screen.getByTestId('p-name')).toHaveValue('汪洋');
    expect(screen.getByTestId('p-typing_line')).toHaveValue('building things…');
    expect(screen.getByTestId('s-handle')).toHaveValue('wangyang');
    expect(screen.getByTestId('s-tagline')).toHaveValue('old tagline');
    expect(screen.getByTestId('s-default_theme')).toHaveValue('dark');
  });

  it('saves only the changed profile + site fields, in parallel', async () => {
    render(<SiteIdentity />);
    await waitFor(() => screen.getByTestId('site-identity'));
    fireEvent.change(screen.getByTestId('p-name'), { target: { value: '新名字' } });
    fireEvent.change(screen.getByTestId('s-tagline'), { target: { value: 'new tagline' } });
    fireEvent.click(screen.getByTestId('save-btn'));

    await waitFor(() => expect(apiProfile.put).toHaveBeenCalledTimes(1));
    expect(apiProfile.put).toHaveBeenCalledWith({ name: '新名字' });
    await waitFor(() => expect(apiSite.putSite).toHaveBeenCalledTimes(1));
    expect(apiSite.putSite).toHaveBeenCalledWith({ tagline: 'new tagline' });
    await waitFor(() => screen.getByText('已保存'));
  });

  it('skips an endpoint when its slice is unchanged', async () => {
    render(<SiteIdentity />);
    await waitFor(() => screen.getByTestId('site-identity'));
    // Only modify a site field
    fireEvent.change(screen.getByTestId('s-tagline'), { target: { value: 'site only' } });
    fireEvent.click(screen.getByTestId('save-btn'));
    await waitFor(() => expect(apiSite.putSite).toHaveBeenCalled());
    expect(apiProfile.put).not.toHaveBeenCalled();
  });

  it('surfaces a partial failure when one PUT throws', async () => {
    apiSite.putSite.mockRejectedValueOnce(Object.assign(new Error('500 boom'), { detail: 'boom' }));
    render(<SiteIdentity />);
    await waitFor(() => screen.getByTestId('site-identity'));
    fireEvent.change(screen.getByTestId('p-name'), { target: { value: 'new' } });
    fireEvent.change(screen.getByTestId('s-tagline'), { target: { value: 'new tag' } });
    fireEvent.click(screen.getByTestId('save-btn'));
    await waitFor(() => screen.getByText(/部分保存失败/));
    expect(apiProfile.put).toHaveBeenCalled();
    expect(apiSite.putSite).toHaveBeenCalled();
  });

  it('disables save when nothing is dirty', async () => {
    render(<SiteIdentity />);
    await waitFor(() => screen.getByTestId('site-identity'));
    expect(screen.getByTestId('save-btn')).toBeDisabled();
  });
});
