import { createContext, useContext, useState, useCallback, useMemo, useEffect } from 'react';
import { apiAdmin, getToken, setToken, clearToken } from '../api/admin.js';

const AuthContext = createContext(null);

// Install once: any /api/admin/* response with 401 clears the token and bounces
// to the login screen, so a stale JWT doesn't leave the app stuck on an
// unrecoverable error card. Patch is idempotent across HMR reloads.
function installAuthFetchInterceptor(onUnauthorized) {
  if (typeof window === 'undefined') return;
  if (window.__myblogFetchPatched) {
    window.__myblogOnUnauthorized = onUnauthorized;
    return;
  }
  const original = window.fetch.bind(window);
  window.__myblogOnUnauthorized = onUnauthorized;
  window.__myblogFetchPatched = true;
  window.fetch = async (input, init) => {
    const r = await original(input, init);
    if (r.status === 401) {
      const url = typeof input === 'string' ? input : input?.url || '';
      if (url.includes('/api/admin/') && !url.includes('/api/admin/auth/login')) {
        window.__myblogOnUnauthorized?.();
      }
    }
    return r;
  };
}

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken());
  const [email, setEmail] = useState(() => {
    try {
      return localStorage.getItem('myblog.admin.email') || null;
    } catch {
      return null;
    }
  });

  const login = useCallback(async (emailInput, password) => {
    const resp = await apiAdmin.login(emailInput, password);
    const access = resp?.access;
    if (!access) throw new Error('Login response missing "access" token');
    setToken(access);
    setTokenState(access);
    setEmail(emailInput);
    try {
      localStorage.setItem('myblog.admin.email', emailInput);
    } catch {
      /* ignore */
    }
    return resp;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setEmail(null);
    try {
      localStorage.removeItem('myblog.admin.email');
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    installAuthFetchInterceptor(() => {
      clearToken();
      setTokenState(null);
      if (window.location.pathname.startsWith('/admin') && window.location.pathname !== '/admin') {
        window.location.replace('/admin');
      }
    });
  }, []);

  const value = useMemo(
    () => ({ token, email, login, logout, isAuthed: Boolean(token) }),
    [token, email, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}

export default AuthContext;
