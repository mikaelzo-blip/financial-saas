import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';
import type { DocumentResponse } from '../../src/types/api';

describe('DocumentReviewForm Line Items Extraction Rendering (Objective 1 & 4)', () => {
  const threeLineInvoiceDoc: DocumentResponse = {
    id: 'doc-invoice-3line',
    organization_id: 'org-001',
    document_code: 'DOC-2026-0045',
    document_type: 'VENDOR_INVOICE',
    file_name: 'faktur-penjualan-0045.pdf',
    file_hash: 'b'.repeat(64),
    file_size_bytes: 54321,
    mime_type: 'application/pdf',
    source_channel: 'WHATSAPP',
    created_at: '2026-09-15T10:00:00Z',
    processing_status: 'REVIEW_REQUIRED',
    review_flags: ['CONFIDENCE_BELOW_THRESHOLD'],
    confidence_scores: {},
    extracted_data: {
      invoice_number: 'INV/2026/09/0045',
      total_amount: 15600000,
      line_items: [
        {
          description: 'COVER / REPAIR STRIP\nSIZE : 100 MM X 10.000 MM',
          quantity: 1,
          unit: 'ROLL',
          unit_price: 3100000,
          amount: 3100000,
        },
        {
          description: 'COVER / REPAIR STRIP\nSIZE : 220 MM X 10.000 MM',
          quantity: 1,
          unit: 'ROLL',
          unit_price: 6300000,
          amount: 6300000,
        },
        {
          description: 'LEM SC 2000 + HARDENER UTR',
          quantity: 10,
          unit: 'SET',
          unit_price: 620000,
          amount: 6200000,
        },
      ],
    },
    matching_results: {},
    candidate_transaction: {},
    source_metadata: {
      caption: 'po roll arjer',
      sender_phone: '+62812345678',
    },
  };

  it('renders exactly 3 extracted line items with multiline descriptions preserved', () => {
    render(
      <DocumentReviewForm
        document={threeLineInvoiceDoc}
        projects={[]}
        counterparties={[]}
        paymentAccounts={[]}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onApprove={vi.fn().mockResolvedValue(undefined)}
        onReject={vi.fn().mockResolvedValue(undefined)}
      />
    );

    // Section header exists
    expect(screen.getByText('Daftar Rincian Barang / Jasa')).toBeInTheDocument();

    const table = screen.getByRole('table');
    const rows = within(table).getAllByRole('row');
    // Header row + 3 data rows = 4 rows
    expect(rows).toHaveLength(4);

    // 15. Exactly 3 line items rendered (row indices 1., 2., 3.)
    expect(within(rows[1]).getByText('1.')).toBeInTheDocument();
    expect(within(rows[2]).getByText('2.')).toBeInTheDocument();
    expect(within(rows[3]).getByText('3.')).toBeInTheDocument();

    // 16. Multiline SIZE descriptions visible without truncation
    const item1Desc = within(rows[1]).getByText((content) =>
      content.includes('COVER / REPAIR STRIP') && content.includes('SIZE : 100 MM X 10.000 MM')
    );
    expect(item1Desc).toBeInTheDocument();
    expect(item1Desc.className).toContain('whitespace-pre-line');

    const item2Desc = within(rows[2]).getByText((content) =>
      content.includes('COVER / REPAIR STRIP') && content.includes('SIZE : 220 MM X 10.000 MM')
    );
    expect(item2Desc).toBeInTheDocument();
    expect(item2Desc.className).toContain('whitespace-pre-line');

    const item3Desc = within(rows[3]).getByText((content) =>
      content.includes('LEM SC 2000 + HARDENER UTR')
    );
    expect(item3Desc).toBeInTheDocument();

    // Quantities and units rendered
    expect(within(rows[1]).getByText('1 ROLL')).toBeInTheDocument();
    expect(within(rows[2]).getByText('1 ROLL')).toBeInTheDocument();
    expect(within(rows[3]).getByText('10 SET')).toBeInTheDocument();

    // Unit prices and line totals formatted
    // Row 1: unit price 3.100.000 and total 3.100.000
    expect(within(rows[1]).getAllByText('Rp 3.100.000')).toHaveLength(2);
    // Row 2: unit price 6.300.000 and total 6.300.000
    expect(within(rows[2]).getAllByText('Rp 6.300.000')).toHaveLength(2);
    // Row 3: unit price 620.000 and total 6.200.000
    expect(within(rows[3]).getByText('Rp 620.000')).toBeInTheDocument();
    expect(within(rows[3]).getByText('Rp 6.200.000')).toBeInTheDocument();

    // 17. Session 1 card "Keterangan dari Pengirim" remains separate from line items
    expect(screen.getByLabelText('Keterangan dari Pengirim')).toBeInTheDocument();
    expect(screen.getByText('po roll arjer')).toBeInTheDocument();
  });
});
