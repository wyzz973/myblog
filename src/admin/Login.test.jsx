import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Login from './Login.jsx';
import { AuthProvider } from './AuthContext.jsx';

vi.mock('../api/admin.js', () => ({
  apiAdmin: {
    login: vi.fn(),
    verifyTfa: vi.fn(),
  },
  getToken: vi.fn(() => null),
  setToken: vi.fn(),
  clearToken: vi.fn(),
  TOKEN_KEY: 'myblog.admin.token',
  adminRequest: vi.fn(),
}));

import { apiAdmin } from '../api/admin.js';

function renderApp() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/admin" element={<Login />} />
          <Route path="/admin/dashboard" element={<div>DASH</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

function fillCreds() {
  fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
    target: { value: 'a@b.c' },
  });
  fireEvent.change(screen.getByPlaceholderText('••••••••'), {
    target: { value: 'pw12345678' },
  });
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('Login 2FA flow', () => {
  it('skips TOTP step when backend returns access directly', async () => {
    apiAdmin.login.mockResolvedValueOnce({ access: 'tok', token_type: 'bearer', expires_in: 900 });
    renderApp();
    fillCreds();
    await waitFor(() => expect(screen.getByText('DASH')).toBeInTheDocument());
    expect(apiAdmin.verifyTfa).not.toHaveBeenCalled();
  });

  it('shows TFA step when backend returns tfa_required and routes after verify', async () => {
    apiAdmin.login.mockResolvedValueOnce({ tfa_required: true, challenge: 'ch_abc' });
    apiAdmin.verifyTfa.mockResolvedValueOnce({ access: 'tok', token_type: 'bearer', expires_in: 900 });
    renderApp();
    fillCreds();
    await screen.findByTestId('tfa-form');
    expect(screen.getByText(/two-factor/i)).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('••••••'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: /verify/i }));

    await waitFor(() => expect(apiAdmin.verifyTfa).toHaveBeenCalledWith('ch_abc', '123456'));
    await waitFor(() => expect(screen.getByText('DASH')).toBeInTheDocument());
  });

  it('rejects malformed TOTP client-side without calling backend', async () => {
    apiAdmin.login.mockResolvedValueOnce({ tfa_required: true, challenge: 'ch_abc' });
    renderApp();
    fillCreds();
    await screen.findByTestId('tfa-form');

    fireEvent.change(screen.getByPlaceholderText('••••••'), { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: /verify/i }));
    expect(screen.getByText(/6 digits/i)).toBeInTheDocument();
    expect(apiAdmin.verifyTfa).not.toHaveBeenCalled();
  });

  it('toggles to recovery code mode and validates xxxx-xxxx format', async () => {
    apiAdmin.login.mockResolvedValueOnce({ tfa_required: true, challenge: 'ch_abc' });
    apiAdmin.verifyTfa.mockResolvedValueOnce({ access: 'tok', token_type: 'bearer', expires_in: 900 });
    renderApp();
    fillCreds();
    await screen.findByTestId('tfa-form');

    fireEvent.click(screen.getByRole('button', { name: /use recovery code/i }));
    fireEvent.change(screen.getByPlaceholderText('abcd-efgh'), {
      target: { value: 'a1b2-c3d4' },
    });
    fireEvent.click(screen.getByRole('button', { name: /verify/i }));
    await waitFor(() => expect(apiAdmin.verifyTfa).toHaveBeenCalledWith('ch_abc', 'a1b2-c3d4'));
  });

  it('back button returns to creds step and clears challenge', async () => {
    apiAdmin.login.mockResolvedValueOnce({ tfa_required: true, challenge: 'ch_abc' });
    renderApp();
    fillCreds();
    await screen.findByTestId('tfa-form');

    fireEvent.click(screen.getByRole('button', { name: /back/i }));
    expect(screen.queryByTestId('tfa-form')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('you@example.com')).toBeInTheDocument();
  });
});
