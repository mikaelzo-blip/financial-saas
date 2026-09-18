import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { bankReconciliationApi } from '../../src/api/bankReconciliation';
import { masterApi } from '../../src/api/master';
import { ToastProvider } from '../../src/components/feedback/Toast';
import { BankReconciliationPage } from '../../src/pages/reconciliation/BankReconciliationPage';

vi.mock('../../src/api/bankReconciliation', () => ({
  bankReconciliationApi: {
    getCashCompletenessDashboard: vi.fn(),
    uploadStatement: vi.fn(),
    autoMatch: vi.fn(),
  },
}));

vi.mock('../../src/api/master', () => ({
  masterApi: {
    getPaymentAccounts: vi.fn(),
  },
}));

describe('BankReconciliationPage Loading, Error, and Empty UX (Objective 3)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter>
            <BankReconciliationPage />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

  // Test 18 & 19: Coherent loading state without giant stacked rectangles
  it('renders coherent skeleton loading state matching page structure with text "Memuat data rekonsiliasi..."', async () => {
    vi.mocked(masterApi.getPaymentAccounts).mockReturnValue(new Promise(() => {}));
    vi.mocked(bankReconciliationApi.getCashCompletenessDashboard).mockReturnValue(new Promise(() => {}));

    renderComponent();

    // Text banner present
    expect(screen.getByText('Memuat data rekonsiliasi...')).toBeInTheDocument();
    expect(screen.getByLabelText('Memuat data rekonsiliasi...')).toBeInTheDocument();

    // Account selector skeleton present
    expect(screen.getByLabelText('Memuat daftar rekening...')).toBeInTheDocument();

    // 3 summary cards: Saldo Buku, Saldo Bank, Selisih
    expect(screen.getByLabelText('Ringkasan Saldo Rekonsiliasi Skeleton')).toBeInTheDocument();
    expect(screen.getByText('Saldo Buku')).toBeInTheDocument();
    expect(screen.getByText('Saldo Bank')).toBeInTheDocument();
    expect(screen.getByText('Selisih')).toBeInTheDocument();

    // Table skeleton and upload skeleton present
    expect(screen.getByLabelText('Tabel Rekonsiliasi Skeleton')).toBeInTheDocument();
    expect(screen.getByLabelText('Unggah Rekening Koran Skeleton')).toBeInTheDocument();
  });

  // Test 20: Reconciliation error state stops skeleton and shows friendly message
  it('stops loading skeleton on error and shows friendly message without raw HTTP/Axios objects', async () => {
    vi.mocked(masterApi.getPaymentAccounts).mockRejectedValue(new Error('Network failure'));
    vi.mocked(bankReconciliationApi.getCashCompletenessDashboard).mockRejectedValue(new Error('AxiosError: Request failed with status code 500'));

    renderComponent();

    expect(await screen.findByText('Data rekonsiliasi belum berhasil dimuat.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Coba Lagi/i })).toBeInTheDocument();

    // Raw HTTP or Axios error details must not leak
    expect(screen.queryByText(/AxiosError/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/status code 500/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Network failure/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Memuat data rekonsiliasi...')).not.toBeInTheDocument();
  });

  // Test 21: Coba Lagi triggers refetch
  it('triggers refetch of reconciliation queries when "Coba Lagi" is clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(masterApi.getPaymentAccounts).mockRejectedValueOnce(new Error('Temporary error'));
    vi.mocked(bankReconciliationApi.getCashCompletenessDashboard).mockRejectedValueOnce(new Error('Temporary error'));

    renderComponent();

    const retryButton = await screen.findByRole('button', { name: /Coba Lagi/i });
    expect(retryButton).toBeInTheDocument();

    // Prepare successful resolution on retry
    vi.mocked(masterApi.getPaymentAccounts).mockResolvedValueOnce([
      { id: 'acc-1', name: 'BCA Operasional', account_number: '1234567890' } as any,
    ]);
    vi.mocked(bankReconciliationApi.getCashCompletenessDashboard).mockResolvedValueOnce({
      total_bank_inflow: 50000000,
      total_bank_outflow: 20000000,
      matched_amount: 15000000,
      unallocated_cash_total: 5000000,
      completeness_percentage: 75.0,
      period_start: '2026-09-01',
      period_end: '2026-09-30',
    } as any);

    await user.click(retryButton);

    expect(await screen.findByText('Total Masuk (Bank)')).toBeInTheDocument();
    expect(screen.queryByText('Data rekonsiliasi belum berhasil dimuat.')).not.toBeInTheDocument();
  });

  // Test 22: Empty state is distinct from error state and preserves upload action
  it('renders distinct empty state with "Belum ada data rekonsiliasi." when no records exist, preserving upload action', async () => {
    vi.mocked(masterApi.getPaymentAccounts).mockResolvedValue([
      { id: 'acc-1', name: 'BCA Operasional', account_number: '1234567890' } as any,
    ]);
    // Empty reconciliation records
    vi.mocked(bankReconciliationApi.getCashCompletenessDashboard).mockResolvedValue({
      total_bank_inflow: 0,
      total_bank_outflow: 0,
      matched_amount: 0,
      unmatched_bank_amount: 0,
      unmatched_book_amount: 0,
      unallocated_cash_total: 0,
      completeness_percentage: 0,
      period_start: '2026-09-01',
      period_end: '2026-09-30',
    } as any);

    renderComponent();

    // Empty state message displayed
    expect(await screen.findByText('Belum ada data rekonsiliasi.')).toBeInTheDocument();
    expect(screen.getByLabelText('Status kosong')).toBeInTheDocument();

    // Crucially: MUST NOT show error state
    expect(screen.queryByText('Data rekonsiliasi belum berhasil dimuat.')).not.toBeInTheDocument();

    // Statement upload section must remain accessible and preserved
    expect(screen.getByText('Unggah Rekening Koran (Bank Statement)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Impor & Rekonsiliasi Otomatis/i })).toBeInTheDocument();
  });
});
