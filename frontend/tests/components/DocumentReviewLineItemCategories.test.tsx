import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DocumentReviewForm } from '../../src/components/documents/DocumentReviewForm';

vi.mock('../../src/api/documents', () => ({
  documentsApi: { correct: vi.fn(), approve: vi.fn(), reject: vi.fn() },
}));

const baseDoc = {
  id: 'doc-1',
  document_code: 'DOC-2026-000016',
  document_type: 'VENDOR_INVOICE',
  processing_status: 'REVIEW_REQUIRED',
  review_flags: [],
  confidence_scores: {},
  extracted_data: {
    total_amount: '19937250',
    transaction_date: '2026-09-14',
    line_items: [
      { description: 'JASA ANGKUT GERMAN TO JAKARTA', amount: '19927250', cost_category: 'LOG' },
      { description: 'STAMP', amount: '10000', expense_category: 'OTHER_OPERATIONAL' },
    ],
  },
  candidate_transaction: { id: 'c1', amount: '19937250', transaction_date: '2026-09-14' },
  matching_results: {},
};
const document = baseDoc as never;

describe('DocumentReviewForm per-line categories', () => {
  it('renders a category selector for each line item', () => {
    render(
      <DocumentReviewForm
        document={document}
        projects={[]}
        counterparties={[]}
        onSave={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );
    const rows = screen.getAllByTestId('line-item-row');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByLabelText(/jenis pencatatan/i)).toBeInTheDocument();
  });

  it('validates that HPP line items require a project before approval', async () => {
    const onApprove = vi.fn();
    const documentWithCandidate = {
      ...baseDoc,
      candidate_transaction: {
        id: 'c1',
        amount: '19937250',
        transaction_date: '2026-09-14',
        proposed_transaction_type: 'DIRECT_PURCHASE',
        counterparty_id: 'cp-1',
        payment_account_id: 'acc-1',
        cost_category: null,
        expense_category: 'OTHER_OPERATIONAL',
      },
    } as never;
    render(
      <DocumentReviewForm
        document={documentWithCandidate}
        projects={[]}
        counterparties={[{ id: 'cp-1', name: 'Vendor A', type: 'VENDOR' } as never]}
        paymentAccounts={[{ id: 'acc-1', account_name: 'Kas', is_active: true } as never]}
        onSave={vi.fn()}
        onApprove={onApprove}
        onReject={vi.fn()}
      />,
    );
    const approveBtn = screen.getByRole('button', { name: /setujui untuk diposting/i });
    await userEvent.click(approveBtn);
    expect(screen.getByText('Setiap baris HPP (barang/jasa proyek) memerlukan proyek.')).toBeInTheDocument();
    expect(onApprove).not.toHaveBeenCalled();
  });
});
