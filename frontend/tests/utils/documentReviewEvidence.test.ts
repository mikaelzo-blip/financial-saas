import { describe, expect, it } from 'vitest';
import { EVIDENCE_DOCUMENT_TYPES, isEvidenceDocument } from '../../src/utils/documentReview';

describe('isEvidenceDocument', () => {
  it('recognises supporting and orphan evidence types', () => {
    for (const t of ['SPK', 'BAST', 'TAX_INVOICE', 'BANK_STATEMENT', 'QUOTATION', 'PETTY_CASH_PROOF', 'CUSTOMER_RECEIPT']) {
      expect(isEvidenceDocument(t)).toBe(true);
    }
  });

  it('excludes financial and unknown types', () => {
    for (const t of ['TRANSFER_PROOF', 'RECEIPT', 'VENDOR_INVOICE', 'CUSTOMER_INVOICE', 'UNKNOWN', undefined]) {
      expect(isEvidenceDocument(t)).toBe(false);
    }
  });

  it('has 17 evidence types', () => {
    expect(EVIDENCE_DOCUMENT_TYPES.size).toBe(17);
  });
});
