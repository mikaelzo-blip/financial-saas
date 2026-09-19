import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import {
  formatDocumentActionError,
  isPaymentAccountRequired,
  validateDocumentReviewForm,
} from '../../src/utils/documentReview';
import type {
  CounterpartyResponse,
  DocumentResponse,
  PaymentAccountResponse,
  ProjectResponse,
} from '../../src/types/api';

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
    name: 'PT Mitra Material',
    is_customer: false,
    is_vendor: true,
    created_at: '2026-01-01T00:00:00Z',
  },
];

const mockPaymentAccounts: PaymentAccountResponse[] = [
  {
    id: 'pa-bank-bca',
    organization_id: 'org-0000',
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
  {
    id: 'pa-bank-mandiri-inactive',
    organization_id: 'org-0000',
    account_type: 'BANK',
    name: 'Mandiri Lama',
    bank_name: 'Mandiri',
    account_number: '9876543210',
    coa_account_id: 'coa-2',
    coa_account_code: '1101-02',
    coa_account_name: 'Kas di Bank Mandiri',
    is_active: false,
    created_at: '2026-01-01T00:00:00Z',
  },
];

const baseDocument: DocumentResponse = {
  id: 'doc-workflow-test',
  organization_id: 'org-0000',
  document_code: 'DOC-2026-000555',
  document_type: 'RECEIPT',
  file_name: 'receipt-solar.pdf',
  file_hash: 'c'.repeat(64),
  file_size_bytes: 32000,
  mime_type: 'application/pdf',
  source_channel: 'WEB',
  created_at: '2026-09-12T10:00:00Z',
  processing_status: 'READY_FOR_APPROVAL',
  extracted_data: {
    invoice_number: 'REC-SOLAR-001',
    issuer_name: 'SPBU Pertamina',
    total_amount: '500000.00',
    transaction_date: '2026-09-12',
  },
  matching_results: {},
  confidence_scores: {
    ocr_confidence: '0.95',
    document_type_confidence: '0.98',
    amount_confidence: '0.99',
  },
  candidate_transaction: {
    proposed_transaction_type: 'DIRECT_PURCHASE',
    amount: '500000.00',
    transaction_date: '2026-09-12',
    project_id: mockProjects[0].id,
    payment_account_id: null,
    status: 'READY_FOR_APPROVAL',
  },
  review_flags: [],
};

describe('Document Review Approval Workflow & Invariants', () => {
  describe('formatDocumentActionError', () => {
    it('translates 422 missing required fields to clear Indonesian message', () => {
      const axiosErr = {
        response: {
          data: {
            detail: 'Candidate is missing required fields for approval',
          },
        },
      };
      expect(formatDocumentActionError(axiosErr)).toBe(
        'Dokumen belum dapat disetujui karena data wajib belum lengkap.',
      );
    });

    it('translates customer payment allocation error to Indonesian message', () => {
      const axiosErr = {
        response: {
          data: {
            detail: 'Customer payment requires an invoice allocation',
          },
        },
      };
      expect(formatDocumentActionError(axiosErr)).toBe(
        'Pembayaran pelanggan memerlukan alokasi faktur penjualan.',
      );
    });

    it('translates payment account unavailable to Indonesian message', () => {
      const axiosErr = {
        response: {
          data: {
            detail: 'Payment account is not available or not active in this organization',
          },
        },
      };
      expect(formatDocumentActionError(axiosErr)).toBe('Pilih rekening pembayaran terlebih dahulu.');
    });

    it('translates raw status code 422 Error instance without technical jargon', () => {
      const err = new Error('Request failed with status code 422');
      expect(formatDocumentActionError(err)).toBe(
        'Dokumen belum dapat disetujui karena data wajib belum lengkap.',
      );
    });
  });

  describe('isPaymentAccountRequired & validateDocumentReviewForm', () => {
    it('determines payment account requirement based on transaction and document types', () => {
      expect(isPaymentAccountRequired('DIRECT_PURCHASE')).toBe(true);
      expect(isPaymentAccountRequired('CUSTOMER_PAYMENT')).toBe(true);
      expect(isPaymentAccountRequired('PAY_VENDOR_BILL')).toBe(true);
      expect(isPaymentAccountRequired('VENDOR_BILL')).toBe(false);
      expect(isPaymentAccountRequired('CUSTOMER_INVOICE')).toBe(false);
      expect(isPaymentAccountRequired(undefined, 'RECEIPT')).toBe(true);
      expect(isPaymentAccountRequired(undefined, 'TRANSFER_PROOF')).toBe(true);
    });

    it('validates required fields for DIRECT_PURCHASE', () => {
      const invalid = validateDocumentReviewForm('DIRECT_PURCHASE', 'RECEIPT', {
        amount: '500000',
        transactionDate: '2026-09-12',
        projectId: 'prj-1',
        paymentAccountId: '',
      });
      expect(invalid.isValid).toBe(false);
      expect(invalid.missingFields).toContain('payment_account_id');
      expect(invalid.errorMessage).toBe('Pilih rekening pembayaran terlebih dahulu.');

      const valid = validateDocumentReviewForm('DIRECT_PURCHASE', 'RECEIPT', {
        amount: '500000',
        transactionDate: '2026-09-12',
        projectId: 'prj-1',
        paymentAccountId: 'pa-1',
      });
      expect(valid.isValid).toBe(true);
      expect(valid.missingFields).toEqual([]);
    });

    it('validates required fields for VENDOR_BILL', () => {
      const invalidProject = validateDocumentReviewForm('VENDOR_BILL', 'VENDOR_INVOICE', {
        amount: '500000',
        transactionDate: '2026-09-12',
        projectId: '',
        counterpartyId: 'vendor-1',
      });
      expect(invalidProject.isValid).toBe(false);
      expect(invalidProject.missingFields).toContain('project_id');
      expect(invalidProject.errorMessage).toBe('Proyek wajib dipilih sebelum dokumen dapat disetujui.');

      const invalidVendor = validateDocumentReviewForm('VENDOR_BILL', 'VENDOR_INVOICE', {
        amount: '500000',
        transactionDate: '2026-09-12',
        projectId: 'prj-1',
        counterpartyId: '',
      });
      expect(invalidVendor.isValid).toBe(false);
      expect(invalidVendor.missingFields).toContain('counterparty_id');
      expect(invalidVendor.errorMessage).toBe('Vendor wajib dipilih sebelum dokumen dapat disetujui.');
    });
  });

  describe('DocumentReviewForm Component Interactions', () => {
    it('renders payment account selector for DIRECT_PURCHASE and filters inactive accounts', () => {
      render(
        <DocumentReviewForm
          document={baseDocument}
          projects={mockProjects}
          counterparties={mockCounterparties}
          paymentAccounts={mockPaymentAccounts}
          onSave={vi.fn()}
          onApprove={vi.fn()}
          onReject={vi.fn()}
        />,
      );

      const paymentSelect = screen.getByLabelText('Pilih Rekening Kas / Bank');
      expect(paymentSelect).toBeInTheDocument();
      expect(screen.getByText(/BCA Operasional/)).toBeInTheDocument();
      expect(screen.queryByText(/Mandiri Lama/)).not.toBeInTheDocument();
    });

    it('does NOT render payment account selector for VENDOR_BILL', () => {
      const billDoc: DocumentResponse = {
        ...baseDocument,
        document_type: 'VENDOR_INVOICE',
        candidate_transaction: {
          ...baseDocument.candidate_transaction,
          proposed_transaction_type: 'VENDOR_BILL',
        },
      };

      render(
        <DocumentReviewForm
          document={billDoc}
          projects={mockProjects}
          counterparties={mockCounterparties}
          paymentAccounts={mockPaymentAccounts}
          onSave={vi.fn()}
          onApprove={vi.fn()}
          onReject={vi.fn()}
        />,
      );

      expect(screen.queryByLabelText('Pilih Rekening Kas / Bank')).not.toBeInTheDocument();
    });

    it('blocks approval and displays friendly error when payment account is missing on DIRECT_PURCHASE', async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const onApprove = vi.fn().mockResolvedValue(undefined);

      render(
        <DocumentReviewForm
          document={baseDocument}
          projects={mockProjects}
          counterparties={mockCounterparties}
          paymentAccounts={mockPaymentAccounts}
          onSave={onSave}
          onApprove={onApprove}
          onReject={vi.fn()}
        />,
      );

      const approveButton = screen.getByRole('button', { name: 'Setujui untuk Diposting' });
      await userEvent.click(approveButton);

      expect(screen.getByText('Pilih rekening pembayaran terlebih dahulu.')).toBeInTheDocument();
      expect(onSave).not.toHaveBeenCalled();
      expect(onApprove).not.toHaveBeenCalled();
    });

    it('saves dirty form values with silent option before calling onApprove', async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const onApprove = vi.fn().mockResolvedValue(undefined);

      render(
        <DocumentReviewForm
          document={baseDocument}
          projects={mockProjects}
          counterparties={mockCounterparties}
          paymentAccounts={mockPaymentAccounts}
          onSave={onSave}
          onApprove={onApprove}
          onReject={vi.fn()}
        />,
      );

      // Select payment account to satisfy required fields and make form dirty
      const paymentSelect = screen.getByLabelText('Pilih Rekening Kas / Bank');
      await userEvent.selectOptions(paymentSelect, 'pa-bank-bca');

      const approveButton = screen.getByRole('button', { name: 'Setujui untuk Diposting' });
      await userEvent.click(approveButton);

      // Verify onSave was called first with dirty changes and silent=true
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ payment_account_id: 'pa-bank-bca' }),
        'Verifikasi dokumen sumber',
        { silent: true },
      );
      // Verify onApprove was called subsequently
      expect(onApprove).toHaveBeenCalledOnce();
    });

    it('does NOT call onApprove if onSave fails during dirty auto-save', async () => {
      const onSave = vi.fn().mockRejectedValue(new Error('Koneksi penyimpanan gagal'));
      const onApprove = vi.fn().mockResolvedValue(undefined);

      render(
        <DocumentReviewForm
          document={baseDocument}
          projects={mockProjects}
          counterparties={mockCounterparties}
          paymentAccounts={mockPaymentAccounts}
          onSave={onSave}
          onApprove={onApprove}
          onReject={vi.fn()}
        />,
      );

      const paymentSelect = screen.getByLabelText('Pilih Rekening Kas / Bank');
      await userEvent.selectOptions(paymentSelect, 'pa-bank-bca');

      const approveButton = screen.getByRole('button', { name: 'Setujui untuk Diposting' });
      await userEvent.click(approveButton);

      expect(onSave).toHaveBeenCalled();
      expect(onApprove).not.toHaveBeenCalled();
    });

    it('does NOT call onSave when form is clean (zero fake correction history)', async () => {
      const readyDoc: DocumentResponse = {
        ...baseDocument,
        candidate_transaction: {
          ...baseDocument.candidate_transaction,
          payment_account_id: 'pa-bank-bca',
        },
      };

      const onSave = vi.fn().mockResolvedValue(undefined);
      const onApprove = vi.fn().mockResolvedValue(undefined);

      render(
        <DocumentReviewForm
          document={readyDoc}
          projects={mockProjects}
          counterparties={mockCounterparties}
          paymentAccounts={mockPaymentAccounts}
          onSave={onSave}
          onApprove={onApprove}
          onReject={vi.fn()}
        />,
      );

      const approveButton = screen.getByRole('button', { name: 'Setujui untuk Diposting' });
      await userEvent.click(approveButton);

      expect(onSave).not.toHaveBeenCalled();
      expect(onApprove).toHaveBeenCalledOnce();
    });

    it('Simpan Koreksi button saves form values without calling onApprove', async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const onApprove = vi.fn().mockResolvedValue(undefined);

      render(
        <DocumentReviewForm
          document={baseDocument}
          projects={mockProjects}
          counterparties={mockCounterparties}
          paymentAccounts={mockPaymentAccounts}
          onSave={onSave}
          onApprove={onApprove}
          onReject={vi.fn()}
        />,
      );

      const paymentSelect = screen.getByLabelText('Pilih Rekening Kas / Bank');
      await userEvent.selectOptions(paymentSelect, 'pa-bank-bca');

      const saveButton = screen.getByRole('button', { name: 'Simpan Koreksi' });
      await userEvent.click(saveButton);

      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ payment_account_id: 'pa-bank-bca' }),
        'Verifikasi dokumen sumber',
      );
      expect(onApprove).not.toHaveBeenCalled();
    });

    it('hides line items table for TRANSFER_PROOF documents', () => {
      const transferDoc: DocumentResponse = {
        ...baseDocument,
        document_type: 'TRANSFER_PROOF',
        extracted_data: {
          transfer_reference: 'TRF-BCA-998811',
          total_amount: '12500000.00',
          transaction_date: '2026-09-12',
          source_bank: 'BCA',
          destination_bank: 'Bank Mandiri',
          destination_account: '1410099887766',
          sender_name: 'PT Konstruksi Jaya',
          line_items: [
            { description: 'Item 1', quantity: 1, unit_price: 12500000, total_amount: 12500000 },
          ],
        },
        candidate_transaction: {
          ...baseDocument.candidate_transaction,
          proposed_transaction_type: 'PAY_VENDOR_BILL',
        },
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

      expect(screen.queryByText('Daftar Rincian Barang / Jasa')).not.toBeInTheDocument();
      expect(screen.getByText('Nomor Referensi Transfer:')).toBeInTheDocument();
      expect(screen.getByText('TRF-BCA-998811')).toBeInTheDocument();
      expect(screen.getByText('Bank Asal:')).toBeInTheDocument();
      expect(screen.getByText('BCA')).toBeInTheDocument();
      expect(screen.getByText('Bank Tujuan:')).toBeInTheDocument();
      expect(screen.getByText('Bank Mandiri')).toBeInTheDocument();
    });
  });
});
