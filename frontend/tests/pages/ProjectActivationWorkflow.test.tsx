import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { projectsApi } from '../../src/api/projects';
import { ToastProvider } from '../../src/components/feedback/Toast';
import { ProjectDetailPage } from '../../src/pages/projects/ProjectDetailPage';
import type { ProjectResponse } from '../../src/types/api';

vi.mock('../../src/api/projects', () => ({
  projectsApi: {
    get: vi.fn(),
    updateStatus: vi.fn(),
    getProfitability: vi.fn(),
  },
}));

vi.mock('../../src/pages/projects/components/ProjectProfitabilityTab', () => ({
  ProjectProfitabilityTab: () => <div data-testid="profitability-tab">Profitability Tab Content</div>,
}));

const mockPlannedProject: ProjectResponse = {
  id: 'prj-2026-001-id',
  organization_id: 'org-1',
  project_code: 'PRJ-2026-001',
  project_name: 'Pembangunan Gardu Induk',
  customer_id: 'cust-1',
  original_contract_value: '100000000.00',
  variation_order_value: '0.00',
  revised_contract_value: '100000000.00',
  start_date: '2026-09-01',
  project_status: 'PLANNED',
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
};

const mockActiveProject: ProjectResponse = {
  ...mockPlannedProject,
  project_status: 'ACTIVE',
  updated_at: '2026-09-17T10:00:00Z',
};

const renderWithProviders = (initialEntry = '/projects/prj-2026-001-id') => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route path="/projects/:id" element={<ProjectDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
};

describe('Project Activation Workflow (PRJ-2026-001)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders PLANNED project with "Mulai Proyek (Aktifkan)" button and activates successfully', async () => {
    vi.mocked(projectsApi.get).mockResolvedValueOnce(mockPlannedProject).mockResolvedValue(mockActiveProject);
    vi.mocked(projectsApi.updateStatus).mockResolvedValue(mockActiveProject);

    const user = userEvent.setup();
    renderWithProviders();

    // Verify header and badge
    expect(await screen.findByText('PRJ-2026-001')).toBeInTheDocument();
    expect(screen.getByText('Pembangunan Gardu Induk')).toBeInTheDocument();
    expect(screen.getByText('Direncanakan')).toBeInTheDocument();

    // Verify activate button is present
    const activateButton = screen.getByRole('button', { name: /Mulai Proyek \(Aktifkan\)/i });
    expect(activateButton).toBeInTheDocument();

    // Click activate button
    await user.click(activateButton);

    // Verify projectsApi.updateStatus was called with exact arguments
    expect(projectsApi.updateStatus).toHaveBeenCalledWith('prj-2026-001-id', 'ACTIVE');

    // Verify UI updates: badge becomes AKTIF and activate button disappears
    await waitFor(() => {
      expect(screen.getByText('Aktif')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /Mulai Proyek \(Aktifkan\)/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Tandai Selesai/i })).toBeInTheDocument();

    // Success toast
    expect(await screen.findByText('Status proyek berhasil diubah ke ACTIVE.')).toBeInTheDocument();
  });

  it('handles structured 422 validation error safely without blanking the page', async () => {
    vi.mocked(projectsApi.get).mockResolvedValue(mockPlannedProject);
    const structured422Error = {
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
    vi.mocked(projectsApi.updateStatus).mockRejectedValue(structured422Error);

    const user = userEvent.setup();
    renderWithProviders();

    expect(await screen.findByText('PRJ-2026-001')).toBeInTheDocument();
    const activateButton = screen.getByRole('button', { name: /Mulai Proyek \(Aktifkan\)/i });

    await user.click(activateButton);

    // Page must remain rendered and NOT crash / go blank
    expect(screen.getByText('PRJ-2026-001')).toBeInTheDocument();
    expect(screen.getByText('Pembangunan Gardu Induk')).toBeInTheDocument();
    expect(screen.getByText('Direncanakan')).toBeInTheDocument();

    // Safe error message rendered in toast
    expect(await screen.findByText('Status proyek wajib diisi.')).toBeInTheDocument();
  });

  it('handles invalid lifecycle transition safely without blanking the page', async () => {
    vi.mocked(projectsApi.get).mockResolvedValue(mockPlannedProject);
    const lifecycleError = {
      response: {
        status: 400,
        data: {
          detail: 'Invalid lifecycle transition: cannot activate from current state.',
        },
      },
    };
    vi.mocked(projectsApi.updateStatus).mockRejectedValue(lifecycleError);

    const user = userEvent.setup();
    renderWithProviders();

    expect(await screen.findByText('PRJ-2026-001')).toBeInTheDocument();
    const activateButton = screen.getByRole('button', { name: /Mulai Proyek \(Aktifkan\)/i });

    await user.click(activateButton);

    // Page remains fully rendered and usable
    expect(screen.getByText('PRJ-2026-001')).toBeInTheDocument();
    expect(screen.getByText('Direncanakan')).toBeInTheDocument();
    expect(await screen.findByText('Invalid lifecycle transition: cannot activate from current state.')).toBeInTheDocument();
  });
});
