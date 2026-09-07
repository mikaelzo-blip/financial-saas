import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, test, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { CounterpartyResponse, DocumentResponse, ProjectResponse } from '../../src/types/api';

const projects = [
  {
    id: '33333333-3333-3333-3333-333333333333',
    organization_id: '22222222-2222-2222-2222-222222222222',
    project_code: 'PRJ-2026-001',
    project_name: 'Penyetelan Roll Arung Jeram',
    customer_id: '55555555-5555-5555-5555-555555555555',
    original_contract_value: '100000000.00',
    variation_order_value: '0.00',
    revised_contract_value: '100000000.00',
    start_date: '2026-05-01',
    project_status: 'ACTIVE',
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-05-01T00:00:00Z',
  },
  {
    id: '99999999-9999-9999-9999-999999999999',
    organization_id: '22222222-2222-2222-2222-222222222222',
    project_code: 'PRJ-CLOSED',
    project_name: 'Proyek Sudah Ditutup',
    customer_id: '55555555-5555-5555-5555-555555555555',
    original_contract_value: '100000000.00',
    variation_order_value: '0.00',
    revised_contract_value: '100000000.00',
    start_date: '2025-01-01',
    project_status: 'CLOSED',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
] satisfies ProjectResponse[];

const counterparties = [
  {
    id: '44444444-4444-4444-4444-444444444444',
    organization_id: '22222222-2222-2222-2222-222222222222',
    name: 'PT Panca Aneka Niaga',
    is_customer: false,
    is_vendor: true,
    created_at: '2026-05-01T00:00:00Z',
  },
  {
    id: '66666666-6666-6666-6666-666666666666',
    organization_id: '22222222-2222-2222-2222-222222222222',
    name: 'PT Pelanggan Saja',
    is_customer: true,
    is_vendor: false,
    created_at: '2026-05-01T00:00:00Z',
  },
] satisfies CounterpartyResponse[];

const document: DocumentResponse = {
  id: '11111111-1111-1111-1111-111111111111', organization_id: '22222222-2222-2222-2222-222222222222',
  document_code: 'DOC-2026-000001', document_type: 'VENDOR_INVOICE', file_name: 'invoice.pdf',
  file_hash: 'a'.repeat(64), file_size_bytes: 100, mime_type: 'application/pdf', source_channel: 'WEB',
  created_at: '2026-08-30T00:00:00Z', processing_status: 'REVIEW_REQUIRED',
  extracted_data: { total_amount: '15000000.00' }, matching_results: {}, confidence_scores: {},
  candidate_transaction: { project_id: null, counterparty_id: null }, review_flags: ['PROJECT_UNKNOWN'],
};

test('shows plain-language choices and records their internal IDs', async () => {
  const onSave = vi.fn().mockResolvedValue(undefined); const onApprove = vi.fn().mockResolvedValue(undefined);
  const onReject = vi.fn().mockResolvedValue(undefined);
  render(
    <DocumentReviewForm
      document={document}
      projects={projects}
      counterparties={counterparties}
      onSave={onSave}
      onApprove={onApprove}
      onReject={onReject}
    />,
  );
  expect(screen.getByText('Proyek belum dikenali')).toBeInTheDocument();
  expect(screen.queryByText('PROJECT_UNKNOWN')).not.toBeInTheDocument();
  expect(screen.getByText('Analisis')).toBeInTheDocument();
  expect(screen.getByText('Persetujuan')).toBeInTheDocument();
  expect(screen.getByText('Pencatatan')).toBeInTheDocument();
  expect(screen.getByText('Belum disetujui')).toBeInTheDocument();
  expect(screen.getByText('Belum diposting')).toBeInTheDocument();
  expect(screen.queryByLabelText(/debit/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/credit/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Project ID/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Counterparty ID/i)).not.toBeInTheDocument();
  expect(screen.getByText('Pilih nama proyek yang berkaitan dengan dokumen ini.')).toBeInTheDocument();
  expect(screen.getByText('Pilih vendor, pelanggan, atau pihak penerima dana yang tertulis pada dokumen.')).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: /Proyek Sudah Ditutup/i })).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'PT Pelanggan Saja' })).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText('Pilih Proyek'), projects[0].id);
  await userEvent.selectOptions(screen.getByLabelText('Pilih Vendor / Pelanggan'), counterparties[0].id);
  await userEvent.click(screen.getByRole('button', { name: 'Simpan Koreksi' }));
  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ project_id: projects[0].id, counterparty_id: counterparties[0].id }),
    'Verifikasi dokumen sumber',
  );
  expect(screen.getByRole('button', { name: 'Setujui & Buat Transaksi' })).toBeDisabled();
  await userEvent.click(screen.getByRole('button', { name: 'Tolak Kandidat' }));
  expect(onReject).toHaveBeenCalledWith('Verifikasi dokumen sumber');
});

test('explains evidence-only documents without technical jargon', () => {
  render(
    <DocumentReviewForm
      document={{ ...document, document_type: 'SPK', candidate_transaction: {} }}
      projects={projects}
      counterparties={counterparties}
      onSave={vi.fn()}
      onApprove={vi.fn()}
      onReject={vi.fn()}
    />,
  );
  expect(screen.getByText('Dokumen pendukung saja')).toBeInTheDocument();
  expect(screen.getByText(/disimpan sebagai bukti dan tidak langsung mengubah saldo/i)).toBeInTheDocument();
  expect(screen.queryByText(/Evidence-Only/i)).not.toBeInTheDocument();
  expect(screen.getByText('Detail Teknis')).toBeInTheDocument();
});
