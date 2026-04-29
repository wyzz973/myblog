import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { apiAdmin, getToken, setToken, clearToken } from '../api/admin.js';

const AuthContext = createContext(null);

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
