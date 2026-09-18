import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import { StatusBadge } from '../../src/components/ui/StatusBadge';
import { formatFailureReason } from '../../src/utils/formatters';
import type { DocumentResponse } from '../../src/types/api';

describe('Requirement C & E: Caption separation and human-friendly status', () => {
  const baseDoc: DocumentResponse = {
    id: 'doc-wa-001',
    organization_id: 'org-001',
    document_code: 'DOC-2026-0001',
    document_type: 'VENDOR_INVOICE',
    file_name: 'invoice-sample.pdf',
    file_hash: 'a'.repeat(64),
    file_size_bytes: 12345,
    mime_type: 'application/pdf',
    source_channel: 'WHATSAPP',
    created_at: '2026-09-15T10:00:00Z',
    processing_status: 'REVIEW_REQUIRED',
    review_flags: ['AMBIGUOUS_MATCH'],
    confidence_scores: {},
    extracted_data: {
      invoice_number: 'INV-123',
      total_amount: 15600000,
    },
    matching_results: {},
    candidate_transaction: {},
    source_metadata: {
      caption: 'po roll arjer',
      wamid: 'wamid.test.123',
      sender_phone: '+62812345678',
    },
  };

  it('renders "Keterangan dari Pengirim" separately without replacing OCR extraction data', () => {
    render(
      <DocumentReviewForm
        document={baseDoc}
        projects={[]}
        counterparties={[]}
        paymentAccounts={[]}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onApprove={vi.fn().mockResolvedValue(undefined)}
        onReject={vi.fn().mockResolvedValue(undefined)}
      />
    );

    // Sender caption is exposed under dedicated heading
    expect(screen.getByLabelText('Keterangan dari Pengirim')).toBeInTheDocument();
    expect(screen.getByText('po roll arjer')).toBeInTheDocument();
    expect(
      screen.getByText(/Keterangan pesan pengirim dicatat terpisah sebagai petunjuk pencocokan/i)
    ).toBeInTheDocument();

    // OCR extracted data is preserved
    expect(screen.getByDisplayValue('INV-123')).toBeInTheDocument();
  });

  it('translates technical failure codes into human-friendly Indonesian text', () => {
    expect(formatFailureReason('DOWNLOAD_FAILED')).toBe('Gagal mengunduh file dari WhatsApp');
    expect(formatFailureReason('OCR_CORRUPT_PAYLOAD')).toBe('File dokumen rusak atau tidak terbaca');
    expect(formatFailureReason('UNSUPPORTED_MEDIA')).toBe('Format file tidak didukung');
    expect(formatFailureReason('MEDIA_TOO_LARGE')).toBe('Ukuran file melebihi batas');
  });

  it('presents operational status labels clearly and distinguishes REVIEW_REQUIRED from technical failure', () => {
    const { rerender } = render(<StatusBadge status="REVIEW_REQUIRED" />);
    const reviewBadge = screen.getByText('Perlu Diperiksa');
    expect(reviewBadge).toBeInTheDocument();
    expect(reviewBadge.className).toMatch(/amber|yellow/);

    rerender(<StatusBadge status="FAILED" />);
    const failedBadge = screen.getByText('Gagal Diproses');
    expect(failedBadge).toBeInTheDocument();
    expect(failedBadge.className).toMatch(/rose|red/);

    rerender(<StatusBadge status="POSTED" />);
    expect(screen.getByText('Sudah Diposting')).toBeInTheDocument();

    rerender(<StatusBadge status="QUEUED" />);
    expect(screen.getByText('Menunggu')).toBeInTheDocument();

    rerender(<StatusBadge status="EXTRACTING" />);
    expect(screen.getByText('Sedang Diproses')).toBeInTheDocument();
  });
});
