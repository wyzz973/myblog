import { createContext, useContext, useState, useCallback, useMemo, useEffect, useRef } from 'react';
import {
  apiAdmin,
  getToken,
  setToken,
  clearToken,
  jwtExpiresAt,
  setOnUnauthorized,
  tryRefresh,
} from '../api/admin.js';

const AuthContext = createContext(null);

// Refresh proactively this far before the access token's `exp` claim.
// 80% of the lifetime — leaves a comfortable margin without burning
// /auth/refresh on every request. Floor at 30s so a tiny TTL doesn't
// cause a refresh storm.
const REFRESH_AHEAD_RATIO = 0.8;
const MIN_REFRESH_DELAY_MS = 30 * 1000;

function computeRefreshDelay(token, now = Date.now()) {
  const expAt = jwtExpiresAt(token);
  if (!expAt) return null;
  const remaining = expAt - now;
  if (remaining <= 0) return null;
  const target = Math.floor(remaining * REFRESH_AHEAD_RATIO);
  return Math.max(target, MIN_REFRESH_DELAY_MS);
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
  const refreshTimerRef = useRef(null);

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const persistAccess = useCallback((access, emailInput) => {
    setToken(access);
    setTokenState(access);
    setEmail(emailInput);
    try {
      localStorage.setItem('myblog.admin.email', emailInput);
    } catch {
      /* ignore */
    }
  }, []);

  const login = useCallback(
    async (emailInput, password) => {
      const resp = await apiAdmin.login(emailInput, password);
      // If 2FA is enabled, backend returns {tfa_required:true, challenge}
      // and no access token yet — caller drives the second step.
      if (resp?.tfa_required) return resp;
      const access = resp?.access;
      if (!access) throw new Error('Login response missing "access" token');
      persistAccess(access, emailInput);
      return resp;
    },
    [persistAccess],
  );

  const verifyTfa = useCallback(
    async (challenge, code, emailInput) => {
      const resp = await apiAdmin.verifyTfa(challenge, code);
      const access = resp?.access;
      if (!access) throw new Error('2FA response missing "access" token');
      persistAccess(access, emailInput);
      return resp;
    },
    [persistAccess],
  );

  const logout = useCallback(() => {
    clearRefreshTimer();
    clearToken();
    setTokenState(null);
    setEmail(null);
    try {
      localStorage.removeItem('myblog.admin.email');
    } catch {
      /* ignore */
    }
  }, [clearRefreshTimer]);

  // Wire the api-layer's onUnauthorized callback once. When refresh
  // ultimately fails, the api layer has already cleared the token; this
  // callback handles the React side: drop session state and bounce to
  // /admin if we're inside a protected screen.
  useEffect(() => {
    setOnUnauthorized(() => {
      clearRefreshTimer();
      setTokenState(null);
      setEmail(null);
      if (
        typeof window !== 'undefined' &&
        window.location.pathname.startsWith('/admin') &&
        window.location.pathname !== '/admin'
      ) {
        window.location.replace('/admin');
      }
    });
    return () => setOnUnauthorized(null);
  }, [clearRefreshTimer]);

  // Proactive refresh: schedule a single timer per token. Whenever the
  // token changes (login / verifyTfa / refresh), reset the timer to fire
  // at ~80% of remaining TTL.
  useEffect(() => {
    clearRefreshTimer();
    if (!token) return undefined;
    const delay = computeRefreshDelay(token);
    if (delay == null) return undefined;
    refreshTimerRef.current = setTimeout(async () => {
      const result = await tryRefresh();
      if (result?.access) {
        // Trigger re-render with new token — onUnauthorized handles the
        // failure path so we don't need to act here on null.
        setTokenState(result.access);
      }
    }, delay);
    return clearRefreshTimer;
  }, [token, clearRefreshTimer]);

  const value = useMemo(
    () => ({ token, email, login, verifyTfa, logout, isAuthed: Boolean(token) }),
    [token, email, login, verifyTfa, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}

export default AuthContext;
