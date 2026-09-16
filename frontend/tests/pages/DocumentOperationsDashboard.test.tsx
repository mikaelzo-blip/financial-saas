import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { documentsApi } from '../../src/api/documents';
import { DocumentListPage } from '../../src/pages/documents/DocumentListPage';
import { ToastProvider } from '../../src/components/feedback/Toast';
import type {
  DocumentOperationsSummaryResponse,
  DocumentOperationalListResponse,
  DocumentOperationalItem,
  WhatsAppIntegrationStatusResponse,
} from '../../src/types/api';

vi.mock('../../src/api/documents', () => ({
  documentsApi: {
    operationsSummary: vi.fn(),
    operationsList: vi.fn(),
    retry: vi.fn(),
    postAccounting: vi.fn(),
    list: vi.fn(),
    whatsappStatus: vi.fn(),
  },
}));

const mockSummary: DocumentOperationsSummaryResponse = {
  status_counts: {
    received: 1,
    queued: 2,
    processing: 1,
    review_required: 3,
    ready_for_approval: 0,
    ready_to_post: 2,
    posted: 5,
    rejected: 1,
    failed: 1,
    total: 16,
  },
  flag_counts: {
    AMBIGUOUS_MATCH: 2,
    PROJECT_UNKNOWN: 1,
    DUPLICATE_SUSPECTED: 1,
  },
  queue_health: {
    pending_count: 2,
    running_count: 1,
    failed_count: 1,
    completed_count: 10,
    retrying_count: 1,
    oldest_pending_seconds: 1200,
    oldest_running_seconds: 300,
    near_max_attempts_count: 1,
    latest_failure: {
      job_type: 'DOCUMENT_PROCESS',
      failure_message: 'File header corrupt or invalid format.',
      attempt_count: 3,
      failed_at: '2026-09-16T08:00:00Z',
    },
  },
  actionable_counts: {
    needs_review: 3,
    ready_to_post: 2,
    failed: 1,
    retrying: 1,
    queued: 2,
    processing: 1,
    posted: 5,
  },
};

const mockItems: DocumentOperationalItem[] = [
  {
    id: 'doc-1',
    organization_id: 'org-1',
    document_code: 'DOC-2026-000001',
    file_name: 'invoice_semen.pdf',
    file_size_bytes: 25000,
    source_channel: 'WEB',
    document_type: 'VENDOR_INVOICE',
    received_at: '2026-09-16T07:00:00Z',
    updated_at: '2026-09-16T07:05:00Z',
    processing_status: 'REVIEW_REQUIRED',
    review_flags: ['AMBIGUOUS_MATCH', 'PROJECT_UNKNOWN'],
    counterparty_name: 'PT Semen Nusantara',
    project_name: 'Proyek Bendungan',
    amount: 5000000,
    processing_attempts: 0,
    age_seconds: 3600,
    age_display: '1j',
    is_stuck: false,
    can_review: true,
    can_retry: false,
    can_post: false,
  },
  {
    id: 'doc-2',
    organization_id: 'org-1',
    document_code: 'DOC-2026-000002',
    file_name: 'nota_bbm.pdf',
    file_size_bytes: 12000,
    source_channel: 'WHATSAPP',
    document_type: 'RECEIPT',
    received_at: '2026-09-16T07:30:00Z',
    updated_at: '2026-09-16T07:35:00Z',
    processing_status: 'READY_TO_POST',
    review_flags: [],
    counterparty_name: 'SPBU 34-1234',
    amount: 750000,
    processing_attempts: 0,
    age_seconds: 1800,
    age_display: '30m',
    is_stuck: false,
    can_review: false,
    can_retry: false,
    can_post: true,
  },
  {
    id: 'doc-3',
    organization_id: 'org-1',
    document_code: 'DOC-2026-000003',
    file_name: 'spk_kontrak.pdf',
    file_size_bytes: 55000,
    source_channel: 'API',
    document_type: 'CONTRACT',
    received_at: '2026-09-16T06:00:00Z',
    updated_at: '2026-09-16T06:10:00Z',
    processing_status: 'POSTED',
    review_flags: [],
    counterparty_name: 'PT Mitra Konstruksi',
    amount: 25000000,
    processing_attempts: 0,
    age_seconds: 7200,
    age_display: '2j',
    is_stuck: false,
    converted_transaction_id: 'trx-123',
    converted_transaction_code: 'TRX-2026-000099',
    can_review: false,
    can_retry: false,
    can_post: false,
  },
  {
    id: 'doc-4',
    organization_id: 'org-1',
    document_code: 'DOC-2026-000004',
    file_name: 'corrupt_scan.pdf',
    file_size_bytes: 5000,
    source_channel: 'WEB',
    document_type: 'RECEIPT',
    received_at: '2026-09-16T05:00:00Z',
    updated_at: '2026-09-16T05:05:00Z',
    processing_status: 'FAILED',
    review_flags: [],
    failure_code: 'OCR_CORRUPT_PAYLOAD',
    failure_message: 'File header corrupt or invalid format.',
    processing_attempts: 3,
    age_seconds: 10800,
    age_display: '3j',
    is_stuck: false,
    can_review: false,
    can_retry: true,
    can_post: false,
  },
];

