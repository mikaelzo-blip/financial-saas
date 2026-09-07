const transactionTypeLabels: Record<string, string> = {
  DIRECT_PURCHASE: 'Pembelian langsung',
  VENDOR_BILL: 'Tagihan vendor',
  PAY_VENDOR_BILL: 'Pembayaran tagihan vendor',
  VENDOR_ADVANCE: 'Uang muka vendor',
  SETTLE_VENDOR_ADVANCE: 'Pertanggungjawaban uang muka vendor',
  SUBCONTRACTOR_BILL: 'Tagihan subkontraktor',
  PAY_SUBCONTRACTOR: 'Pembayaran subkontraktor',
  EMPLOYEE_ADVANCE: 'Uang muka karyawan',
  EMPLOYEE_SETTLEMENT: 'Pertanggungjawaban uang muka karyawan',
  CUSTOMER_ADVANCE: 'Uang muka pelanggan',
  REIMBURSEMENT: 'Penggantian biaya',
  PAY_REIMBURSEMENT: 'Pembayaran penggantian biaya',
  PETTY_CASH_EXPENSE: 'Pengeluaran kas kecil',
  TOPUP_PETTY_CASH: 'Pengisian kas kecil',
  RETURN_PETTY_CASH: 'Pengembalian kas kecil',
  BANK_TO_CASH: 'Transfer bank ke kas',
  CASH_TO_BANK: 'Setoran kas ke bank',
  INTERBANK_TRANSFER: 'Transfer antar rekening',
  INVENTORY_PURCHASE: 'Pembelian persediaan',
  INVENTORY_USAGE: 'Pemakaian persediaan',
  ASSET_PURCHASE: 'Pembelian aset tetap',
  CUSTOMER_INVOICE: 'Tagihan pelanggan',
  CUSTOMER_PAYMENT: 'Pembayaran pelanggan',
  RETENTION_RELEASE: 'Pelepasan retensi',
  REVENUE_RECOGNITION: 'Pengakuan pendapatan',
  LOAN_PAYMENT: 'Pembayaran pinjaman',
  OWNER_CONTRIBUTION: 'Setoran modal',
  OWNER_DRAW: 'Prive pemilik',
  OWNER_DRAWING: 'Prive pemilik',
  OTHER_EXPENSE: 'Beban lainnya',
  OTHER_INCOME: 'Pendapatan lainnya',
  BANK_CHARGE: 'Biaya bank',
  CUSTOMER_REFUND: 'Pengembalian dana pelanggan',
  VENDOR_REFUND: 'Pengembalian dana vendor',
  JOURNAL_ADJUSTMENT: 'Penyesuaian jurnal',
  REVERSAL: 'Pembatalan transaksi',
};

const documentTypeLabels: Record<string, string> = {
  VENDOR_INVOICE: 'Tagihan vendor',
  CUSTOMER_INVOICE: 'Tagihan pelanggan',
  RECEIPT: 'Struk / nota',
  PAYMENT_PROOF: 'Bukti pembayaran',
  BANK_STATEMENT: 'Rekening koran',
  TAX_INVOICE: 'Faktur pajak',
  CONTRACT: 'Kontrak',
  SPK: 'Surat perintah kerja',
  BAST: 'Berita acara serah terima',
  SURAT_JALAN: 'Surat jalan',
  PROGRESS_REPORT: 'Laporan kemajuan',
  OTHER: 'Dokumen lainnya',
};

const sourceChannelLabels: Record<string, string> = {
  WEB: 'Web',
  WHATSAPP: 'WhatsApp',
  API: 'API',
  IMPORT: 'Impor',
};

export const formatTransactionType = (value: string): string =>
  transactionTypeLabels[value] ?? value.toLowerCase().replaceAll('_', ' ');

export const formatDocumentType = (value: string): string =>
  documentTypeLabels[value] ?? value.toLowerCase().replaceAll('_', ' ');

export const formatSourceChannel = (value: string): string =>
  sourceChannelLabels[value] ?? value.toLowerCase().replaceAll('_', ' ');
