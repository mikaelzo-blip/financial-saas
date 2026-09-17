import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { AppLayout } from '../../src/components/layout/AppLayout';
import { DashboardPage } from '../../src/pages/dashboard/DashboardPage';
import { ProjectListPage } from '../../src/pages/projects/ProjectListPage';
import { PaymentAccountsPage } from '../../src/pages/master/PaymentAccountsPage';
import { reportsApi } from '../../src/api/reports';
import { projectsApi } from '../../src/api/projects';
import { masterApi } from '../../src/api/master';
import { moneyMovementsApi } from '../../src/api/moneyMovements';
import { authApi } from '../../src/api/auth';
import { AuthProvider } from '../../src/store/AuthContext';

vi.mock('../../src/api/reports', () => ({
  reportsApi: {
    getDashboardSummary: vi.fn(),
    getCashFlowTrend: vi.fn(),
    getProjectPerformance: vi.fn(),
    getActionItems: vi.fn(),
    getCashBankOverview: vi.fn(),
    getARAging: vi.fn(),
    getAPAging: vi.fn(),
  },
}));

vi.mock('../../src/api/projects', () => ({
  projectsApi: {
    list: vi.fn(),
  },
}));

vi.mock('../../src/api/master', () => ({
  masterApi: {
    getPaymentAccounts: vi.fn(),
  },
}));

vi.mock('../../src/api/moneyMovements', () => ({
  moneyMovementsApi: {
    listMovements: vi.fn(),
  },
}));

vi.mock('../../src/api/auth', () => ({
  authApi: {
    getSession: vi.fn(),
  },
}));

// Mock recharts ResponsiveContainer for JSDOM
vi.mock('recharts', async () => {
  const original = await vi.importActual<any>('recharts');
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: 800, height: 400 }} data-testid="responsive-container">
        {children}
      </div>
    ),
  };
});

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

