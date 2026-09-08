import type { DocumentType, TransactionType } from '../types/api';

const transactionTypeLabels: Record<TransactionType, string> = {
  DIRECT_PURCHASE: 'Pembelian langsung',
  VENDOR_BILL: 'Tagihan vendor',
  PAY_VENDOR_BILL: 'Pembayaran tagihan vendor',
  SUBCONTRACTOR_BILL: 'Tagihan subkontraktor',
  PAY_SUBCONTRACTOR: 'Pembayaran subkontraktor',
  VENDOR_ADVANCE: 'Uang muka vendor',
  SETTLE_VENDOR_ADVANCE: 'Pertanggungjawaban uang muka vendor',
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
  ASSET_PURCHASE: 'Pembelian aset tetap',
  FIXED_ASSET_DEPRECIATION: 'Penyusutan aset tetap',
  INVENTORY_PURCHASE: 'Pembelian persediaan',
  INVENTORY_USAGE: 'Pemakaian persediaan',
  CUSTOMER_INVOICE: 'Tagihan pelanggan',
  CUSTOMER_PAYMENT: 'Pembayaran pelanggan',
  RETENTION_RELEASE: 'Pelepasan retensi',
  REVENUE_RECOGNITION: 'Pengakuan pendapatan',
  OWNER_CONTRIBUTION: 'Setoran modal',
  CUSTOMER_REFUND: 'Pengembalian dana pelanggan',
  VENDOR_REFUND: 'Pengembalian dana vendor',
  OWNER_WITHDRAWAL: 'Prive pemilik',
  LOAN_RECEIVED: 'Penerimaan pinjaman',
  LOAN_PAYMENT: 'Pembayaran pinjaman',
  BANK_CHARGE: 'Biaya bank',
  OTHER_INCOME: 'Pendapatan lainnya',
  OTHER_EXPENSE: 'Beban lainnya',
  JOURNAL_ADJUSTMENT: 'Penyesuaian jurnal',
  REVERSAL: 'Pembatalan transaksi',
};

const documentTypeLabels: Record<DocumentType, string> = {
  PO_CUSTOMER: 'Pesanan pembelian pelanggan',
  SPK: 'Surat perintah kerja',
  CONTRACT: 'Kontrak',
  VARIATION_ORDER: 'Perintah perubahan pekerjaan',
  PURCHASE_ORDER: 'Pesanan pembelian',
  QUOTATION: 'Penawaran harga',
  VENDOR_INVOICE: 'Tagihan vendor',
  SUBCONTRACT_AGREEMENT: 'Perjanjian subkontrak',
  TRANSFER_PROOF: 'Bukti transfer',
  RECEIPT: 'Struk / nota',
  BANK_STATEMENT: 'Rekening koran',
  PETTY_CASH_PROOF: 'Bukti kas kecil',
  SURAT_JALAN: 'Surat jalan',
  BAST: 'Berita acara serah terima',
  PROGRESS_REPORT: 'Laporan kemajuan',
  TIMESHEET: 'Lembar waktu kerja',
  CUSTOMER_INVOICE: 'Tagihan pelanggan',
  CUSTOMER_RECEIPT: 'Bukti penerimaan pelanggan',
  TAX_INVOICE: 'Faktur pajak',
  WITHHOLDING_DOCUMENT: 'Bukti potong pajak',
  OTHER_TAX_DOCUMENT: 'Dokumen pajak lainnya',
  UNKNOWN: 'Jenis dokumen belum diketahui',
};

const sourceChannelLabels: Record<string, string> = {
  WEB: 'Web',
  WEB_UPLOAD: 'Web',
  WHATSAPP: 'WhatsApp',
  API: 'API',
  IMPORT: 'Impor',
};

export const formatTransactionType = (value: TransactionType): string =>
  transactionTypeLabels[value] ?? `Jenis transaksi tidak dikenal (${value})`;

export const formatDocumentType = (value: DocumentType): string =>
  documentTypeLabels[value] ?? `Jenis dokumen tidak dikenal (${value})`;

export const formatSourceChannel = (value: string): string =>
  sourceChannelLabels[value] ?? value.toLowerCase().replaceAll('_', ' ');
