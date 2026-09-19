import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { DocumentResponse } from '../../src/types/api';

const baseDoc = (overrides: Partial<DocumentResponse> = {}): DocumentResponse =>
  ({
    id: 'doc-1',
    document_code: 'DOC-1',
    document_type: 'VENDOR_INVOICE',
    processing_status: 'REVIEW_REQUIRED',
    file_name: 'x.pdf',
    mime_type: 'application/pdf',
    file_size_bytes: 1,
    file_hash: 'h',
    source_channel: 'UPLOAD',
    source_metadata: {},
    created_at: '2026-09-16T00:00:00Z',
    extracted_data: {},
    matching_results: {},
    confidence_scores: {},
    candidate_transaction: {
      id: 'c1',
      proposed_transaction_type: 'VENDOR_BILL',
      amount: '1000000.00',
      transaction_date: '2026-09-16',
      status: 'REVIEW_REQUIRED',
    },
    review_flags: [],
    corrections: [{ id: 'k1', field_path: 'amount', old_value: '1', new_value: '2', reason: 'x', corrected_at: '2026-09-16T00:00:00Z' }],
    ...overrides,
  }) as unknown as DocumentResponse;

const noop = async () => {};

describe('simplified review form', () => {
  it('hides debug panels and reason input for financial documents', () => {
    render(
      <DocumentReviewForm document={baseDoc()} projects={[]} counterparties={[]} onSave={noop} onApprove={noop} onReject={noop} />,
    );
    expect(screen.queryByText('Riwayat Koreksi')).not.toBeInTheDocument();
    expect(screen.queryByText('Detail Teknis')).not.toBeInTheDocument();
    expect(screen.queryByText('Mengapa data ini diubah?')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Simpan Koreksi' })).not.toBeInTheDocument();
  });

  it('shows a single save button for evidence documents', () => {
    render(
      <DocumentReviewForm
        document={baseDoc({ document_type: 'BANK_STATEMENT', candidate_transaction: { id: 'c', status: 'REVIEW_REQUIRED' } as never })}
        projects={[]}
        counterparties={[]}
        onSave={noop}
        onApprove={noop}
        onReject={noop}
      />,
    );
    expect(screen.getByRole('button', { name: 'Simpan Dokumen' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Setujui untuk Diposting' })).not.toBeInTheDocument();
  });

  it('keeps approve enabled while review flags exist', () => {
    render(
      <DocumentReviewForm document={baseDoc({ review_flags: ['AMOUNT_MISMATCH'] })} projects={[]} counterparties={[]} onSave={noop} onApprove={noop} onReject={noop} />,
    );
    expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeEnabled();
  });

  it('hides the line-items table for evidence documents', () => {
    render(
      <DocumentReviewForm
        document={baseDoc({
          document_type: 'BANK_STATEMENT',
          candidate_transaction: { id: 'c', status: 'REVIEW_REQUIRED' } as never,
          extracted_data: { line_items: [{ description: 'IDR', line_total: '750.00' }] },
        })}
        projects={[]}
        counterparties={[]}
        onSave={noop}
        onApprove={noop}
        onReject={noop}
      />,
    );
    expect(screen.queryByText('Daftar Rincian Barang / Jasa')).not.toBeInTheDocument();
  });
});
