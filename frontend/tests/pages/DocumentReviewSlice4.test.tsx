import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { CounterpartyResponse, DocumentResponse, ProjectResponse } from '../../src/types/api';

const mockProjects: ProjectResponse[] = [
  {
    id: 'prj-1111-1111',
    organization_id: 'org-0000',
    project_code: 'PRJ-2026-001',
    project_name: 'Pembangunan Jembatan',
    customer_id: 'cust-1',
    original_contract_value: '50000000.00',
    variation_order_value: '0.00',
    revised_contract_value: '50000000.00',
    start_date: '2026-01-01',
    project_status: 'ACTIVE',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const mockCounterparties: CounterpartyResponse[] = [
  {
    id: 'cparty-vendor-1',
    organization_id: 'org-0000',
    name: 'PT Semen Nusantara',
    is_customer: false,
    is_vendor: true,
    created_at: '2026-01-01T00:00:00Z',
  },
];

const slice4Document: DocumentResponse = {
  id: 'doc-slice4-1234',
  organization_id: 'org-0000',
  document_code: 'DOC-2026-000123',
  document_type: 'VENDOR_INVOICE',
  file_name: 'inv-semen.pdf',
  file_hash: 'b'.repeat(64),
  file_size_bytes: 45000,
  mime_type: 'application/pdf',
  source_channel: 'WEB',
  created_at: '2026-09-10T10:00:00Z',
  processing_status: 'REVIEW_REQUIRED',
  extracted_data: {
    invoice_number: 'INV-SN-9988',
    issuer_name: 'PT Semen Nusantara',
    transaction_date: '2026-09-08',
    due_date: '2026-10-08',
    subtotal: '10000000.00',
    vat_amount: '1100000.00',
    total_amount: '11100000.00',
    line_items: [
      {
        description: 'Semen Portland Komposit 50kg',
        quantity: 100,
        unit_price: '100000.00',
        total_amount: '10000000.00',
      },
    ],
    field_evidence: {
      total_amount: {
        value: '11100000.00',
        confidence: 0.95,
        evidence: 'Total: Rp 11.100.000',
        validation_status: 'VALID',
      },
      invoice_number: {
        value: 'INV-SN-9988',
        confidence: 0.88,
        evidence: 'No. Faktur: INV-SN-9988',
        validation_status: 'VALID',
      },
    },
  },
  matching_results: {
    ambiguous: true,
    requires_review: true,
    match_candidates: [
      {
        entity_type: 'VendorBill',
        entity_id: 'bill-cand-1',
        score: '0.88',
        confidence_band: 'HIGH',
        positive_signals: ['Nomor faktur cocok', 'Nominal cocok'],
        negative_signals: [],
        explanation: 'Faktur tagihan vendor nomor INV-SN-9988 cocok dengan data PO',
      },
      {
        entity_type: 'VendorBill',
        entity_id: 'bill-cand-2',
        score: '0.65',
        confidence_band: 'MEDIUM',
        positive_signals: ['Vendor cocok'],
        negative_signals: ['Nomor faktur berbeda'],
        explanation: 'Tagihan lain dari vendor yang sama belum lunas',
      },
    ],
  },
  confidence_scores: {
    ocr_confidence: '0.94',
    document_type_confidence: '0.98',
    entity_confidence: '0.92',
    amount_confidence: '0.95',
  },
  candidate_transaction: {
    proposed_transaction_type: 'VENDOR_BILL',
    amount: '11100000.00',
    transaction_date: '2026-09-08',
    status: 'REVIEW_REQUIRED',
  },
  review_flags: ['AMBIGUOUS_MATCH'],
  corrections: [
    {
      id: 'corr-1',
      organization_id: 'org-0000',
      document_id: 'doc-slice4-1234',
      field_path: 'invoice_number',
      old_value: 'INV-SN-9980',
      new_value: 'INV-SN-9988',
      reason: 'Koreksi salah baca OCR digit terakhir',
      corrected_by: 'user-manager-1',
      corrected_at: '2026-09-10T11:00:00Z',
    },
  ],
};

describe('DocumentReview Workspace Slice 4', () => {
  it('renders extraction fields, line items, and confidence evidence', () => {
    render(
      <DocumentReviewForm
        document={slice4Document}
        projects={mockProjects}
        counterparties={mockCounterparties}
        onSave={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    // Extraction fields
    expect(screen.getAllByText('INV-SN-9988').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Semen Portland Komposit 50kg')).toBeInTheDocument();
    expect(screen.getAllByText(/11.100.000/).length).toBeGreaterThanOrEqual(1);

    // Line items table
    expect(screen.getByText('Daftar Rincian Barang / Jasa')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();

    // Corrections audit history
    expect(screen.getByText('Riwayat Koreksi')).toBeInTheDocument();
    expect(screen.getByText(/Koreksi salah baca OCR digit terakhir/)).toBeInTheDocument();
  });

  it('renders ranked candidates, signals, conflicts, and handles candidate selection', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <DocumentReviewForm
        document={slice4Document}
        projects={mockProjects}
        counterparties={mockCounterparties}
        onSave={onSave}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    // Ranked candidates
    expect(screen.getByText('Kandidat Pencocokan')).toBeInTheDocument();
    expect(screen.getByText(/Faktur tagihan vendor nomor INV-SN-9988/)).toBeInTheDocument();
    expect(screen.getByText('Nomor faktur cocok')).toBeInTheDocument();
    expect(screen.getByText('Nomor faktur berbeda')).toBeInTheDocument();

    // Ambiguous alert
    expect(screen.getAllByText(/Pencocokan ambigu/i).length).toBeGreaterThanOrEqual(1);

    // Select candidate
    const selectCandidateButtons = screen.getAllByRole('button', { name: /Pilih Kandidat/i });
    expect(selectCandidateButtons.length).toBeGreaterThanOrEqual(2);
    await userEvent.click(selectCandidateButtons[0]);

    // Save should be called with selected_candidate_id
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ selected_candidate_id: 'bill-cand-1' }),
      expect.any(String),
    );
  });

  it('allows editing product-relevant fields and submitting corrections', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <DocumentReviewForm
        document={slice4Document}
        projects={mockProjects}
        counterparties={mockCounterparties}
        onSave={onSave}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    const invoiceInput = screen.getByLabelText('Nomor Faktur / Dokumen');
    await userEvent.clear(invoiceInput);
    await userEvent.type(invoiceInput, 'INV-CORRECTED-123');

    await userEvent.click(screen.getByRole('button', { name: 'Simpan Koreksi' }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ invoice_number: 'INV-CORRECTED-123' }),
      expect.any(String),
    );
  });

  it('calls onApprove and onReject with proper reason', async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    const onReject = vi.fn().mockResolvedValue(undefined);

    const docReady = {
      ...slice4Document,
      review_flags: [],
      processing_status: 'READY_FOR_APPROVAL' as const,
      candidate_transaction: {
        ...slice4Document.candidate_transaction,
        status: 'READY_FOR_APPROVAL',
        project_id: mockProjects[0].id,
        counterparty_id: mockCounterparties[0].id,
      },
    };

    render(
      <DocumentReviewForm
        document={docReady}
        projects={mockProjects}
        counterparties={mockCounterparties}
        onSave={vi.fn()}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );

    const approveButton = screen.getByRole('button', { name: 'Setujui untuk Diposting' });
    expect(approveButton).toBeEnabled();
    await userEvent.click(approveButton);
    expect(onApprove).toHaveBeenCalledOnce();

    const rejectButton = screen.getByRole('button', { name: 'Tolak Kandidat' });
    await userEvent.click(rejectButton);
    expect(onReject).toHaveBeenCalledWith('Verifikasi dokumen sumber');
  });
});
