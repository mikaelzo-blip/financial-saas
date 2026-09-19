import { TRANSACTION_TYPES, DocumentResponse, TransactionType } from '../types/api';
import { PROJECT_REQUIRED_COST_CATEGORIES } from './recordingCategories';

const CUSTOMER_TRANSACTION_TYPES = new Set<TransactionType>([
  'CUSTOMER_INVOICE',
  'CUSTOMER_PAYMENT',
  'CUSTOMER_ADVANCE',
  'CUSTOMER_REFUND',
]);

const VENDOR_TRANSACTION_TYPES = new Set<TransactionType>([
  'VENDOR_BILL',
  'PAY_VENDOR_BILL',
  'VENDOR_ADVANCE',
  'SETTLE_VENDOR_ADVANCE',
  'SUBCONTRACTOR_BILL',
  'PAY_SUBCONTRACTOR',
  'VENDOR_REFUND',
]);

export const PROJECT_REQUIRED_TRANSACTION_TYPES = new Set<TransactionType>([
  'VENDOR_BILL',
  'CUSTOMER_INVOICE',
]);

export const PAYMENT_ACCOUNT_REQUIRED_TRANSACTION_TYPES = new Set<TransactionType>([
  'DIRECT_PURCHASE',
  'CUSTOMER_PAYMENT',
  'PAY_VENDOR_BILL',
]);

// Keep in sync with backend/src/services/documents/status.py (EVIDENCE_DOCUMENT_TYPES).
export const EVIDENCE_DOCUMENT_TYPES: ReadonlySet<string> = new Set<string>([
  // Supporting documents
  'SPK',
  'CONTRACT',
  'BAST',
  'SURAT_JALAN',
  'PROGRESS_REPORT',
  'TIMESHEET',
  'PURCHASE_ORDER',
  'PO_CUSTOMER',
  'TAX_INVOICE',
  'WITHHOLDING_DOCUMENT',
  'OTHER_TAX_DOCUMENT',
  // Evidence-only orphans
  'BANK_STATEMENT',
  'QUOTATION',
  'VARIATION_ORDER',
  'SUBCONTRACT_AGREEMENT',
  'PETTY_CASH_PROOF',
  'CUSTOMER_RECEIPT',
]);

export const isEvidenceDocument = (documentType: string | undefined | null): boolean =>
  Boolean(documentType && EVIDENCE_DOCUMENT_TYPES.has(documentType));

export const isPaymentAccountRequired = (
  transactionType: TransactionType | undefined,
  documentType?: string,
): boolean => {
  if (transactionType && PAYMENT_ACCOUNT_REQUIRED_TRANSACTION_TYPES.has(transactionType)) {
    return true;
  }
  if (documentType === 'RECEIPT' || documentType === 'TRANSFER_PROOF') {
    return true;
  }
  return false;
};

export interface FormValidationResult {
  isValid: boolean;
  missingFields: string[];
  errorMessage?: string;
}

export const validateDocumentReviewForm = (
  transactionType: TransactionType | undefined,
  documentType: string | undefined,
  values: {
    amount?: string | number | null;
    transactionDate?: string | null;
    projectId?: string | null;
    counterpartyId?: string | null;
    paymentAccountId?: string | null;
    allocationTargetId?: string | null;
    costCategory?: string | null;
    expenseCategory?: string | null;
  },
): FormValidationResult => {
  const missingFields: string[] = [];

  const requiresPaymentAccount = isPaymentAccountRequired(transactionType, documentType);
  if (requiresPaymentAccount && !values.paymentAccountId?.trim()) {
    missingFields.push('payment_account_id');
  }

  if (transactionType === 'VENDOR_BILL') {
    if (!values.projectId?.trim()) missingFields.push('project_id');
    if (!values.counterpartyId?.trim()) missingFields.push('counterparty_id');
  } else if (transactionType === 'CUSTOMER_INVOICE') {
    if (!values.projectId?.trim()) missingFields.push('project_id');
    if (!values.counterpartyId?.trim()) missingFields.push('counterparty_id');
  } else if (transactionType === 'DIRECT_PURCHASE') {
    if (!values.paymentAccountId?.trim() && !missingFields.includes('payment_account_id')) {
      missingFields.push('payment_account_id');
    }
    const hasProject = Boolean(values.projectId?.trim());
    const hasCategory = Boolean(values.costCategory?.trim() || values.expenseCategory?.trim());
    if (!hasProject && !hasCategory) {
      missingFields.push('project_id');
    }
    if (
      values.costCategory &&
      PROJECT_REQUIRED_COST_CATEGORIES.includes(values.costCategory) &&
      !values.projectId?.trim()
    ) {
      missingFields.push('project_id_for_category');
    }
  } else if (transactionType === 'CUSTOMER_PAYMENT') {
    if (!values.counterpartyId?.trim()) missingFields.push('counterparty_id');
    if (!values.paymentAccountId?.trim() && !missingFields.includes('payment_account_id')) {
      missingFields.push('payment_account_id');
    }
    if (!values.allocationTargetId?.trim()) missingFields.push('allocation_target_id');
  } else if (transactionType === 'PAY_VENDOR_BILL') {
    if (!values.counterpartyId?.trim()) missingFields.push('counterparty_id');
    if (!values.paymentAccountId?.trim() && !missingFields.includes('payment_account_id')) {
      missingFields.push('payment_account_id');
    }
    if (!values.allocationTargetId?.trim()) missingFields.push('allocation_target_id');
  }

  if (missingFields.length === 0) {
    return { isValid: true, missingFields: [] };
  }

  let errorMessage = 'Dokumen belum dapat disetujui karena data wajib belum lengkap.';
  if (missingFields.includes('payment_account_id')) {
    errorMessage = 'Pilih asal dana (rekening kas/bank) terlebih dahulu.';
  } else if (missingFields.includes('project_id')) {
    errorMessage = 'Proyek wajib dipilih sebelum dokumen dapat disetujui.';
  } else if (missingFields.includes('project_id_for_category')) {
    errorMessage = 'Proyek wajib dipilih untuk kategori biaya proyek (5101).';
  } else if (missingFields.includes('counterparty_id')) {
    const isCustomer = transactionType ? CUSTOMER_TRANSACTION_TYPES.has(transactionType) : false;
    errorMessage = isCustomer
      ? 'Pelanggan wajib dipilih sebelum dokumen dapat disetujui.'
      : 'Vendor wajib dipilih sebelum dokumen dapat disetujui.';
  } else if (missingFields.includes('allocation_target_id')) {
    errorMessage = 'Pilih kandidat pencocokan / alokasi faktur terlebih dahulu.';
  }

  return { isValid: false, missingFields, errorMessage };
};

