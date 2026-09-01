import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, expect, it, vi } from 'vitest';

import { masterApi } from '../../src/api/master';
import { ProjectForm } from '../../src/components/forms/ProjectForm';

beforeEach(() => vi.restoreAllMocks());

it('shows customers returned by the database API in the project dropdown', async () => {
  vi.spyOn(masterApi, 'getCustomers').mockResolvedValue([
    {
      id: 'customer-new',
      organization_id: 'organization-1',
      name: 'PT Customer UAT Baru',
      is_customer: true,
      is_vendor: false,
      created_at: '2026-09-01T00:00:00Z',
    },
  ]);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <ProjectForm onSubmit={vi.fn()} />
    </QueryClientProvider>,
  );

  expect(await screen.findByRole('option', { name: 'PT Customer UAT Baru' })).toHaveValue('customer-new');
});
