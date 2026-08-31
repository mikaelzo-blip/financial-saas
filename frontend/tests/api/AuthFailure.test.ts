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
