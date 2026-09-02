import axios, { AxiosHeaders } from 'axios';
import { beforeEach, expect, it, vi } from 'vitest';
import { authApi } from '../../src/api/auth';
import { apiClient } from '../../src/api/client';

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

it('does not create a mock session when authentication fails', async () => {
  vi.spyOn(apiClient, 'post').mockRejectedValue(new Error('Unauthorized'));
  await expect(authApi.login({ email: 'operator@example.test', password: 'wrong' })).rejects.toThrow('Unauthorized');
  expect(localStorage.getItem('financial_user_session')).toBeNull();
});

it('lets AuthProvider surface session-validation failures instead of redirecting silently', async () => {
  localStorage.setItem('financial_user_session', JSON.stringify({ accessToken: 'expired' }));
  const adapter = vi.fn().mockRejectedValue(
    new axios.AxiosError(
      'Request failed with status code 401',
      'ERR_BAD_REQUEST',
      { headers: new AxiosHeaders() },
      undefined,
      {
        data: { detail: 'Authenticated user required' },
        status: 401,
        statusText: 'Unauthorized',
        headers: {},
        config: { headers: new AxiosHeaders() },
      },
    ),
  );

  await expect(apiClient.get('/auth/session', { adapter })).rejects.toBeDefined();
  expect(localStorage.getItem('financial_user_session')).not.toBeNull();
});
