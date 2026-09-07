import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { projectsApi } from '../../src/api/projects';
import { reportsApi } from '../../src/api/reports';
import { ProjectProfitabilityPage } from '../../src/pages/reports/ProjectProfitabilityPage';

vi.mock('../../src/api/projects', () => ({
  projectsApi: { list: vi.fn() },
}));
vi.mock('../../src/api/reports', () => ({
  reportsApi: { getProjectProfitability: vi.fn(), downloadReport: vi.fn() },
}));
vi.mock('../../src/components/ai/ProjectHealthCard', () => ({
  ProjectHealthCard: () => null,
}));

const queryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe('Project profitability management report', () => {
  it('renders backend management metrics with permanent scope language', async () => {
    vi.mocked(projectsApi.list).mockResolvedValue([
      {
        id: 'project-1',
        organization_id: 'org-1',
        project_code: 'PRJ-001',
        project_name: 'Renovasi Kantor',
        customer_id: 'customer-1',
        original_contract_value: '500000000.00',
        variation_order_value: '0.00',
        revised_contract_value: '500000000.00',
        start_date: '2026-01-01',
        project_status: 'ACTIVE',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ] as never);
    vi.mocked(reportsApi.getProjectProfitability).mockResolvedValue({
      organization_name: 'PT Test',
      project_id: 'project-1',
      project_code: 'PRJ-001',
      project_name: 'Renovasi Kantor',
      client_name: 'PT Pemilik Gedung',
      status: 'ACTIVE',
      original_contract_value: '500000000.00',
      variation_orders_value: '0.00',
      revised_contract_value: '500000000.00',
      invoiced_amount: '200000000.00',
      cash_received: '150000000.00',
      receivable_outstanding: '50000000.00',
      retention_withheld: '10000000.00',
      revenue_recognized: '175000000.00',
      cost_breakdown: [],
      direct_project_cost: '100000000.00',
      total_project_cost: '100000000.00',
      gross_profit: '100000000.00',
      gross_project_profit: '100000000.00',
      gross_margin_percentage: '50.00',
      project_cash_position: '50000000.00',
      cash_spent: '100000000.00',
      pph_withheld: '12000000.00',
      loan_principal_paid: '25000000.00',
      project_fee: '5000000.00',
      bank_charges: '1000000.00',
      pph_final: '2000000.00',
      has_net_contribution_data: false,
      project_net_contribution: null,
    });

    render(
      <QueryClientProvider client={queryClient()}>
        <ProjectProfitabilityPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('PT Pemilik Gedung')).toBeInTheDocument();
    expect(screen.getByText('Rp 10.000.000')).toBeInTheDocument();
    expect(screen.getByText('Rp 12.000.000')).toBeInTheDocument();
    expect(screen.getByText('Rp 25.000.000')).toBeInTheDocument();
    expect(screen.getByText(/Belum termasuk alokasi biaya kantor umum dan pajak perusahaan/)).toBeInTheDocument();
    expect(screen.getByText(/Pelanggan:/)).toBeInTheDocument();
    expect(screen.getByText('Sudah Ditagih')).toBeInTheDocument();
    expect(screen.getByText('Rp 200.000.000')).toBeInTheDocument();
    expect(screen.queryByText('Rp 175.000.000')).not.toBeInTheDocument();
    expect(screen.getByText(/Basis sementara pendapatan proyek: invoice terposting/)).toBeInTheDocument();
    expect(screen.getByText('Belum tersedia')).toBeInTheDocument();
    expect(screen.getByText(/Butuh data fee, bunga, atau PPh Final terposting/)).toBeInTheDocument();
    expect(screen.queryByText(/Laba Bersih Proyek/i)).not.toBeInTheDocument();
  });
});