const mockListResponse: DocumentOperationalListResponse = {
  items: mockItems,
  total: 4,
  page: 1,
  limit: 10,
  pages: 1,
};

const mockWhatsAppStatus: WhatsAppIntegrationStatusResponse = {
  enabled: true,
  connection_state: 'CONNECTED',
  last_connected_at: '2026-09-16T08:00:00Z',
  last_message_at: '2026-09-16T08:05:00Z',
  last_successful_ingestion_at: '2026-09-16T08:05:00Z',
  last_error_code: null,
  last_error_message_safe: null,
  pending_handoff_count: 2,
  integration_version: '1.0.0',
  provider: 'baileys',
};

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <DocumentListPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe('Document Operational Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(documentsApi.operationsSummary).mockResolvedValue(mockSummary);
    vi.mocked(documentsApi.operationsList).mockResolvedValue(mockListResponse);
    vi.mocked(documentsApi.whatsappStatus).mockResolvedValue(mockWhatsAppStatus);
  });

  it('renders WhatsApp integration health card with connection state and metrics', async () => {
    renderDashboard();

    expect(await screen.findByText('Integrasi WhatsApp')).toBeInTheDocument();
    expect(await screen.findByText('Terhubung')).toBeInTheDocument();
    expect(screen.getByText('Antrean / Pending:')).toBeInTheDocument();
  });

  it('renders actionable summary cards and queue metrics', async () => {
    renderDashboard();

    // Summary cards
    expect(await screen.findByText('Perlu Review')).toBeInTheDocument();
    expect(screen.getByText('Siap Posting')).toBeInTheDocument();
    expect(screen.getByText('Gagal')).toBeInTheDocument();

    // Queue health section
    expect(screen.getByText('Antrean & Background Worker')).toBeInTheDocument();
    expect(await screen.findByText('Pencocokan Ambiguitas')).toBeInTheDocument();
  });

  it('renders operational table with correct status labels and flags', async () => {
    renderDashboard();

    expect(await screen.findByText('DOC-2026-000001')).toBeInTheDocument();
    expect(screen.getByText('invoice_semen.pdf')).toBeInTheDocument();
    expect(screen.getByText('DOC-2026-000002')).toBeInTheDocument();
    expect(screen.getByText('nota_bbm.pdf')).toBeInTheDocument();

    // Ready to post button visible
    expect(screen.getByText('Posting')).toBeInTheDocument();

    // Converted transaction reference visible
    expect(screen.getByText('TRX-2026-000099')).toBeInTheDocument();

    // Failure code and attempt count visible for failed item
    expect(screen.getByText('OCR_CORRUPT_PAYLOAD')).toBeInTheDocument();
    expect(screen.getByText('Percobaan: 3x')).toBeInTheDocument();

    // Retry button visible for failed item
    expect(screen.getByText('Coba Lagi')).toBeInTheDocument();
  });

  it('clicking a summary card filters the operational list', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const needsReviewCard = await screen.findByText('Perlu Review');
    await user.click(needsReviewCard);

    await waitFor(() => {
      expect(documentsApi.operationsList).toHaveBeenCalledWith(
        expect.objectContaining({ action_filter: 'NEEDS_REVIEW' })
      );
    });
  });

  it('allows sorting when clicking column headers', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const codeHeader = await screen.findByText('Kode & Berkas');
    await user.click(codeHeader);

    await waitFor(() => {
      expect(documentsApi.operationsList).toHaveBeenCalledWith(
        expect.objectContaining({ sort_by: 'document_code', sort_dir: 'asc' })
      );
    });
  });

  it('allows filtering by document type', async () => {
    const user = userEvent.setup();
    renderDashboard();

    const docTypeSelect = await screen.findByLabelText('Filter Jenis Dokumen');
    expect(docTypeSelect).toBeInTheDocument();

    await user.selectOptions(docTypeSelect, 'VENDOR_INVOICE');
    await waitFor(() => {
      expect(documentsApi.operationsList).toHaveBeenCalledWith(
        expect.objectContaining({ document_type: 'VENDOR_INVOICE' })
      );
    });
  });

  it('handles empty states cleanly', async () => {
    vi.mocked(documentsApi.operationsList).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      limit: 10,
      pages: 1,
    });

    renderDashboard();
    expect(await screen.findByText(/Tidak ada dokumen/i)).toBeInTheDocument();
  });

  it('handles backend error state without crashing', async () => {
    vi.mocked(documentsApi.operationsSummary).mockRejectedValue(new Error('Network error'));
    vi.mocked(documentsApi.operationsList).mockRejectedValue(new Error('Network error'));

    renderDashboard();
    expect(await screen.findByText(/Gagal memuat/i)).toBeInTheDocument();
  });
});
