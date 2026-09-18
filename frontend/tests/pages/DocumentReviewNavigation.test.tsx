import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { DocumentReviewPage } from '../../src/pages/documents/DocumentReviewPage';
import { documentsApi } from '../../src/api/documents';
import { masterApi } from '../../src/api/master';
import { projectsApi } from '../../src/api/projects';
import { ToastProvider } from '../../src/components/feedback/Toast';
import type { DocumentResponse } from '../../src/types/api';

vi.mock('../../src/api/documents', () => ({
  documentsApi: {
    get: vi.fn(),
    content: vi.fn(),
    correct: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
  },
}));

vi.mock('../../src/api/projects', () => ({
  projectsApi: {
    list: vi.fn(),
  },
}));

vi.mock('../../src/api/master', () => ({
  masterApi: {
    getCustomers: vi.fn(),
    getVendors: vi.fn(),
    getPaymentAccounts: vi.fn(),
  },
}));

const mockDoc: DocumentResponse = {
  id: 'doc-nav-123',
  organization_id: 'org-001',
  document_code: 'DOC-2026-000123',
  document_type: 'VENDOR_INVOICE',
  file_name: 'invoice.pdf',
  file_hash: 'f'.repeat(64),
  file_size_bytes: 50000,
  mime_type: 'application/pdf',
  source_channel: 'WEB',
  created_at: '2026-09-15T10:00:00Z',
  processing_status: 'REVIEW_REQUIRED',
  extracted_data: {
    invoice_number: 'INV-001',
    issuer_name: 'PT Semen Nusantara',
    total_amount: '5000000.00',
    transaction_date: '2026-09-15',
  },
  matching_results: {},
  confidence_scores: {},
  candidate_transaction: {
    proposed_transaction_type: 'VENDOR_BILL',
    amount: '5000000.00',
    transaction_date: '2026-09-15',
    project_id: 'prj-1',
    counterparty_id: 'vendor-1',
    payment_account_id: null,
  },
  review_flags: [],
};

const mockProjects = [
  {
    id: 'prj-1',
    organization_id: 'org-001',
    project_code: 'PRJ-2026-001',
    project_name: 'Proyek Utama',
    customer_id: 'cust-1',
    original_contract_value: '10000000.00',
    variation_order_value: '0.00',
    revised_contract_value: '10000000.00',
    start_date: '2026-01-01',
    project_status: 'ACTIVE',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const mockVendors = [
  {
    id: 'vendor-1',
    organization_id: 'org-001',
    name: 'PT Semen Nusantara',
    is_customer: false,
    is_vendor: true,
    created_at: '2026-01-01T00:00:00Z',
  },
];

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

describe('DocumentReviewNavigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(documentsApi.get).mockResolvedValue(mockDoc);
    vi.mocked(documentsApi.content).mockResolvedValue(new Blob(['test'], { type: 'application/pdf' }));
    vi.mocked(projectsApi.list).mockResolvedValue(mockProjects as any);
    vi.mocked(masterApi.getCustomers).mockResolvedValue([]);
    vi.mocked(masterApi.getVendors).mockResolvedValue(mockVendors as any);
    vi.mocked(masterApi.getPaymentAccounts).mockResolvedValue([]);
    vi.mocked(documentsApi.approve).mockResolvedValue({
      ...mockDoc,
      processing_status: 'APPROVED',
    });
    vi.mocked(documentsApi.correct).mockResolvedValue({
      ...mockDoc,
      extracted_data: { ...mockDoc.extracted_data, invoice_number: 'INV-EDITED' },
    });
    // Stub URL.createObjectURL
    if (!window.URL.createObjectURL) {
      window.URL.createObjectURL = () => 'blob:mock-url';
    }
  });

  it('navigates back to returnTo preserved in location state after approval', async () => {
    const queryClient = createTestQueryClient();
    const returnTarget = '/documents?page=2&status=REVIEW_REQUIRED&search=semen';

    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter
            initialEntries={[
              {
                pathname: '/documents/doc-nav-123/review',
                state: { returnTo: returnTarget },
              },
            ]}
          >
            <Routes>
              <Route path="/documents/:id/review" element={<DocumentReviewPage />} />
              <Route path="/documents" element={<div data-testid="documents-list-page">Document List Route</div>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    // Wait for document to load
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeInTheDocument();
    });

    // Click Approve
    const approveButton = screen.getByRole('button', { name: 'Setujui untuk Diposting' });
    await userEvent.click(approveButton);

    await waitFor(() => {
      expect(documentsApi.approve).toHaveBeenCalledWith('doc-nav-123');
      expect(screen.getByTestId('documents-list-page')).toBeInTheDocument();
    });
  });

  it('navigates back to returnTo preserved in location state after saving correction', async () => {
    const queryClient = createTestQueryClient();
    const returnTarget = '/documents?page=3&status=REVIEW_REQUIRED';

    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter
            initialEntries={[
              {
                pathname: '/documents/doc-nav-123/review',
                state: { returnTo: returnTarget },
              },
            ]}
          >
            <Routes>
              <Route path="/documents/:id/review" element={<DocumentReviewPage />} />
              <Route path="/documents" element={<div data-testid="documents-list-page">Document List Route</div>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Simpan Koreksi' })).toBeInTheDocument();
    });

    // Click Simpan Koreksi
    const saveButton = screen.getByRole('button', { name: 'Simpan Koreksi' });
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(documentsApi.correct).toHaveBeenCalled();
      expect(screen.getByTestId('documents-list-page')).toBeInTheDocument();
    });
  });

  it('falls back to /documents when no state or query is provided', async () => {
    const queryClient = createTestQueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={['/documents/doc-nav-123/review']}>
            <Routes>
              <Route path="/documents/:id/review" element={<DocumentReviewPage />} />
              <Route path="/documents" element={<div data-testid="documents-list-page">Document List Route</div>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeInTheDocument();
    });

    const approveButton = screen.getByRole('button', { name: 'Setujui untuk Diposting' });
    await userEvent.click(approveButton);

    await waitFor(() => {
      expect(screen.getByTestId('documents-list-page')).toBeInTheDocument();
    });
  });
});
