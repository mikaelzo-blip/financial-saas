import { beforeEach, expect, it, vi } from 'vitest';
import { masterApi } from '../../src/api/master';
import { apiClient } from '../../src/api/client';

beforeEach(() => vi.restoreAllMocks());

it('returns database customers from the API', async () => {
  const customers = [{ id: 'customer-1', name: 'PT Customer Database' }];
  vi.spyOn(apiClient, 'get').mockResolvedValue({ data: customers });

  await expect(masterApi.getCustomers()).resolves.toEqual(customers);
  expect(apiClient.get).toHaveBeenCalledWith('/counterparties?is_customer=true');
});

it('does not replace customer API failures with hardcoded demo data', async () => {
  vi.spyOn(apiClient, 'get').mockRejectedValue(new Error('Network failure'));
  await expect(masterApi.getCustomers()).rejects.toThrow('Network failure');
});
