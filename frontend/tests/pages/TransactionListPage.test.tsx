import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { transactionsApi } from '../../src/api/transactions';
import { TransactionListPage } from '../../src/pages/transactions/TransactionListPage';

vi.mock('../../src/api/transactions', () => ({
  transactionsApi: { list: vi.fn() },
}));

const queryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe('TransactionListPage UX', () => {
  it('renders translated Indonesian transaction types instead of raw enums', async () => {
    vi.mocked(transactionsApi.list).mockResolvedValue([
      {
        id: 'trx-1',
        organization_id: 'org-1',
        transaction_code: 'TRX-001',
        transaction_type: 'VENDOR_BILL',
        transaction_date: '2026-09-08',
        amount: '15000000.00',
        currency: 'IDR',
        workflow_status: 'POSTED',
        counterparty_id: 'c-1',
        counterparty_name: 'PT Semen Padang',
        description: 'Beli semen sak proyek',
        source_channel: 'WEB',
        allocations: [],
        review_flags: [],
        created_at: '2026-09-08T00:00:00Z',
        updated_at: '2026-09-08T00:00:00Z',
      },
    ] as never);

    render(
      <QueryClientProvider client={queryClient()}>
        <MemoryRouter>
          <TransactionListPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Tagihan vendor')).toBeInTheDocument();
    expect(screen.queryByText('VENDOR_BILL')).not.toBeInTheDocument();
  });
});
