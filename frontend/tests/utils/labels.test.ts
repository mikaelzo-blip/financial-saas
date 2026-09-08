import { describe, expect, it } from 'vitest';

import { formatDocumentType, formatSourceChannel, formatTransactionType } from '../../src/utils/labels';
import { DOCUMENT_TYPES, TRANSACTION_TYPES } from '../../src/types/api';

describe('owner-facing enum labels', () => {
  it('converts internal transaction, document, and source enums to Indonesian labels', () => {
    expect(formatTransactionType('VENDOR_BILL')).toBe('Tagihan vendor');
    expect(formatTransactionType('CUSTOMER_PAYMENT')).toBe('Pembayaran pelanggan');
    expect(formatTransactionType('ASSET_PURCHASE')).toBe('Pembelian aset tetap');
    expect(formatTransactionType('REVERSAL')).toBe('Pembatalan transaksi');
    expect(formatDocumentType('TAX_INVOICE')).toBe('Faktur pajak');
    expect(formatSourceChannel('WHATSAPP')).toBe('WhatsApp');
  });

  it('localizes every known transaction and document enum without a raw fallback', () => {
    for (const transactionType of TRANSACTION_TYPES) {
      expect(formatTransactionType(transactionType)).not.toMatch(/_|tidak dikenal/i);
    }
    for (const documentType of DOCUMENT_TYPES) {
      expect(formatDocumentType(documentType)).not.toMatch(/_|tidak dikenal/i);
    }
    expect(formatTransactionType('OWNER_WITHDRAWAL')).toBe('Prive pemilik');
    expect(formatTransactionType('LOAN_RECEIVED')).toBe('Penerimaan pinjaman');
    expect(formatTransactionType('FIXED_ASSET_DEPRECIATION')).toBe('Penyusutan aset tetap');
    expect(formatDocumentType('TRANSFER_PROOF')).toBe('Bukti transfer');
  });
});
