import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from '../../src/store/AuthContext';
import { UserSession } from '../../src/types/api';
import React from 'react';

const mockSession: UserSession = {
  userId: 'user-123',
  email: 'operator@example.com',
  fullName: 'Operator Test',
  role: 'OPERATOR',
  organizationId: 'org-123',
  organizationName: 'PT Test Org',
  accessToken: 'token-abc',
};

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('provides initial unauthenticated state when localStorage is empty', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <AuthProvider>{children}</AuthProvider>
    );
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('updates state and persists session to localStorage on login', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <AuthProvider>{children}</AuthProvider>
    );
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.login(mockSession);
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.email).toBe('operator@example.com');
    expect(result.current.hasRole(['OPERATOR'])).toBe(true);
    expect(result.current.hasRole(['MANAGER'])).toBe(false);
  });

  it('clears state and localStorage on logout', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <AuthProvider>{children}</AuthProvider>
    );
    const { result } = renderHook(() => useAuth(), { wrapper });

    act(() => {
      result.current.login(mockSession);
    });
    expect(result.current.isAuthenticated).toBe(true);

    act(() => {
      result.current.logout();
    });
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });
});
