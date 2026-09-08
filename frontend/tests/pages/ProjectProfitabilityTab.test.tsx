import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { projectsApi } from '../../src/api/projects';
import { ProjectProfitabilityTab } from '../../src/pages/projects/components/ProjectProfitabilityTab';

vi.mock('../../src/api/projects', () => ({
  projectsApi: { getProfitability: vi.fn() },
}));

const queryClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe('Project profitability detail tab', () => {
  it('renders the financial-summary response contract without zero fallbacks', async () => {
    vi.mocked(projectsApi.getProfitability).mockResolvedValue({
      project_id: 'project-1',
      project_code: 'PRJ-001',
      project_name: 'Renovasi Kantor',
      contract: {
        original_contract_value: '500000000.00',
        variation_order_value: '0.00',
        revised_contract_value: '500000000.00',
      },
      pnl: {
        recognized_revenue: '200000000.00',
        actual_project_cost: '100000000.00',
        gross_profit: '100000000.00',
        margin_percentage: '50.00',
      },
      cash_and_billing: {
        total_invoiced: '200000000.00',
        total_cash_received: '150000000.00',
        outstanding_receivable: '50000000.00',
        cash_spent: '100000000.00',
        net_cash_flow: '50000000.00',
        project_cash_surplus: '50000000.00',
      },
      cost_categories: {
        MAT: '60000000.00',
        LAB: '40000000.00',
      },
    });

    render(
      <QueryClientProvider client={queryClient()}>
        <ProjectProfitabilityTab projectId="project-1" />
      </QueryClientProvider>,
    );

    expect(await screen.findAllByText('Rp 200.000.000')).toHaveLength(2);
    expect(screen.getAllByText('Rp 100.000.000')).toHaveLength(2);
    expect(screen.getByText('50.00%')).toBeInTheDocument();
    expect(screen.getAllByText('Rp 50.000.000')).toHaveLength(2);
    expect(screen.getByText('MAT')).toBeInTheDocument();
    expect(screen.getByText('Rp 60.000.000')).toBeInTheDocument();
    expect(screen.getByText(/Basis sementara: invoice terposting/)).toBeInTheDocument();
    expect(screen.getByText(/Belum termasuk alokasi biaya kantor umum dan pajak perusahaan/)).toBeInTheDocument();
  });
});
