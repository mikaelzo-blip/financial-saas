import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { DocumentResponse, PaymentAccountResponse } from '../../src/types/api';

const transferProofDoc: DocumentResponse = {
  id: 'doc-transfer-proof-1',
  organization_id: 'org-001',
  document_code: 'DOC-2026-0099',
  document_type: 'TRANSFER_PROOF',
  file_name: 'bukti-transfer.pdf',
  file_hash: 'a'.repeat(64),
  file_size_bytes: 12345,
  mime_type: 'application/pdf',
  source_channel: 'WHATSAPP',
  created_at: '2026-09-15T10:00:00Z',
  processing_status: 'READY_FOR_APPROVAL',
  review_flags: [],
  confidence_scores: {},
  extracted_data: { transfer_reference: '20708003319', total_amount: 48930988.86 },
  matching_results: {},
  candidate_transaction: {
    id: 'doc-transfer-proof-1',
    amount: '48930988.86',
    transaction_date: '2026-08-13',
    status: 'READY_FOR_APPROVAL',
  },
  source_metadata: {},
};

const mandiriAccount: PaymentAccountResponse = {
  id: 'acc-1',
  organization_id: 'org-001',
  coa_account_id: 'coa-1101',
  coa_account_code: '1101',
  coa_account_name: 'Kas dan Bank',
  name: 'Mandiri',
  account_type: 'BANK',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
};

describe('DocumentReviewForm - transfer proof recording category', () => {
  it('shows the Jenis Pencatatan picker for TRANSFER_PROOF', () => {
    render(
      <DocumentReviewForm
        document={transferProofDoc}
        projects={[]}
        counterparties={[]}
        paymentAccounts={[mandiriAccount]}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onApprove={vi.fn().mockResolvedValue(undefined)}
        onReject={vi.fn().mockResolvedValue(undefined)}
      />
    );

    expect(screen.getByLabelText(/jenis pencatatan/i)).toBeInTheDocument();
  });
});
