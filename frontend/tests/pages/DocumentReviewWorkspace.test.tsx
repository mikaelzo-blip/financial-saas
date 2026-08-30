import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { DocumentResponse } from '../../src/types/api';

const document: DocumentResponse = {
  id: '11111111-1111-1111-1111-111111111111', organization_id: '22222222-2222-2222-2222-222222222222',
  document_code: 'DOC-2026-000001', document_type: 'VENDOR_INVOICE', file_name: 'invoice.pdf',
  file_hash: 'a'.repeat(64), file_size_bytes: 100, mime_type: 'application/pdf', source_channel: 'WEB',
  created_at: '2026-08-30T00:00:00Z', processing_status: 'REVIEW_REQUIRED',
  extracted_data: { total_amount: '15000000.00' }, matching_results: {}, confidence_scores: {},
  candidate_transaction: { project_id: null, counterparty_id: null }, review_flags: ['PROJECT_UNKNOWN'],
};

test('shows evidence flags, excludes accounting controls, and records correction reason', async () => {
  const onSave = vi.fn().mockResolvedValue(undefined); const onApprove = vi.fn().mockResolvedValue(undefined);
  render(<DocumentReviewForm document={document} onSave={onSave} onApprove={onApprove} />);
  expect(screen.getByText('PROJECT_UNKNOWN')).toBeInTheDocument();
  expect(screen.queryByLabelText(/debit/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/credit/i)).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Project ID'), '33333333-3333-3333-3333-333333333333');
  await userEvent.click(screen.getByRole('button', { name: 'Simpan Koreksi' }));
  expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ project_id: '33333333-3333-3333-3333-333333333333' }), 'Verifikasi dokumen sumber');
  expect(screen.getByRole('button', { name: 'Setujui & Buat Transaksi' })).toBeDisabled();
});
