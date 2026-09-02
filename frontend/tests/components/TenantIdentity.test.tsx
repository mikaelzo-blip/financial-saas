import React from 'react';
import { render, renderHook, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../../src/App';
import { authApi } from '../../src/api/auth';
import { apiClient } from '../../src/api/client';
import { AppLayout } from '../../src/components/layout/AppLayout';
import { AuthProvider, useAuth } from '../../src/store/AuthContext';
import type { UserSession } from '../../src/types/api';

const authoritativeSession: UserSession = {
  userId: 'user-pt',
  email: 'admin@kontraktor-utama.co.id',
  fullName: 'Administrator',
  role: 'ADMIN',
  organizationId: '9670673b-c0fd-4ebe-87e4-a646358084ea',
  organizationName: 'PT Kontraktor Utama Indonesia',
  accessToken: 'signed-token',
};

const staleSession: UserSession = {
  ...authoritativeSession,
  organizationName: 'Demo Kontraktor',
};

describe('authoritative tenant identity', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('revalidates persisted tenant identity with the authenticated backend on reload', async () => {
    localStorage.setItem('financial_user_session', JSON.stringify(staleSession));
    vi.spyOn(authApi, 'getSession').mockResolvedValue(authoritativeSession);
    const wrapper = ({ children }: { children: React.ReactNode }) => <AuthProvider>{children}</AuthProvider>;

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toEqual(authoritativeSession);
    expect(JSON.parse(localStorage.getItem('financial_user_session')!)).toEqual(authoritativeSession);
  });

  it('fails closed instead of displaying a cached or fallback tenant when validation fails', async () => {
    localStorage.setItem('financial_user_session', JSON.stringify(staleSession));
    vi.spyOn(authApi, 'getSession').mockRejectedValue(new Error('Session validation failed'));
    const wrapper = ({ children }: { children: React.ReactNode }) => <AuthProvider>{children}</AuthProvider>;

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(result.current.sessionError).toBe('Identitas perusahaan tidak dapat diverifikasi. Silakan masuk kembali.');
    expect(localStorage.getItem('financial_user_session')).toBeNull();
  });

  it('shows an explicit verification error after a stale session redirects to login', async () => {
    localStorage.setItem('financial_user_session', JSON.stringify(staleSession));
    vi.spyOn(authApi, 'getSession').mockRejectedValue(new Error('Session validation failed'));
    window.history.pushState({}, '', '/dashboard');

    render(<App />);

    expect(await screen.findByText('Identitas perusahaan tidak dapat diverifikasi. Silakan masuk kembali.')).toBeInTheDocument();
    expect(screen.queryByText('Demo Kontraktor')).not.toBeInTheDocument();
  });

  it('renders only the organization name paired with the authenticated organization id', async () => {
    localStorage.setItem('financial_user_session', JSON.stringify(authoritativeSession));
    vi.spyOn(authApi, 'getSession').mockResolvedValue(authoritativeSession);
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AuthProvider>
          <AppLayout />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('PT Kontraktor Utama Indonesia')).toBeInTheDocument();
    expect(screen.queryByText('Demo Kontraktor')).not.toBeInTheDocument();
    expect(screen.queryByText('PT Kontraktor Utama', { exact: true })).not.toBeInTheDocument();
  });

  it('uses the authenticated tenant id for API requests and cannot switch implicitly', async () => {
    localStorage.setItem('financial_user_session', JSON.stringify(authoritativeSession));
    let requestHeaders: Record<string, unknown> = {};

    await apiClient.get('/projects', {
      adapter: async (config) => {
        requestHeaders = config.headers?.toJSON() || {};
        return { data: [], status: 200, statusText: 'OK', headers: {}, config };
      },
    });

    expect(requestHeaders['X-Organization-ID']).toBe(authoritativeSession.organizationId);
    expect(requestHeaders.Authorization).toBe(`Bearer ${authoritativeSession.accessToken}`);
  });
});
