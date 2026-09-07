import { describe, expect, it } from 'vitest';

import { formatDocumentType, formatSourceChannel, formatTransactionType } from '../../src/utils/labels';

describe('owner-facing enum labels', () => {
  it('converts internal transaction, document, and source enums to Indonesian labels', () => {
    expect(formatTransactionType('VENDOR_BILL')).toBe('Tagihan vendor');
    expect(formatTransactionType('CUSTOMER_PAYMENT')).toBe('Pembayaran pelanggan');
    expect(formatTransactionType('ASSET_PURCHASE')).toBe('Pembelian aset tetap');
    expect(formatTransactionType('REVERSAL')).toBe('Pembatalan transaksi');
    expect(formatDocumentType('TAX_INVOICE')).toBe('Faktur pajak');
    expect(formatSourceChannel('WHATSAPP')).toBe('WhatsApp');
  });

  it('formats unknown enum values without exposing underscore codes', () => {
    expect(formatTransactionType('FUTURE_TRANSACTION')).toBe('future transaction');
    expect(formatDocumentType('FUTURE_DOCUMENT')).toBe('future document');
  });
});
