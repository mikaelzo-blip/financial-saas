import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import { isPaymentAccountRequired } from '../../src/utils/documentReview';
import type { CounterpartyResponse, DocumentResponse, PaymentAccountResponse, ProjectResponse } from '../../src/types/api';

const mockProjects: ProjectResponse[] = [
  {
    id: 'prj-1',
    organization_id: 'org-1',
    project_code: 'PRJ-2026-001',
    project_name: 'Pembangunan Ruko',
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
    id: 'vendor-1',
    organization_id: 'org-1',
    name: 'PT Semen Nusantara',
    is_customer: false,
    is_vendor: true,
    created_at: '2026-01-01T00:00:00Z',
  },
];

const mockPaymentAccounts: PaymentAccountResponse[] = [
  {
    id: 'pa-1',
    organization_id: 'org-1',
    account_type: 'BANK',
    name: 'BCA Operasional',
    bank_name: 'BCA',
    account_number: '1234567890',
    coa_account_id: 'coa-1',
    coa_account_code: '1101-01',
    coa_account_name: 'Kas di Bank BCA',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
  },
];

describe('DocumentTypeAwareReview', () => {
  it('hides line items table and shows transfer details for TRANSFER_PROOF documents', () => {
    const transferDoc: DocumentResponse = {
      id: 'doc-trf-1',
      organization_id: 'org-1',
      document_code: 'DOC-2026-000999',
      document_type: 'TRANSFER_PROOF',
      file_name: 'bukti-transfer.jpg',
      file_hash: 'd'.repeat(64),
      file_size_bytes: 50000,
      mime_type: 'image/jpeg',
      source_channel: 'WHATSAPP',
      created_at: '2026-09-15T12:00:00Z',
      processing_status: 'REVIEW_REQUIRED',
      extracted_data: {
        transfer_reference: 'TRF-BCA-20260915-01',
        sender_name: 'CV Berkah Sentosa',
        source_bank: 'BCA',
        destination_bank: 'Mandiri',
        destination_account: '1420012345678',
        total_amount: '8500000.00',
        transaction_date: '2026-09-15',
        line_items: [
          { description: 'Synthetic item', quantity: 1, unit_price: 8500000, total_amount: 8500000 },
        ],
      },
      matching_results: {},
      confidence_scores: {},
      candidate_transaction: {
        proposed_transaction_type: 'PAY_VENDOR_BILL',
        amount: '8500000.00',
        transaction_date: '2026-09-15',
        project_id: mockProjects[0].id,
        payment_account_id: 'pa-1',
      },
      review_flags: [],
    };

    render(
      <DocumentReviewForm
        document={transferDoc}
        projects={mockProjects}
        counterparties={mockCounterparties}
        paymentAccounts={mockPaymentAccounts}
        onSave={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    // Assert line-item goods/services table is NOT displayed
    expect(screen.queryByText('Daftar Rincian Barang / Jasa')).not.toBeInTheDocument();

    // Assert transfer proof metadata card is displayed
    expect(screen.getByText('Nomor Referensi Transfer:')).toBeInTheDocument();
    expect(screen.getByText('TRF-BCA-20260915-01')).toBeInTheDocument();
    expect(screen.getByText('Bank Asal:')).toBeInTheDocument();
    expect(screen.getByText('BCA')).toBeInTheDocument();
    expect(screen.getByText('Bank Tujuan:')).toBeInTheDocument();
    expect(screen.getByText('Mandiri')).toBeInTheDocument();
    expect(screen.getByText('Rekening Tujuan:')).toBeInTheDocument();
    expect(screen.getByText('1420012345678')).toBeInTheDocument();
  });

  it('renders line items table for VENDOR_INVOICE documents with line items', () => {
    const invoiceDoc: DocumentResponse = {
      id: 'doc-inv-1',
      organization_id: 'org-1',
      document_code: 'DOC-2026-000888',
      document_type: 'VENDOR_INVOICE',
      file_name: 'invoice-vendor.pdf',
      file_hash: 'e'.repeat(64),
      file_size_bytes: 75000,
      mime_type: 'application/pdf',
      source_channel: 'WEB',
      created_at: '2026-09-15T10:00:00Z',
      processing_status: 'REVIEW_REQUIRED',
      extracted_data: {
        invoice_number: 'INV-SN-1234',
        issuer_name: 'PT Semen Nusantara',
        total_amount: '5000000.00',
        transaction_date: '2026-09-15',
        line_items: [
          { description: 'Semen Gresik 50kg', quantity: 50, unit_price: 100000, total_amount: 5000000 },
        ],
      },
      matching_results: {},
      confidence_scores: {},
      candidate_transaction: {
        proposed_transaction_type: 'VENDOR_BILL',
        amount: '5000000.00',
        transaction_date: '2026-09-15',
        project_id: mockProjects[0].id,
        counterparty_id: mockCounterparties[0].id,
      },
      review_flags: [],
    };

    render(
      <DocumentReviewForm
        document={invoiceDoc}
        projects={mockProjects}
        counterparties={mockCounterparties}
        paymentAccounts={mockPaymentAccounts}
        onSave={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    // Line items table IS displayed
    expect(screen.getByText('Daftar Rincian Barang / Jasa')).toBeInTheDocument();
    expect(screen.getByText('Semen Gresik 50kg')).toBeInTheDocument();
    // Transfer fields NOT displayed
    expect(screen.queryByText('Nomor Referensi Transfer:')).not.toBeInTheDocument();
  });

  it('evaluates payment account requirement by document type and transaction type', () => {
    expect(isPaymentAccountRequired(undefined, 'TRANSFER_PROOF')).toBe(true);
    expect(isPaymentAccountRequired(undefined, 'RECEIPT')).toBe(true);
    expect(isPaymentAccountRequired('DIRECT_PURCHASE')).toBe(true);
    expect(isPaymentAccountRequired('CUSTOMER_PAYMENT')).toBe(true);
    expect(isPaymentAccountRequired('PAY_VENDOR_BILL')).toBe(true);
    expect(isPaymentAccountRequired('VENDOR_BILL', 'VENDOR_INVOICE')).toBe(false);
    expect(isPaymentAccountRequired('CUSTOMER_INVOICE', 'CUSTOMER_INVOICE')).toBe(false);
  });
});
