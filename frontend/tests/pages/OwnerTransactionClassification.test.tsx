import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { TransactionForm } from '../../src/components/forms/TransactionForm';
import { projectsApi } from '../../src/api/projects';
import { masterApi } from '../../src/api/master';
import { COST_CATEGORIES } from '../../src/types/api';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe('Owner Transaction Classification (Proyek vs Kantor)', () => {
  it('switches between Proyek tertentu and Operasional kantor and submits corresponding categories', async () => {
    vi.spyOn(projectsApi, 'list').mockResolvedValue([
      {
        id: 'prj-1-uuid',
        organization_id: 'org-1',
        project_code: 'PRJ-2026-001',
        project_name: 'Renovasi Gedung Utama',
        customer_id: 'cust-1',
        original_contract_value: '100000000.00',
        variation_order_value: '0.00',
        revised_contract_value: '100000000.00',
        start_date: '2026-01-01',
        project_status: 'ACTIVE',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ] as never);

    vi.spyOn(masterApi, 'getPaymentAccounts').mockResolvedValue([
      {
        id: 'acc-1-uuid',
        organization_id: 'org-1',
        coa_account_id: 'coa-1',
        name: 'Bank Mandiri',
        bank_name: 'Mandiri',
        is_active: true,
        coa_account_code: '1101',
        coa_account_name: 'Kas dan Bank',
        account_type: 'ASSET',
        created_at: '2026-01-01T00:00:00Z',
      },
    ]);

    const handleSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <TransactionForm onSubmit={handleSubmit} />
      </QueryClientProvider>
    );

    // Context choices should be available
    expect(screen.getByText('Proyek tertentu')).toBeInTheDocument();
    expect(screen.getByText('Operasional kantor')).toBeInTheDocument();

    // Default is Project: shows project cost categories
    expect(screen.getByText('Kategori Biaya Konstruksi')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /MAT — Material & Bahan Bangunan/ })).toBeInTheDocument();
    const projectCategorySelect = screen.getByLabelText('Kategori Biaya Konstruksi');
    expect(
      within(projectCategorySelect).getAllByRole('option').map((option) =>
        (option as HTMLOptionElement).value
      )
    ).toEqual([...COST_CATEGORIES]);
    expect(within(projectCategorySelect).queryByRole('option', { name: /UTL|PRM|OHD/ })).not.toBeInTheDocument();

    // Switch to Operasional kantor
    fireEvent.click(screen.getByText('Operasional kantor'));
    expect(screen.getByText('Kategori Biaya Operasional Kantor')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Keperluan Kantor & ATK/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /BBM, Parkir & Transportasi Kantor/ })).toBeInTheDocument();

    // Fill form for office fuel expense
    await userEvent.type(screen.getByLabelText('Nominal Transaksi (Rp) *'), '250000');
    await userEvent.selectOptions(
      screen.getByLabelText(/Akun Kas \/ Bank Pembayaran/),
      'acc-1-uuid'
    );
    await userEvent.selectOptions(
      screen.getByLabelText('Kategori Biaya Operasional Kantor'),
      'TRAVEL_OFFICE'
    );
    await userEvent.type(
      screen.getByLabelText('Keterangan Transaksi *'),
      'BBM operasional kantor keliling bank'
    );

    // Verify summary card reflects office operational context and business impact
    const summaryCard = screen.getByLabelText('Ringkasan Transaksi');
    expect(within(summaryCard).getByText('Operasional Kantor')).toBeInTheDocument();
    expect(within(summaryCard).getByText('BBM, Parkir & Transportasi Kantor')).toBeInTheDocument();
    expect(
      within(summaryCard).getByText(
        'Mencatat beban operasional umum kantor dan pengeluaran kas/bank.'
      )
    ).toBeInTheDocument();

    // Submit and verify payload
    await userEvent.click(screen.getByRole('button', { name: 'Simpan Transaksi' }));

    expect(handleSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        transaction_type: 'DIRECT_PURCHASE',
        amount: 250000,
        expense_category: 'TRAVEL_OFFICE',
        project_id: undefined,
        cost_category: undefined,
        description: 'BBM operasional kantor keliling bank',
      })
    );
  });
});
