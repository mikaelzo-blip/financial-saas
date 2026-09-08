import { TRANSACTION_TYPES, DocumentResponse, TransactionType } from '../types/api';

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
