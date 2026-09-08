import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { BalanceSheetPage } from '../../src/pages/reports/BalanceSheetPage';
import { FixedAssetsPage } from '../../src/pages/assets/FixedAssetsPage';
import { SettingsPage } from '../../src/pages/settings/SettingsPage';
import { reportsApi } from '../../src/api/reports';
import { fixedAssetsApi } from '../../src/api/fixedAssets';
import { authApi } from '../../src/api/auth';
import { ToastProvider } from '../../src/components/feedback/Toast';
import { AuthProvider } from '../../src/store/AuthContext';
import type { ReportLineItem } from '../../src/types/reporting';

vi.mock('../../src/api/reports', () => ({
  reportsApi: { getBalanceSheet: vi.fn(), downloadReport: vi.fn() },
}));
vi.mock('../../src/api/fixedAssets', () => ({
  fixedAssetsApi: {
    getAssets: vi.fn(), createAsset: vi.fn(), depreciateBatch: vi.fn(),
    depreciateSingleAsset: vi.fn(), disposeAsset: vi.fn(),
  },
}));
vi.mock('../../src/api/auth', () => ({
  authApi: { getSession: vi.fn() },
}));

const queryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
const section = (code: string, lines: ReportLineItem[], subtotal = '0.00') => ({
  section_code: code, section_name: code, lines, subtotal,
});

describe('Owner-facing terminology', () => {
  it('hides the synthetic current-year earnings code on the balance sheet', async () => {
    vi.mocked(reportsApi.getBalanceSheet).mockResolvedValue({
      organization_name: 'PT Test', as_of_date: '2026-08-31', generated_at: '2026-08-31',
      current_assets: section('Aset Lancar', []), fixed_assets: section('Aset Tetap', []), total_assets: '100.00',
      current_liabilities: section('Kewajiban', []), long_term_liabilities: section('Kewajiban Jangka Panjang', []), total_liabilities: '0.00',
      equity: section('Ekuitas', [{ account_code: 'EQ-CY', line_name: 'Laba / (Rugi) Periode Berjalan', amount: '100.00', drill_down_supported: false }], '100.00'),
      total_equity: '100.00', total_liabilities_and_equity: '100.00', is_balanced: true, balancing_difference: '0.00', integrity_status: 'VALID',
    });
    render(<QueryClientProvider client={queryClient()}><MemoryRouter><BalanceSheetPage /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText('Laba / (Rugi) Periode Berjalan')).toBeInTheDocument();
    expect(screen.queryByText(/EQ-CY/)).not.toBeInTheDocument();
  });

  it('explains capitalization and useful life in natural Indonesian', async () => {
    vi.mocked(fixedAssetsApi.getAssets).mockResolvedValue([{
      id: 'asset-1', organization_id: 'org-1', asset_code: 'AST-001', asset_name: 'Laptop', asset_category: 'KOMPUTER',
      purchase_date: '2026-01-01', available_for_use_date: '2026-01-01', purchase_cost: '5000000.00', salvage_value: '0.00',
      useful_life_months: 48, depreciation_method: 'STRAIGHT_LINE', accumulated_depreciation: '0.00', net_book_value: '5000000.00',
      status: 'ACTIVE', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    } as never]);
    render(<QueryClientProvider client={queryClient()}><ToastProvider><FixedAssetsPage /></ToastProvider></QueryClientProvider>);
    expect(await screen.findByText('Laptop')).toBeInTheDocument();
    expect(screen.getByText(/minimal Rp5\.000\.000/)).toBeInTheDocument();
    expect(screen.getByText('48 bulan (4 tahun)')).toBeInTheDocument();
    expect(screen.getByText(/berorientasi pada SAK EP/i)).toBeInTheDocument();
    expect(screen.queryByText(/\$\\ge/)).not.toBeInTheDocument();
    expect(screen.queryByText(/sesuai kebijakan SAK EP/i)).not.toBeInTheDocument();
  });

  it('uses business labels in settings without tenant or cutoff jargon', async () => {
    vi.mocked(authApi.getSession).mockResolvedValue({
      accessToken: 'token', userId: 'user-1', organizationId: 'org-1',
      organizationName: 'PT Test', email: 'owner@test.local', fullName: 'Owner', role: 'ADMIN',
    });
    render(
      <QueryClientProvider client={queryClient()}>
        <MemoryRouter><AuthProvider><SettingsPage /></AuthProvider></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole('button', { name: 'Profil Perusahaan' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Periode Akuntansi' })).toBeInTheDocument();
    expect(screen.queryByText(/Tenant|Cutoff/)).not.toBeInTheDocument();
  });
});