describe('Phase A UI/UX Refinements', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const session = {
      userId: 'u1',
      email: 'owner@kontraktor.test',
      fullName: 'Budi Direktur',
      role: 'ADMIN' as const,
      organizationId: 'org-phase-a',
      organizationName: 'PT Bangun Jaya Sentosa',
      accessToken: 'token-abc',
    };
    localStorage.setItem('financial_user_session', JSON.stringify(session));
    vi.spyOn(authApi, 'getSession').mockResolvedValue(session);
  });

  describe('Navigation & Layout (AppLayout)', () => {
    it('renders clean navigation without numbering and groups items', async () => {
      render(
        <AuthProvider>
          <MemoryRouter initialEntries={['/dashboard']}>
            <AppLayout />
          </MemoryRouter>
        </AuthProvider>
      );

      // Primary navigation items without numbering prefixes
      expect(screen.getAllByText('Beranda').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Inbox')).toBeInTheDocument();
      expect(screen.getByText('Proyek')).toBeInTheDocument();
      expect(screen.getByText('Kas & Bank')).toBeInTheDocument();
      expect(screen.getByText('Tagihan')).toBeInTheDocument();
      expect(screen.getByText('Laporan')).toBeInTheDocument();
      expect(screen.getByText('Pengaturan')).toBeInTheDocument();

      // Ensure NO visible numbering like "1. Dashboard", "2. WhatsApp"
      expect(screen.queryByText(/1\.\s*Dashboard/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/2\.\s*WhatsApp/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/3\.\s*Proyek/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/4\.\s*Mutasi/i)).not.toBeInTheDocument();

      // De-emphasized session indicator
      expect(screen.getByText('Sesi Aman')).toBeInTheDocument();
    });

    it('expands accordion groups on demand without losing route links', async () => {
      render(
        <AuthProvider>
          <MemoryRouter initialEntries={['/dashboard']}>
            <AppLayout />
          </MemoryRouter>
        </AuthProvider>
      );

      // Click on Tagihan group
      fireEvent.click(screen.getByText('Tagihan'));
      expect(await screen.findByText('Piutang Pelanggan')).toBeInTheDocument();
      expect(screen.getByText('Utang Vendor')).toBeInTheDocument();

      // Click on Kas & Bank group
      fireEvent.click(screen.getByText('Kas & Bank'));
      expect(await screen.findByText('Akun Kas & Bank')).toBeInTheDocument();
      expect(screen.getByText('Rekonsiliasi Bank')).toBeInTheDocument();
      expect(screen.getByText('Transaksi Jurnal')).toBeInTheDocument();
    });
  });

  describe('Dashboard (DashboardPage)', () => {
    it('renders actionable operational items, financial position, and charts', async () => {
      vi.mocked(reportsApi.getDashboardSummary).mockResolvedValue({
        organization_name: 'PT Bangun Jaya Sentosa',
        as_of_date: '2026-03-31',
        cash_and_bank_balance: '150000000.00',
        accounts_receivable_outstanding: '80000000.00',
        accounts_payable_outstanding: '45000000.00',
        cash_runway_months: '4.5',
        estimated_monthly_burn_rate: '30000000.00',
        revenue_ytd: '500000000.00',
        net_profit_ytd: '120000000.00',
        cash_in_period: '200000000.00',
        cash_out_period: '110000000.00',
        net_cash_flow: '90000000.00',
        project_spending: '75000000.00',
        active_projects_count: 3,
        review_queue_pending_count: 2,
        integrity_status: 'VALID',
      } as any);

      vi.mocked(reportsApi.getActionItems).mockResolvedValue({
        documents_requires_review: 2,
        documents_failed: 1,
        documents_ready_to_post: 3,
        unmatched_bank_movements: 4,
        overdue_ar_count: 1,
        overdue_ar_amount: '25000000.00',
        overdue_ap_count: 2,
        overdue_ap_amount: '15000000.00',
        projects_with_warning: 1,
        total_action_count: 14,
      });

      vi.mocked(reportsApi.getCashFlowTrend).mockResolvedValue({
        items: [
          { period: '2026-01', month_label: 'Jan 2026', cash_in: '100000000.00', cash_out: '60000000.00', net_cash: '40000000.00' },
          { period: '2026-02', month_label: 'Feb 2026', cash_in: '150000000.00', cash_out: '80000000.00', net_cash: '70000000.00' },
          { period: '2026-03', month_label: 'Mar 2026', cash_in: '200000000.00', cash_out: '110000000.00', net_cash: '90000000.00' },
        ],
      });

      vi.mocked(reportsApi.getProjectPerformance).mockResolvedValue({
        items: [
          {
            project_id: 'p1',
            project_code: 'PRJ-01',
            project_name: 'Gedung Wisma Niaga',
            customer_name: 'PT Mitra Usaha',
            contract_value: '500000000.00',
            actual_cost: '200000000.00',
            invoiced_amount: '300000000.00',
            cash_received: '250000000.00',
            gross_profit: '300000000.00',
            gross_margin_percentage: '60.0',
            financial_progress_percentage: '40.0',
            status: 'ACTIVE',
            health_status: 'NORMAL',
          },
        ],
        total_active_projects: 1,
        total_contract_value: '500000000.00',
        total_actual_cost: '200000000.00',
        average_margin_percentage: '60.0',
      });

      vi.mocked(reportsApi.getARAging).mockResolvedValue({
        organization_name: 'PT Bangun Jaya Sentosa',
        as_of_date: '2026-03-31',
        summary: {
          current: '50000000.00',
          days_1_30: '10000000.00',
          days_31_60: '15000000.00',
          days_61_90: '5000000.00',
          days_over_90: '0.00',
          total: '80000000.00',
        },
        invoices: [],
      });

      vi.mocked(reportsApi.getAPAging).mockResolvedValue({
        organization_name: 'PT Bangun Jaya Sentosa',
        as_of_date: '2026-03-31',
        summary: {
          current: '30000000.00',
          days_1_30: '5000000.00',
          days_31_60: '10000000.00',
          days_61_90: '0.00',
          days_over_90: '0.00',
          total: '45000000.00',
        },
        bills: [],
        unsettled_advances_total: '0.00',
      });

      render(
        <AuthProvider>
          <QueryClientProvider client={createTestQueryClient()}>
            <MemoryRouter>
              <DashboardPage />
            </MemoryRouter>
          </QueryClientProvider>
        </AuthProvider>
      );

      // Section A: Perlu Tindakan
      expect(await screen.findByText('Perlu Tindakan Operasional')).toBeInTheDocument();
      expect(screen.getByText('Dokumen Perlu Review')).toBeInTheDocument();
      expect(screen.getByText('Mutasi Belum Cocok')).toBeInTheDocument();
      expect(screen.getByText('Dokumen Siap Posting')).toBeInTheDocument();
      expect(screen.getByText('Piutang Jatuh Tempo')).toBeInTheDocument();
      expect(screen.getByText('Utang Vendor Jatuh Tempo')).toBeInTheDocument();

      // Section B: Posisi Keuangan
      expect(screen.getByText('Total Kas & Bank')).toBeInTheDocument();
      expect(screen.getByText('Piutang Usaha (AR)')).toBeInTheDocument();
      expect(screen.getByText('Utang Vendor (AP)')).toBeInTheDocument();
      expect(screen.getByText('Posisi Bersih Likuid')).toBeInTheDocument();

      // Section C: 3 Real Business Charts
      expect(screen.getByText('Arus Kas 6 Bulan Terakhir')).toBeInTheDocument();
      expect(screen.getByText('Kinerja Proyek Aktif')).toBeInTheDocument();
      expect(screen.getByText('Umur Piutang & Utang (Aging)')).toBeInTheDocument();

      // Section E: Collapsible AI advisory
      expect(screen.getByText('Wawasan & Asisten Keuangan AI (Advisory)')).toBeInTheDocument();
    });

    it('displays clean empty state when no action items are pending', async () => {
      vi.mocked(reportsApi.getDashboardSummary).mockResolvedValue({
        cash_and_bank_balance: '100000000.00',
        accounts_receivable_outstanding: '0.00',
        accounts_payable_outstanding: '0.00',
        cash_runway_months: null,
        estimated_monthly_burn_rate: '0.00',
        integrity_status: 'VALID',
      } as any);

      vi.mocked(reportsApi.getActionItems).mockResolvedValue({
        documents_requires_review: 0,
        documents_failed: 0,
        documents_ready_to_post: 0,
        unmatched_bank_movements: 0,
        overdue_ar_count: 0,
        overdue_ar_amount: '0.00',
        overdue_ap_count: 0,
        overdue_ap_amount: '0.00',
        projects_with_warning: 0,
        total_action_count: 0,
      });

      vi.mocked(reportsApi.getCashFlowTrend).mockResolvedValue({ items: [] });
      vi.mocked(reportsApi.getProjectPerformance).mockResolvedValue({
        items: [],
        total_active_projects: 0,
        total_contract_value: '0.00',
        total_actual_cost: '0.00',
        average_margin_percentage: '0.0',
      });
      vi.mocked(reportsApi.getARAging).mockResolvedValue({
        summary: { current: '0', days_1_30: '0', days_31_60: '0', days_61_90: '0', days_over_90: '0', total: '0' },
      } as any);
      vi.mocked(reportsApi.getAPAging).mockResolvedValue({
        summary: { current: '0', days_1_30: '0', days_31_60: '0', days_61_90: '0', days_over_90: '0', total: '0' },
      } as any);

      render(
        <AuthProvider>
          <QueryClientProvider client={createTestQueryClient()}>
            <MemoryRouter>
              <DashboardPage />
            </MemoryRouter>
          </QueryClientProvider>
        </AuthProvider>
      );

      expect(await screen.findByText('Semua Tugas Operasional Tuntas')).toBeInTheDocument();
      expect(screen.getByText('Data arus kas belum tersedia')).toBeInTheDocument();
      expect(screen.getByText('Belum ada proyek aktif')).toBeInTheDocument();
      expect(screen.getByText('Tidak ada piutang atau utang outstanding')).toBeInTheDocument();
    });
  });

  describe('Project List Page (ProjectListPage)', () => {
    it('renders financial summary cards and table columns with real data', async () => {
      vi.mocked(reportsApi.getProjectPerformance).mockResolvedValue({
        items: [
          {
            project_id: 'p1',
            project_code: 'PRJ-2026-001',
            project_name: 'Jembatan Mahakam II',
            customer_name: 'Dinas PU',
            contract_value: '1000000000.00',
            actual_cost: '400000000.00',
            invoiced_amount: '600000000.00',
            cash_received: '500000000.00',
            gross_profit: '600000000.00',
            gross_margin_percentage: '60.0',
            financial_progress_percentage: '40.0',
            status: 'ACTIVE',
            health_status: 'NORMAL',
          },
        ],
        total_active_projects: 1,
        total_contract_value: '1000000000.00',
        total_actual_cost: '400000000.00',
        average_margin_percentage: '60.0',
      });

      vi.mocked(projectsApi.list).mockResolvedValue([
        {
          id: 'p1',
          organization_id: 'org-phase-a',
          project_code: 'PRJ-2026-001',
          project_name: 'Jembatan Mahakam II',
          customer_id: 'c1',
          original_contract_value: '1000000000.00',
          revised_contract_value: '1000000000.00',
          variation_order_value: '0.00',
          start_date: '2026-01-01',
          project_status: 'ACTIVE' as any,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ]);

      render(
        <AuthProvider>
          <QueryClientProvider client={createTestQueryClient()}>
            <MemoryRouter>
              <ProjectListPage />
            </MemoryRouter>
          </QueryClientProvider>
        </AuthProvider>
      );

      expect(await screen.findByText('Proyek Aktif')).toBeInTheDocument();
      // Summary cards
      expect(screen.getByText('Total Nilai Kontrak')).toBeInTheDocument();
      expect(screen.getByText('Total Biaya Aktual')).toBeInTheDocument();
      expect(screen.getByText('Laba Kotor & Margin')).toBeInTheDocument();

      // Table rows
      expect(await screen.findByText('Jembatan Mahakam II')).toBeInTheDocument();
      expect(screen.getByText('PRJ-2026-001')).toBeInTheDocument();
      expect(screen.getByText('Dinas PU')).toBeInTheDocument();
      expect(screen.getAllByText('60.0%').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Cash & Bank Page (PaymentAccountsPage)', () => {
    it('renders operational workspace with balance summary, accounts list, and movements', async () => {
      vi.mocked(reportsApi.getCashBankOverview).mockResolvedValue({
        total_cash_and_bank: '250000000.00',
        total_bank: '200000000.00',
        total_cash: '50000000.00',
        unmatched_movements_count: 2,
        unmatched_amount: '12000000.00',
        accounts: [
          {
            id: 'pa1',
            name: 'BCA Operasional',
            bank_name: 'BCA',
            account_number: '1234567890',
            account_type: 'BANK',
            coa_account_code: '1101.02',
            balance: '200000000.00',
            is_active: true,
            last_movement_date: '2026-03-25',
          },
          {
            id: 'pa2',
            name: 'Kas Kantor',
            bank_name: null,
            account_number: null,
            account_type: 'KAS',
            coa_account_code: '1101.01',
            balance: '50000000.00',
            is_active: true,
            last_movement_date: '2026-03-20',
          },
        ],
      });

      vi.mocked(reportsApi.getCashFlowTrend).mockResolvedValue({
        items: [
          { period: '2026-03', month_label: 'Mar 2026', cash_in: '100000000.00', cash_out: '50000000.00', net_cash: '50000000.00' },
        ],
      });

      vi.mocked(masterApi.getPaymentAccounts).mockResolvedValue([]);
      vi.mocked(moneyMovementsApi.listMovements).mockResolvedValue([
        {
          id: 'mm1',
          organization_id: 'org-phase-a',
          payment_account_id: 'pa1',
          movement_code: 'MM-2026-001',
          direction: 'IN',
          amount: '100000000.00',
          movement_date: '2026-03-25',
          source_type: 'BANK_STATEMENT',
          description: 'Penerimaan Termin 1',
          reference_no: 'TRF-BCA-99',
        } as any,
      ]);

      render(
        <AuthProvider>
          <QueryClientProvider client={createTestQueryClient()}>
            <MemoryRouter>
              <PaymentAccountsPage />
            </MemoryRouter>
          </QueryClientProvider>
        </AuthProvider>
      );

      expect(await screen.findByText('Total Kas & Bank')).toBeInTheDocument();
      // Summary cards
      expect(screen.getByText('Saldo Rekening Bank')).toBeInTheDocument();
      expect(screen.getByText('Saldo Kas Tunai')).toBeInTheDocument();
      expect(screen.getByText('Mutasi Belum Cocok')).toBeInTheDocument();
      expect(screen.getByText('2 Mutasi')).toBeInTheDocument();

      // Accounts table
      expect(await screen.findByText('BCA Operasional')).toBeInTheDocument();
      expect(screen.getByText('Kas Kantor')).toBeInTheDocument();

      // Movements
      expect(await screen.findByText('MM-2026-001')).toBeInTheDocument();
      expect(screen.getByText('Penerimaan Termin 1')).toBeInTheDocument();
    });
  });
});
