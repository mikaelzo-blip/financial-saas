import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, expect, it, vi } from 'vitest';

import { masterApi } from '../../src/api/master';
import { projectsApi } from '../../src/api/projects';
import { TransactionForm } from '../../src/components/forms/TransactionForm';

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(projectsApi, 'list').mockResolvedValue([]);
  vi.spyOn(masterApi, 'getCustomers').mockResolvedValue([]);
  vi.spyOn(masterApi, 'getVendors').mockResolvedValue([]);
});

function renderForm(onSubmit = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <TransactionForm onSubmit={onSubmit} />
    </QueryClientProvider>,
  );
  return onSubmit;
}

it('shows persisted payment-account names and COA codes as dropdown labels', async () => {
  vi.spyOn(masterApi, 'getPaymentAccounts').mockResolvedValue([
    {
      id: 'account-bca-uuid',
      organization_id: 'organization-1',
      coa_account_id: 'coa-1101-uuid',
      name: 'Bank BCA',
      bank_name: 'BCA',
      is_active: true,
      coa_account_code: '1101',
      coa_account_name: 'Kas dan Bank',
      account_type: 'ASSET',
      created_at: '2026-09-01T00:00:00Z',
    },
  ]);

  renderForm();

  expect(await screen.findByRole('option', { name: 'Bank BCA (1101)' })).toHaveValue(
    'account-bca-uuid',
  );
  expect(screen.queryByRole('option', { name: '0' })).not.toBeInTheDocument();
});

it('submits the selected persisted payment-account UUID without fallback', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  vi.spyOn(masterApi, 'getPaymentAccounts').mockResolvedValue([
    {
      id: 'account-mandiri-uuid',
      organization_id: 'organization-1',
      coa_account_id: 'coa-1101-uuid',
      name: 'Bank Mandiri',
      bank_name: 'Mandiri',
      is_active: true,
      coa_account_code: '1101',
      coa_account_name: 'Kas dan Bank',
      account_type: 'ASSET',
      created_at: '2026-09-01T00:00:00Z',
    },
  ]);
  renderForm(onSubmit);
  const user = userEvent.setup();

  const select = await screen.findByLabelText('Akun Kas / Bank Pembayaran *');
  expect(await screen.findByRole('option', { name: 'Bank Mandiri (1101)' })).toBeInTheDocument();
  await user.selectOptions(select, 'account-mandiri-uuid');
  await user.type(screen.getByLabelText('Nominal Transaksi (Rp) *'), '5000000');
  await user.type(screen.getByLabelText('Keterangan Transaksi *'), 'Pembelian material');
  await user.click(screen.getByRole('button', { name: 'Simpan Transaksi' }));

  await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  expect(onSubmit.mock.calls[0][0].payment_account_id).toBe('account-mandiri-uuid');
});

it('omits a stale payment account after switching to customer invoice', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  vi.spyOn(masterApi, 'getPaymentAccounts').mockResolvedValue([
    {
      id: 'account-mandiri-uuid',
      organization_id: 'organization-1',
      coa_account_id: 'coa-1101-uuid',
      name: 'Bank Mandiri',
      bank_name: 'Mandiri',
      is_active: true,
      coa_account_code: '1101',
      coa_account_name: 'Kas dan Bank',
      account_type: 'ASSET',
      created_at: '2026-09-01T00:00:00Z',
    },
  ]);
  renderForm(onSubmit);
  const user = userEvent.setup();

  const paymentAccount = await screen.findByLabelText('Akun Kas / Bank Pembayaran *');
  expect(await screen.findByRole('option', { name: 'Bank Mandiri (1101)' })).toBeInTheDocument();
  await user.selectOptions(paymentAccount, 'account-mandiri-uuid');
  await user.selectOptions(screen.getByLabelText('Jenis Transaksi *'), 'CUSTOMER_INVOICE');
  await user.type(screen.getByLabelText('Nominal Transaksi (Rp) *'), '25000000');
  await user.type(screen.getByLabelText('Keterangan Transaksi *'), 'Termin proyek');
  await user.click(screen.getByRole('button', { name: 'Simpan Transaksi' }));

  await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  expect(onSubmit.mock.calls[0][0].payment_account_id).toBeUndefined();
});

it('does not replace payment-account API failures with fake options', async () => {
  vi.spyOn(masterApi, 'getPaymentAccounts').mockRejectedValue(new Error('Network failure'));

  renderForm();

  await waitFor(() => expect(masterApi.getPaymentAccounts).toHaveBeenCalledOnce());
  expect(within(screen.getByLabelText('Akun Kas / Bank Pembayaran *')).getAllByRole('option')).toHaveLength(1);
  expect(screen.queryByRole('option', { name: /Bank BCA|Bank Mandiri|Petty Cash/ })).not.toBeInTheDocument();
});
