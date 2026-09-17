import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { DocumentResponse } from '../../src/types/api';

const document: DocumentResponse = {
  id: 'transfer-1', organization_id: 'org-1', document_code: 'DOC-1', document_type: 'TRANSFER_PROOF',
  file_name: 'transfer.pdf', mime_type: 'application/pdf', file_size_bytes: 100, file_hash: 'a'.repeat(64),
  source_channel: 'WEB', created_at: '2026-09-10', processing_status: 'REVIEW_REQUIRED',
  extracted_data: {
    transfer_reference: 'REF-123', invoice_number: 'INV-CONTEXT', due_date: '2026-09-30',
    total_amount: '48110249.26', currency_code: 'IDR', transaction_date: '2026-08-13',
    line_items: [{ description: '3A1G', quantity: 20, unit_price: 2 }],
    transfer_details: {
      foreign: { amount: '2500.00', currency_code: 'EUR', evidence: 'Foreign Amount EUR 2500.00' },
      principal: { amount: '48110249.26', currency_code: 'IDR', evidence: 'Jumlah Rupiah 48110249.26' },
      fee: { amount: '25000.00', currency_code: 'IDR', evidence: 'Biaya Admin 25000.00' },
      debit: { amount: '48135249.26', currency_code: 'IDR', evidence: 'Total Debit 48135249.26' },
      purpose: 'Pembayaran barang', execution_status: 'REQUESTED', execution_evidence: 'Overbooking Application',
    },
  },
  candidate_transaction: {}, matching_results: {}, confidence_scores: {}, review_flags: [],
};

function renderForm(doc = document, onSave = vi.fn().mockResolvedValue(undefined)) {
  render(<DocumentReviewForm document={doc} projects={[]} counterparties={[]}
    onSave={onSave} onApprove={vi.fn()} onReject={vi.fn()} />);
  return onSave;
}

test('bank slip uses transfer fields and never renders legacy goods or due date', async () => {
  const onSave = renderForm();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  expect(screen.queryByText('Daftar Rincian Barang / Jasa')).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Jatuh Tempo/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Nomor Faktur / Dokumen')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Referensi Transfer')).toHaveValue('REF-123');
  expect(screen.getByLabelText('Tanggal Transfer / Aplikasi')).toHaveValue('2026-08-13');
  expect(screen.getByLabelText('Total Nominal')).toHaveValue('48110249.26');
  const evidence = screen.getByRole('region', { name: 'Rincian transfer dari sumber' });
  expect(within(evidence).getByText('EUR 2500.00')).toBeInTheDocument();
  expect(within(evidence).getByText('IDR 48110249.26')).toBeInTheDocument();
  expect(within(evidence).getByText('IDR 25000.00')).toBeInTheDocument();
  expect(within(evidence).getByText('IDR 48135249.26')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeDisabled();
  await userEvent.clear(screen.getByLabelText('Referensi Transfer'));
  await userEvent.type(screen.getByLabelText('Referensi Transfer'), 'REF-NEW');
  await userEvent.clear(screen.getByLabelText('Total Nominal'));
  await userEvent.type(screen.getByLabelText('Total Nominal'), '50000000');
  await userEvent.click(screen.getByRole('button', { name: 'Simpan Koreksi' }));
  const changes = onSave.mock.calls[0][0];
  expect(changes.transfer_reference).toBe('REF-NEW');
  expect(changes.amount).toBe('50000000');
  expect(changes).not.toHaveProperty('invoice_number');
  expect(changes).not.toHaveProperty('due_date');
});

test('legacy foreign transfer is never labelled rupiah and missing execution stays blocked', () => {
  renderForm({ ...document, extracted_data: { total_amount: '2500.00', currency_code: 'EUR' } });
  expect(screen.getByText('EUR 2500.00')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Setujui untuk Diposting' })).toBeDisabled();
});

test('approval handoff is not posting and cannot be approved again', () => {
  renderForm({ ...document, processing_status: 'READY_TO_POST', candidate_transaction: { status: 'READY_TO_POST' } });
  expect(screen.getByText('Belum diposting')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Setujui untuk Diposting' })).not.toBeInTheDocument();
  expect(screen.queryByText(/transaksi akuntansi terkait telah berhasil dibuat/)).not.toBeInTheDocument();
});
