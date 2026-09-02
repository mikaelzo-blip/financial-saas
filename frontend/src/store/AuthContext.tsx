import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../api/auth';
import { UserSession, UserRole } from '../types/api';

interface AuthContextType {
  user: UserSession | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  sessionError: string | null;
  login: (session: UserSession) => void;
  logout: () => void;
  hasRole: (roles: UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const STORAGE_KEY = 'financial_user_session';
const SESSION_ERROR = 'Identitas perusahaan tidak dapat diverifikasi. Silakan masuk kembali.';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    const restoreSession = async () => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return;
        const cached: UserSession = JSON.parse(stored);
        const authoritative = await authApi.getSession(cached.accessToken);
        setUser(authoritative);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(authoritative));
      } catch {
        setUser(null);
        setSessionError(SESSION_ERROR);
        localStorage.removeItem(STORAGE_KEY);
      } finally {
        setIsLoading(false);
      }
    };
    void restoreSession();
  }, []);

  const login = (session: UserSession) => {
    setSessionError(null);
    setUser(session);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  };

  const logout = () => {
    setSessionError(null);
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  };

  const hasRole = (roles: UserRole[]) => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        sessionError,
        login,
        logout,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
