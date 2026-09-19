import { describe, expect, it } from 'vitest';
import { validateDocumentReviewForm } from '../../src/utils/documentReview';

describe('validateDocumentReviewForm - recording category', () => {
  it('requires project for project cost category', () => {
    const result = validateDocumentReviewForm('DIRECT_PURCHASE', 'TRANSFER_PROOF', {
      paymentAccountId: 'acc-1',
      projectId: '',
      costCategory: 'MAT',
      expenseCategory: '',
    });
    expect(result.isValid).toBe(false);
    expect(result.errorMessage).toMatch(/proyek/i);
  });

  it('allows operational category without project', () => {
    const result = validateDocumentReviewForm('DIRECT_PURCHASE', 'TRANSFER_PROOF', {
      paymentAccountId: 'acc-1',
      projectId: '',
      costCategory: '',
      expenseCategory: 'OFFICE_ADMIN',
    });
    expect(result.isValid).toBe(true);
  });
});
