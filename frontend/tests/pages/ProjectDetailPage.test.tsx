import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { projectsApi } from '../../src/api/projects';
import { ToastProvider } from '../../src/components/feedback/Toast';
import { ProjectDetailPage } from '../../src/pages/projects/ProjectDetailPage';
import { ProjectStatus } from '../../src/types/api';

vi.mock('../../src/api/projects', () => ({
  projectsApi: {
    get: vi.fn(),
    updateStatus: vi.fn(),
    updateVariationOrder: vi.fn(),
    getProfitability: vi.fn(),
  },
}));

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

const mockProject = {
  id: 'e3735f3a-3524-44b6-9970-32ece33277dc',
  organization_id: 'org-1',
  project_code: 'PRJ-2026-001',
  project_name: 'Demo Perbaikan Panel Listrik',
  customer_id: 'cust-1',
  customer_name: 'PT Pemberi Tugas',
  original_contract_value: '25000000.00',
  variation_order_value: '0.00',
  revised_contract_value: '25000000.00',
  start_date: '2026-01-15',
  project_status: 'PLANNED' as ProjectStatus,
  created_at: '2026-01-15T00:00:00Z',
  updated_at: '2026-01-15T00:00:00Z',
};

describe('ProjectDetailPage lifecycle and status transition', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(projectsApi.get).mockResolvedValue({ ...mockProject });
    vi.mocked(projectsApi.getProfitability).mockResolvedValue({
      project_id: mockProject.id,
      project_code: mockProject.project_code,
      project_name: mockProject.project_name,
      contract: {
        original_contract_value: '25000000.00',
        variation_order_value: '0.00',
        revised_contract_value: '25000000.00',
      },
      pnl: {
        recognized_revenue: '25000000.00',
        actual_project_cost: '73100000.00',
        gross_profit: '-48100000.00',
        margin_percentage: '-192.40',
      },
      cash_and_billing: {
        total_invoiced: '25000000.00',
        total_cash_received: '25000000.00',
        outstanding_receivable: '0.00',
        cash_spent: '2250000.00',
        net_cash_flow: '22750000.00',
        project_cash_surplus: '22750000.00',
      },
      cost_categories: {},
    });
  });

  it('renders project detail with PLANNED status and activates project on button click', async () => {
    const user = userEvent.setup();
    vi.mocked(projectsApi.updateStatus).mockResolvedValue({
      ...mockProject,
      project_status: 'ACTIVE',
    });

    render(
      <QueryClientProvider client={createQueryClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/projects/${mockProject.id}`]}>
            <Routes>
              <Route path="/projects/:id" element={<ProjectDetailPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    );

    // Wait for project code and name to render
    expect(await screen.findByText('PRJ-2026-001')).toBeInTheDocument();
    expect(screen.getByText('Demo Perbaikan Panel Listrik')).toBeInTheDocument();

    // Click "Mulai Proyek (Aktifkan)"
    const activateBtn = screen.getByRole('button', { name: /Mulai Proyek \(Aktifkan\)/i });
    expect(activateBtn).toBeInTheDocument();
    await user.click(activateBtn);

    // Verify updateStatus called with ACTIVE
    expect(projectsApi.updateStatus).toHaveBeenCalledWith(mockProject.id, 'ACTIVE');

    // Toast success should be displayed without crash
    await waitFor(() => {
      expect(screen.getByText(/Status proyek berhasil diubah ke ACTIVE/i)).toBeInTheDocument();
    });
  });

  it('handles backend 422 error gracefully without blanking screen or crashing React', async () => {
    const user = userEvent.setup();
    // Simulate FastAPI 422 Unprocessable Entity error with detail array
    const validationError = {
      isAxiosError: true,
      name: 'AxiosError',
      message: 'Request failed with status code 422',
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ['body', 'status'],
              msg: 'Field required',
              type: 'missing',
            },
          ],
        },
      },
    };
    vi.mocked(projectsApi.updateStatus).mockRejectedValue(validationError);

    render(
      <QueryClientProvider client={createQueryClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/projects/${mockProject.id}`]}>
            <Routes>
              <Route path="/projects/:id" element={<ProjectDetailPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    );

    expect(await screen.findByText('PRJ-2026-001')).toBeInTheDocument();

    const activateBtn = screen.getByRole('button', { name: /Mulai Proyek \(Aktifkan\)/i });
    await user.click(activateBtn);

    // Page must NOT crash; error toast must be shown
    await waitFor(() => {
      expect(screen.getByText(/Gagal mengubah status proyek/i)).toBeInTheDocument();
    });
    // The project header is still rendered and visible
    expect(screen.getByText('Demo Perbaikan Panel Listrik')).toBeInTheDocument();
  });
});
