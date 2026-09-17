import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MonthlyCashFlowSection } from '../../src/pages/dashboard/components/MonthlyCashFlowSection';
import { reportsApi } from '../../src/api/reports';

vi.mock('../../src/api/reports', () => ({
  reportsApi: {
    getCashFlowTrend: vi.fn(),
  },
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

describe('MonthlyCashFlowSection Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders monthly cash flow metrics correctly with real data', async () => {
    vi.mocked(reportsApi.getCashFlowTrend).mockResolvedValue({
      items: [
        {
          period: '2026-08',
          month_label: 'Agu 2026',
          cash_in: '120000000.00',
          cash_out: '90000000.00',
          net_cash: '30000000.00',
        },
        {
          period: '2026-09',
          month_label: 'Sep 2026',
          cash_in: '250000000.00',
          cash_out: '180000000.00',
          net_cash: '70000000.00',
        },
      ],
    });

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MonthlyCashFlowSection />
      </QueryClientProvider>
    );

    expect(await screen.findByTestId('monthly-cash-flow-section')).toBeInTheDocument();
    expect(screen.getByText('Arus Kas Bulan Ini')).toBeInTheDocument();
    expect(screen.getByText('Sep 2026')).toBeInTheDocument();

    // Check Uang Masuk
    const cardMasuk = screen.getByTestId('card-uang-masuk');
    expect(cardMasuk).toHaveTextContent('Uang Masuk');
    expect(cardMasuk).toHaveTextContent('Rp 250.000.000');

    // Check Uang Keluar
    const cardKeluar = screen.getByTestId('card-uang-keluar');
    expect(cardKeluar).toHaveTextContent('Uang Keluar');
    expect(cardKeluar).toHaveTextContent('Rp 180.000.000');

    // Check Arus Kas Bersih
    const cardBersih = screen.getByTestId('card-arus-kas-bersih');
    expect(cardBersih).toHaveTextContent('Arus Kas Bersih');
    expect(cardBersih).toHaveTextContent('Rp 70.000.000');
  });

  it('renders error state with retry button on failure', async () => {
    vi.mocked(reportsApi.getCashFlowTrend).mockRejectedValue(new Error('Network error'));

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MonthlyCashFlowSection />
      </QueryClientProvider>
    );

    expect(await screen.findByText('Data arus kas bulan ini belum dapat dimuat.')).toBeInTheDocument();
    expect(screen.getByText('Coba lagi')).toBeInTheDocument();
  });
});