export const formatDocumentActionError = (err: unknown): string => {
  if (!err) return '';
  let detail: unknown;
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const axiosResponse = (err as { response?: { data?: { detail?: unknown } } }).response;
    detail = axiosResponse?.data?.detail;
  }

  if (typeof detail === 'string') {
    if (detail.includes('missing required fields for approval')) {
      return 'Dokumen belum dapat disetujui karena data wajib belum lengkap.';
    }
    if (detail.includes('Customer payment requires an invoice allocation')) {
      return 'Pembayaran pelanggan memerlukan alokasi faktur penjualan.';
    }
    if (detail.includes('Vendor payment requires a bill allocation')) {
      return 'Pembayaran vendor memerlukan alokasi tagihan vendor.';
    }
    if (detail.includes('Payment account is not available') || detail.includes('PaymentAccount is not available')) {
      return 'Pilih asal dana (rekening kas/bank) terlebih dahulu.';
    }
    if (detail.includes('Project is not available or not active') || detail.includes('Project is no longer available')) {
      return 'Proyek yang dipilih tidak aktif atau tidak tersedia di organisasi ini.';
    }
    if (detail.includes('Counterparty is not available')) {
      return 'Vendor atau pelanggan tidak aktif atau tidak tersedia di organisasi ini.';
    }
    if (detail.includes('unresolved review requirements')) {
      return `Dokumen masih memiliki review yang belum selesai: ${detail.replace('Document has unresolved review requirements:', '').trim()}`;
    }
    if (detail.includes('ambiguous matching results')) {
      return 'Pencocokan dokumen ambigu. Harap pilih kandidat yang sesuai terlebih dahulu.';
    }
    if (detail.includes('already final')) {
      return 'Keputusan review dokumen sudah final dan tidak dapat diubah lagi.';
    }
    if (detail.includes('not awaiting review')) {
      return 'Dokumen tidak sedang dalam status menunggu review.';
    }
    if (detail.includes('Allocation target does not belong')) {
      return 'Target alokasi tidak cocok dengan vendor atau pelanggan yang dipilih.';
    }
    if (detail.includes('Candidate is incomplete')) {
      return 'Data kandidat transaksi belum lengkap (tipe transaksi, tanggal, atau nominal).';
    }
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) {
          const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
          return `${loc ? loc + ': ' : ''}${item.msg}`;
        }
        return JSON.stringify(item);
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join('; ');
  }

  if (err instanceof Error) {
    if (err.message.includes('status code 422')) {
      return 'Dokumen belum dapat disetujui karena data wajib belum lengkap.';
    }
    if (err.message.includes('status code 409')) {
      return 'Terjadi konflik status pada dokumen. Silakan muat ulang halaman.';
    }
    return err.message;
  }

  return 'Terjadi kesalahan saat memproses dokumen.';
};

const isTransactionType = (value: unknown): value is TransactionType =>
  typeof value === 'string' && (TRANSACTION_TYPES as readonly string[]).includes(value);

export const getDocumentReviewTransactionType = (
  document: DocumentResponse,
): TransactionType | undefined => {
  const proposedType = document.candidate_transaction.proposed_transaction_type;
  if (isTransactionType(proposedType)) return proposedType;
  if (document.document_type === 'VENDOR_INVOICE') return 'VENDOR_BILL';
  if (document.document_type === 'CUSTOMER_INVOICE') return 'CUSTOMER_INVOICE';
  return undefined;
};

export const getDocumentReviewLookupRequirements = (document: DocumentResponse) => {
  const transactionType = getDocumentReviewTransactionType(document);
  const candidate = document.candidate_transaction;
  return {
    project:
      (transactionType ? PROJECT_REQUIRED_TRANSACTION_TYPES.has(transactionType) : false) ||
      Boolean(candidate.project_id) ||
      document.review_flags.includes('PROJECT_UNKNOWN'),
    customer:
      (transactionType ? CUSTOMER_TRANSACTION_TYPES.has(transactionType) : false) ||
      document.review_flags.includes('CUSTOMER_UNKNOWN'),
    vendor:
      (transactionType ? VENDOR_TRANSACTION_TYPES.has(transactionType) : false) ||
      document.review_flags.includes('VENDOR_UNKNOWN'),
  };
};
