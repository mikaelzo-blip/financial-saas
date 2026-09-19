import React, { useState } from 'react';
import { Button } from '../ui/Button';
import { Select } from '../ui/Select';
import {
  CounterpartyResponse,
  DocumentResponse,
  MatchCandidateResponse,
  PaymentAccountResponse,
  ProjectResponse,
  TransactionType,
} from '../../types/api';
import { RECORDING_CATEGORIES } from '../../utils/recordingCategories';
import { formatIDR, formatDate } from '../../utils/formatters';
import {
  FileText,
  AlertTriangle,
  UserCheck,
  Layers,
  CheckCircle,
  MessageSquare,
} from 'lucide-react';
import {
  isEvidenceDocument,
  isPaymentAccountRequired,
  validateDocumentReviewForm,
  validateLineItemCategories,
} from '../../utils/documentReview';

const AUTO_CORRECTION_REASON = 'Verifikasi dokumen sumber';

interface Props {
  document: DocumentResponse;
  projects: ProjectResponse[];
  counterparties: CounterpartyResponse[];
  paymentAccounts?: PaymentAccountResponse[];
  projectLookupLoading?: boolean;
  counterpartyLookupLoading?: boolean;
  paymentAccountLookupLoading?: boolean;
  projectLookupError?: string;
  counterpartyLookupError?: string;
  paymentAccountLookupError?: string;
  approvalLookupLoading?: boolean;
  approvalLookupError?: string;
  actionError?: string;
  onSave: (changes: Record<string, unknown>, reason: string, options?: { silent?: boolean }) => Promise<void>;
  onApprove: () => Promise<void>;
  onReject: (reason: string) => Promise<void>;
}

const statusLabels: Record<DocumentResponse['processing_status'], string> = {
  UPLOADED: 'Dokumen diterima',
  HASHED: 'Dokumen diperiksa',
  QUEUED: 'Menunggu antrean',
  EXTRACTING: 'Sedang membaca dokumen',
  EXTRACTED: 'Dokumen selesai dibaca',
  MATCHING: 'Sedang mencari data terkait',
  REVIEW_REQUIRED: 'Perlu Diperiksa',
  READY_FOR_APPROVAL: 'Siap disetujui',
  READY_TO_POST: 'Siap diposting',
  POSTED: 'Sudah diposting',
  PROCESSED: 'Selesai diproses',
  REJECTED: 'Ditolak',
  FAILED: 'Gagal diproses',
};

const reviewFlagLabels: Record<string, string> = {
  PROJECT_UNKNOWN: 'Proyek belum dikenali',
  VENDOR_UNKNOWN: 'Vendor belum dikenali',
  CUSTOMER_UNKNOWN: 'Pelanggan belum dikenali',
  COUNTERPARTY_UNKNOWN: 'Pihak dalam transaksi belum dikenali',
  OCR_LOW_CONFIDENCE: 'Hasil pembacaan perlu diperiksa',
  MISSING_CRITICAL_FIELD: 'Data penting belum lengkap',
  MISSING_DOCUMENT: 'Dokumen sumber belum tersedia',
  DUPLICATE_SUSPECTED: 'Dokumen atau transaksi mungkin sudah pernah dicatat',
  AMOUNT_MISMATCH: 'Jumlah uang tidak cocok',
  DATE_MISMATCH: 'Tanggal tidak cocok',
  TAX_REVIEW: 'Data pajak perlu diperiksa',
  ACCOUNT_REVIEW: 'Jenis pencatatan perlu diperiksa',
  RELATED_PARTY_REVIEW: 'Hubungan dengan pihak terkait perlu diperiksa',
  AMBIGUOUS_MATCH: 'Pencocokan ambigu — butuh pemilihan kandidat',
};

const reviewFlagLabel = (flag: string) =>
  reviewFlagLabels[flag] ?? flag.toLowerCase().replaceAll('_', ' ');

export const DocumentReviewForm: React.FC<Props> = ({
  document,
  projects,
  counterparties,
  paymentAccounts = [],
  projectLookupLoading = false,
  counterpartyLookupLoading = false,
  paymentAccountLookupLoading = false,
  projectLookupError,
  counterpartyLookupError,
  paymentAccountLookupError,
  approvalLookupLoading = false,
  approvalLookupError,
  actionError,
  onSave,
  onApprove,
  onReject,
}) => {
  const candidate = (document.candidate_transaction || {}) as Record<string, unknown>;
  const extracted = (document.extracted_data || {}) as Record<string, unknown>;
  const confScores = document.confidence_scores || {};
  const matchingResults = (document.matching_results || {}) as Record<string, unknown>;
  const matchCandidates = (matchingResults.match_candidates || []) as MatchCandidateResponse[];
  const isAmbiguous = Boolean(matchingResults.ambiguous);

  const [projectId, setProjectId] = useState(String(candidate.project_id ?? ''));
  const [counterpartyId, setCounterpartyId] = useState(String(candidate.counterparty_id ?? ''));
  const [paymentAccountId, setPaymentAccountId] = useState(String(candidate.payment_account_id ?? ''));
  const [invoiceNumber, setInvoiceNumber] = useState(
    String(extracted.invoice_number ?? extracted.document_number ?? candidate.external_reference ?? ''),
  );
  const [totalAmount, setTotalAmount] = useState(
    String(candidate.amount ?? extracted.total_amount ?? ''),
  );
  const [transactionDate, setTransactionDate] = useState(
    String(candidate.transaction_date ?? extracted.transaction_date ?? ''),
  );
  const [dueDate, setDueDate] = useState(String(extracted.due_date ?? ''));
  const [selectedCandidateId, setSelectedCandidateId] = useState(
    String(candidate.allocation_target_id ?? ''),
  );

  const [projectSearch, setProjectSearch] = useState('');
  const [counterpartySearch, setCounterpartySearch] = useState('');
  const [recordingCategory, setRecordingCategory] = useState<string>(
    String(
      candidate.cost_category ??
        candidate.expense_category ??
        (document.matching_results?.suggested_cost_category as string | undefined) ??
        (document.matching_results?.suggested_expense_category as string | undefined) ??
        '',
    ),
  );
  const [lineItemCategories, setLineItemCategories] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      (Array.isArray(extracted.line_items) ? (extracted.line_items as Record<string, unknown>[]) : []).map(
        (item, idx) => [idx, String(item.cost_category ?? item.expense_category ?? '')],
      ),
    ),
  );
  const reason = AUTO_CORRECTION_REASON;
  const [busy, setBusy] = useState(false);
  const [formValidationError, setFormValidationError] = useState<string | undefined>(undefined);

  const initialProjectId = String(candidate.project_id ?? '');
  const initialCounterpartyId = String(candidate.counterparty_id ?? '');
  const initialPaymentAccountId = String(candidate.payment_account_id ?? '');
  const initialInvoiceNumber = String(
    extracted.invoice_number ?? extracted.document_number ?? candidate.external_reference ?? '',
  );
  const initialAmount = String(candidate.amount ?? extracted.total_amount ?? '');
  const initialTransactionDate = String(candidate.transaction_date ?? extracted.transaction_date ?? '');
  const initialDueDate = String(extracted.due_date ?? '');
  const initialCandidateId = String(candidate.allocation_target_id ?? '');

  const selectedRecording = RECORDING_CATEGORIES.find((c) => c.value === recordingCategory);

  const transactionType = String(
    candidate.proposed_transaction_type ??
      (selectedRecording
        ? 'DIRECT_PURCHASE'
        : document.document_type === 'VENDOR_INVOICE'
        ? 'VENDOR_BILL'
        : document.document_type === 'CUSTOMER_INVOICE'
        ? 'CUSTOMER_INVOICE'
        : document.document_type === 'RECEIPT'
        ? 'DIRECT_PURCHASE'
        : ''),
  );

  const requiresPaymentAccount = isPaymentAccountRequired(
    (transactionType as TransactionType) || undefined,
    document.document_type,
  );

  const customerTypes = new Set(['CUSTOMER_INVOICE', 'CUSTOMER_PAYMENT', 'CUSTOMER_ADVANCE', 'CUSTOMER_REFUND']);
  const vendorTypes = new Set([
    'VENDOR_BILL',
    'PAY_VENDOR_BILL',
    'VENDOR_ADVANCE',
    'SETTLE_VENDOR_ADVANCE',
    'SUBCONTRACTOR_BILL',
    'PAY_SUBCONTRACTOR',
    'VENDOR_REFUND',
  ]);

  const availableProjects = projects.filter(
    ({ id, project_code, project_name, project_status }) =>
      ['PLANNED', 'ACTIVE', 'ON_HOLD'].includes(project_status) &&
      (id === projectId || `${project_code} ${project_name}`.toLowerCase().includes(projectSearch.toLowerCase())),
  );

  const availableCounterparties = counterparties.filter(
    (counterparty) =>
      (customerTypes.has(transactionType)
        ? counterparty.is_customer
        : vendorTypes.has(transactionType)
        ? counterparty.is_vendor
        : true) &&
      (counterparty.id === counterpartyId || counterparty.name.toLowerCase().includes(counterpartySearch.toLowerCase())),
  );

  const availablePaymentAccounts = paymentAccounts.filter((account) => account.is_active);

  const buildCurrentChanges = (): { changes: Record<string, unknown>; isDirty: boolean } => {
    const changes: Record<string, unknown> = {};
    let isDirty = false;

    if (projectId !== initialProjectId) {
      changes.project_id = projectId || null;
      isDirty = true;
    }
    if (counterpartyId !== initialCounterpartyId) {
      changes.counterparty_id = counterpartyId || null;
      isDirty = true;
    }
    if (paymentAccountId !== initialPaymentAccountId) {
      changes.payment_account_id = paymentAccountId || null;
      isDirty = true;
    }
    if (invoiceNumber !== initialInvoiceNumber) {
      changes.invoice_number = invoiceNumber || null;
      isDirty = true;
    }
    if (totalAmount !== initialAmount) {
      changes.amount = totalAmount || null;
      isDirty = true;
    }
    if (transactionDate !== initialTransactionDate) {
      changes.transaction_date = transactionDate || null;
      isDirty = true;
    }
    if (dueDate !== initialDueDate) {
      changes.due_date = dueDate || null;
      isDirty = true;
    }
    if (selectedCandidateId !== initialCandidateId) {
      changes.selected_candidate_id = selectedCandidateId || null;
      changes.allocation_target_id = selectedCandidateId || null;
      isDirty = true;
    }

    if (document.document_type === 'TRANSFER_PROOF') {
      const selected = RECORDING_CATEGORIES.find((c) => c.value === recordingCategory);
      if (selected) {
        const nextCost = selected.costCategory ?? null;
        const nextExpense = selected.expenseCategory ?? null;
        if (
          nextCost !== (candidate.cost_category ?? null) ||
          nextExpense !== (candidate.expense_category ?? null)
        ) {
          changes.cost_category = nextCost;
          changes.expense_category = nextExpense;
          changes.proposed_transaction_type = 'DIRECT_PURCHASE';
          isDirty = true;
        }
      }
    }

    const items = Array.isArray(extracted.line_items)
      ? (extracted.line_items as Record<string, unknown>[])
      : [];
    if (items.length > 0) {
      const corrected = items.map((item, idx) => {
        const selected = RECORDING_CATEGORIES.find((c) => c.value === lineItemCategories[idx]);
        return {
          ...item,
          cost_category: selected?.costCategory ?? null,
          expense_category: selected?.expenseCategory ?? null,
        };
      });
      changes.line_items = corrected;
      isDirty = true;
    }

    return { changes, isDirty };
  };

  const save = async () => {
    setFormValidationError(undefined);
    setBusy(true);
    try {
      const { changes } = buildCurrentChanges();
      const payload: Record<string, unknown> = {
        project_id: projectId || null,
        counterparty_id: counterpartyId || null,
        invoice_number: invoiceNumber || null,
        amount: totalAmount || null,
        transaction_date: transactionDate || null,
        due_date: dueDate || null,
        ...changes,
      };
      if (paymentAccountId) {
        payload.payment_account_id = paymentAccountId;
      }
      if (selectedCandidateId) {
        payload.selected_candidate_id = selectedCandidateId;
      }
      await onSave(payload, reason);
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async () => {
    setFormValidationError(undefined);
    const validation = validateDocumentReviewForm(
      (transactionType as TransactionType) || undefined,
      document.document_type,
      {
        amount: totalAmount,
        transactionDate,
        projectId,
        counterpartyId,
        paymentAccountId,
        allocationTargetId: selectedCandidateId,
        costCategory: selectedRecording?.costCategory ?? String(candidate.cost_category ?? ''),
        expenseCategory: selectedRecording?.expenseCategory ?? String(candidate.expense_category ?? ''),
      },
    );

    if (!validation.isValid) {
      setFormValidationError(validation.errorMessage);
      return;
    }

    const { changes, isDirty } = buildCurrentChanges();

    if (Array.isArray(changes.line_items)) {
      const lineErr = validateLineItemCategories(
        changes.line_items as Array<Record<string, unknown>>,
        projectId,
      );
      if (lineErr) {
        setFormValidationError(lineErr);
        return;
      }
    }

    setBusy(true);
    try {
      if (isDirty) {
        await onSave(changes, reason, { silent: true });
      }
      await onApprove();
    } catch {
      // Error is caught and surfaced via actionError from parent mutation
    } finally {
      setBusy(false);
    }
  };

  const handleSelectCandidate = async (cand: MatchCandidateResponse) => {
    setSelectedCandidateId(cand.entity_id);
    setBusy(true);
    try {
      const changes: Record<string, unknown> = {
        project_id: projectId || null,
        counterparty_id: counterpartyId || null,
        invoice_number: invoiceNumber || null,
        amount: totalAmount || null,
        transaction_date: transactionDate || null,
        due_date: dueDate || null,
        payment_account_id: paymentAccountId || null,
        selected_candidate_id: cand.entity_id,
        allocation_target_id: cand.entity_id,
      };
      await onSave(changes, reason || 'Memilih kandidat pencocokan');
    } finally {
      setBusy(false);
    }
  };

  const isEvidenceOnly = isEvidenceDocument(document.document_type);
  const candidateStatus = String(candidate.status ?? 'PROPOSED');
  const approvalStatus =
    candidateStatus === 'CONVERTED'
      ? 'Disetujui'
      : candidateStatus === 'READY_TO_POST'
      ? 'Siap diposting'
      : candidateStatus === 'REJECTED'
      ? 'Ditolak'
      : candidateStatus === 'READY_FOR_APPROVAL'
      ? 'Menunggu persetujuan'
      : 'Belum disetujui';
  const postingStatus = candidate.converted_transaction_id ? 'Terposting' : 'Belum diposting';

  const lineItems = Array.isArray(extracted.line_items) ? (extracted.line_items as Record<string, unknown>[]) : [];

  return (
    <section className="space-y-4" aria-label="Form koreksi hasil ekstraksi">
      {/* Header Info */}
      <div className="flex items-center justify-between border-b pb-3">
        <div>
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <FileText className="h-4 w-4 text-blue-600" />
            Data yang perlu diperiksa
          </h3>
          <p className="text-xs text-slate-500">
            Periksa data hasil pembacaan dokumen. Sistem menentukan pencatatan akuntansi setelah Anda menyetujui.
          </p>
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
            document.processing_status === 'PROCESSED' || document.processing_status === 'POSTED' || document.processing_status === 'READY_TO_POST'
              ? 'bg-emerald-100 text-emerald-800'
              : document.processing_status === 'REJECTED'
              ? 'bg-rose-100 text-rose-800'
              : document.processing_status === 'READY_FOR_APPROVAL'
              ? 'bg-blue-100 text-blue-800'
              : 'bg-amber-100 text-amber-800'
          }`}
        >
          {statusLabels[document.processing_status]}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3" aria-label="Status dokumen">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
          <span className="block text-slate-500">Analisis</span>
          <strong className="text-slate-900">{statusLabels[document.processing_status]}</strong>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
          <span className="block text-slate-500">Persetujuan</span>
          <strong className="text-slate-900">{approvalStatus}</strong>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
          <span className="block text-slate-500">Pencatatan</span>
          <strong className="text-slate-900">{postingStatus}</strong>
        </div>
      </div>

      {/* Ambiguous Match Warning Alert */}
      {isAmbiguous && (
        <div className="rounded-lg bg-amber-50 p-3 border border-amber-300 text-xs text-amber-900" role="alert">
          <strong className="font-semibold block mb-1 flex items-center gap-1.5">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            Pencocokan ambigu terdeteksi
          </strong>
          <p>
            Terdapat beberapa kandidat yang cocok. Harap pilih kandidat yang tepat secara manual di bawah sebelum menyetujui.
          </p>
        </div>
      )}

      {/* Review Flags */}
      {document.review_flags.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 border border-amber-200" aria-label="Hal yang perlu diperiksa">
          <strong className="text-xs text-amber-900 block mb-1">Hal yang perlu diperiksa</strong>
          <div className="flex flex-wrap gap-1">
            {document.review_flags.map((flag) => (
              <span key={flag} className="rounded bg-amber-200 px-2 py-1 text-xs text-amber-900 font-semibold">
                {reviewFlagLabel(flag)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Keterangan dari Pengirim (WhatsApp caption / notes) */}
      {Boolean(document.source_metadata && (document.source_metadata as any).caption) && (
        <div className="rounded-lg bg-sky-50 p-3 border border-sky-200" aria-label="Keterangan dari Pengirim">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-sky-950 mb-1">
            <MessageSquare className="h-4 w-4 text-sky-700 shrink-0" />
            <span>Keterangan dari Pengirim</span>
          </div>
          <p className="text-xs text-sky-900 bg-white/90 p-2.5 rounded border border-sky-100 font-medium whitespace-pre-wrap">
            {(document.source_metadata as any).caption}
          </p>
          <p className="text-[11px] text-sky-700 mt-1.5">
            * Keterangan pesan pengirim dicatat terpisah sebagai petunjuk pencocokan dan tidak menggantikan teks hasil ekstraksi OCR dokumen.
          </p>
        </div>
      )}

      {/* Session Context: Dokumen terkait dalam kiriman yang sama (Section 24) */}
      {Boolean(
        (document.matching_results as any)?.session_matched_documents?.length > 0 ||
        ((document.matching_results as any)?.session_context?.document_count > 1)
      ) && (
        <div className="rounded-lg bg-indigo-50/70 p-3 border border-indigo-200" aria-label="Dokumen terkait dalam kiriman yang sama">
          <div className="flex items-center justify-between text-xs font-semibold text-indigo-950 mb-1.5">
            <div className="flex items-center gap-1.5">
              <FileText className="h-4 w-4 text-indigo-700 shrink-0" />
              <span>Dokumen terkait dalam kiriman yang sama</span>
            </div>
            {(document.matching_results as any)?.session_context?.session_code && (
              <span className="text-[10px] font-mono bg-indigo-100/80 text-indigo-800 px-1.5 py-0.5 rounded">
                {(document.matching_results as any).session_context.session_code}
              </span>
            )}
          </div>
          <p className="text-[11px] text-indigo-700 mb-2">
            Dokumen diterima dalam satu rangkaian pengiriman WhatsApp dan dianalisis keterkaitannya:
          </p>
          <div className="space-y-1.5">
            {((document.matching_results as any)?.session_matched_documents || []).map((relDoc: any, idx: number) => (
              <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between text-xs bg-white/90 p-2 rounded border border-indigo-100 gap-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-800">
                    {relDoc.document_type || 'Dokumen'}
                  </span>
                  {relDoc.document_code && (
                    <span className="text-slate-500 font-mono text-[11px]">({relDoc.document_code})</span>
                  )}
                  {relDoc.nominal && (
                    <span className="text-slate-700 font-medium">
                      Rp {Number(relDoc.nominal).toLocaleString('id-ID')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {relDoc.relationship && (
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800">
                      {relDoc.relationship === '1:1_MATCH'
                        ? 'Cocok 1:1'
                        : relDoc.relationship === 'MULTI_INVOICE_PAYMENT'
                        ? 'Pembayaran Multi-Invoice'
                        : relDoc.relationship}
                    </span>
                  )}
                  {relDoc.confidence && (
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                      relDoc.confidence === 'HIGH' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {relDoc.confidence === 'HIGH' ? 'Keyakinan Tinggi' : 'Perlu Review'}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
          {((document.matching_results as any)?.session_matched_documents?.[0]?.explanation) && (
            <p className="text-[11px] text-indigo-900 mt-2 bg-white/60 p-1.5 rounded italic">
              Petunjuk pencocokan: {(document.matching_results as any).session_matched_documents[0].explanation}
            </p>
          )}
        </div>
      )}

      {/* Confidence & Evidence Overview */}
      <div>
        <p className="mb-1 text-xs text-slate-500">Tingkat keyakinan sistem saat membaca dokumen:</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 rounded-lg bg-slate-50 p-3 border border-slate-200 text-xs">
          <div>
            <span className="text-slate-500 block">Tulisan terbaca</span>
            <strong className="text-slate-800">
              {confScores.ocr_confidence ? `${(Number(confScores.ocr_confidence) * 100).toFixed(0)}%` : 'Belum dinilai'}
            </strong>
          </div>
          <div>
            <span className="text-slate-500 block">Jenis dokumen</span>
            <strong className="text-slate-800">
              {confScores.document_type_confidence ? `${(Number(confScores.document_type_confidence) * 100).toFixed(0)}%` : 'Belum dinilai'}
            </strong>
          </div>
          <div>
            <span className="text-slate-500 block">Nama pihak</span>
            <strong className="text-slate-800">
              {confScores.entity_confidence ? `${(Number(confScores.entity_confidence) * 100).toFixed(0)}%` : 'Belum dinilai'}
            </strong>
          </div>
          <div>
            <span className="text-slate-500 block">Jumlah uang</span>
            <strong className="text-slate-800">
              {confScores.amount_confidence ? `${(Number(confScores.amount_confidence) * 100).toFixed(0)}%` : 'Belum dinilai'}
            </strong>
          </div>
        </div>
      </div>

      {/* Extracted Values Overview */}
      <div className="rounded-lg border border-slate-200 overflow-hidden text-xs">
        <div className="bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 flex justify-between">
          <span>Data yang dibaca dari dokumen</span>
          <span>Hasil pembacaan</span>
        </div>

        {document.document_type === 'TRANSFER_PROOF' ? (
          <div className="p-3 space-y-2 bg-white">
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Nomor Referensi Transfer:</span>
              <span className="font-semibold text-slate-900">
                {String(
                  extracted.transfer_reference ??
                    extracted.reference_number ??
                    extracted.invoice_number ??
                    extracted.document_number ??
                    candidate.external_reference ??
                    '-',
                )}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Nominal Transfer:</span>
              <span className="font-semibold text-slate-900">
                {extracted.total_amount ? (
                  formatIDR(Number(extracted.total_amount))
                ) : candidate.amount ? (
                  formatIDR(Number(candidate.amount))
                ) : (
                  <span className="text-slate-400 italic">Tidak terdeteksi</span>
                )}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Tanggal Transfer:</span>
              <span className="text-slate-900 font-medium">
                {extracted.transaction_date ? (
                  formatDate(String(extracted.transaction_date))
                ) : candidate.transaction_date ? (
                  formatDate(String(candidate.transaction_date))
                ) : (
                  <span className="text-slate-400 italic">Tidak terdeteksi</span>
                )}
              </span>
            </div>
            {Boolean(extracted.source_bank || extracted.origin_bank || extracted.sender_bank) && (
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-500">Bank Asal:</span>
                <span className="text-slate-700 font-medium">
                  {String(extracted.source_bank || extracted.origin_bank || extracted.sender_bank)}
                </span>
              </div>
            )}
            {Boolean(extracted.destination_bank || extracted.recipient_bank) && (
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-500">Bank Tujuan:</span>
                <span className="text-slate-700 font-medium">
                  {String(extracted.destination_bank || extracted.recipient_bank)}
                </span>
              </div>
            )}
            {Boolean(
              extracted.destination_account ||
                extracted.destination_account_number ||
                extracted.recipient_account,
            ) && (
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-500">Rekening Tujuan:</span>
                <span className="text-slate-700 font-medium">
                  {String(
                    extracted.destination_account ||
                      extracted.destination_account_number ||
                      extracted.recipient_account,
                  )}
                </span>
              </div>
            )}
            {Boolean(extracted.sender_name || extracted.recipient_name || extracted.issuer_name) && (
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-500">Pihak Terkait:</span>
                <span className="text-slate-700 font-medium">
                  {String(extracted.sender_name || extracted.recipient_name || extracted.issuer_name)}
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="p-3 space-y-2 bg-white">
            {extracted.invoice_number || extracted.document_number ? (
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Nomor Faktur / Dokumen:</span>
                <span className="font-semibold text-slate-900">
                  {String(extracted.invoice_number ?? extracted.document_number)}
                </span>
              </div>
            ) : null}
            {extracted.issuer_name ? (
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Penerbit:</span>
                <span className="text-slate-900 font-medium">{String(extracted.issuer_name)}</span>
              </div>
            ) : null}
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Nominal Total:</span>
              <span className="font-semibold text-slate-900">
                {extracted.total_amount || candidate?.amount ? (
                  formatIDR(Number(extracted.total_amount ?? candidate?.amount))
                ) : (
                  <span className="text-slate-400 italic">Tidak terdeteksi</span>
                )}
              </span>
            </div>
            {extracted.subtotal ? (
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-500">Subtotal:</span>
                <span className="text-slate-700">{formatIDR(Number(extracted.subtotal))}</span>
              </div>
            ) : null}
            {extracted.vat_amount ? (
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-500">PPN / Pajak:</span>
                <span className="text-slate-700">{formatIDR(Number(extracted.vat_amount))}</span>
              </div>
            ) : null}
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Tanggal Transaksi:</span>
              <span className="text-slate-900 font-medium">
                {extracted.transaction_date ? formatDate(String(extracted.transaction_date)) : <span className="text-slate-400 italic">Tidak terdeteksi</span>}
              </span>
            </div>
            {extracted.due_date ? (
              <div className="flex justify-between items-center text-[11px]">
                <span className="text-slate-500">Jatuh Tempo:</span>
                <span className="text-slate-700">{formatDate(String(extracted.due_date))}</span>
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Line Items Table (Slice 2 extracted items, hidden for TRANSFER_PROOF) */}
      {lineItems.length > 0 && !isEvidenceOnly && document.document_type !== 'TRANSFER_PROOF' && (
        <div className="rounded-lg border border-slate-200 overflow-hidden text-xs">
          <div className="bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-slate-600" />
            <span>Daftar Rincian Barang / Jasa</span>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left">
              <thead className="bg-slate-50 text-[11px] text-slate-600">
                <tr>
                  <th className="px-3 py-1.5 w-8">#</th>
                  <th className="px-3 py-1.5">Deskripsi</th>
                  <th className="px-3 py-1.5">Jenis Pencatatan</th>
                  <th className="px-3 py-1.5 text-right">Kuantitas</th>
                  <th className="px-3 py-1.5 text-right">Harga Satuan</th>
                  <th className="px-3 py-1.5 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {lineItems.map((item, idx) => (
                  <tr key={idx} data-testid="line-item-row" className="hover:bg-slate-50 align-top">
                    <td className="px-3 py-1.5 text-slate-400 font-mono text-[11px]">{idx + 1}.</td>
                    <td className="px-3 py-1.5 text-slate-900 whitespace-pre-line font-medium leading-relaxed">
                      {String(item.description ?? '-')}
                    </td>
                    <td className="px-3 py-1.5">
                      <select
                        aria-label="Jenis Pencatatan"
                        className="rounded border border-slate-300 text-[11px] px-1 py-0.5"
                        value={lineItemCategories[idx] ?? ''}
                        onChange={(e) =>
                          setLineItemCategories((prev) => ({ ...prev, [idx]: e.target.value }))
                        }
                      >
                        <option value="">— pilih —</option>
                        {RECORDING_CATEGORIES.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-1.5 text-right text-slate-700">
                      {item.quantity != null
                        ? `${item.quantity}${item.unit ? ' ' + String(item.unit).toUpperCase() : ''}`
                        : '-'}
                    </td>
                    <td className="px-3 py-1.5 text-right text-slate-700">
                      {item.unit_price != null ? formatIDR(Number(item.unit_price)) : '-'}
                    </td>
                    <td className="px-3 py-1.5 text-right font-semibold text-slate-900">
                      {(item.amount ?? item.line_total ?? item.total_amount) != null
                        ? formatIDR(Number(item.amount ?? item.line_total ?? item.total_amount))
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Ambiguous Matching Alert */}
      {isAmbiguous && (
        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold block">Pencocokan Ambigu Terdeteksi</strong>
            <p className="mt-0.5">
              Sistem mendeteksi beberapa kandidat tagihan/faktur dengan skor serupa. Silakan pilih salah satu kandidat di bawah ini untuk menetapkan alokasi pembayaran yang sesuai.
            </p>
          </div>
        </div>
      )}

      {/* Ranked Matching Candidates (Slice 3 MatchResult) */}
      {matchCandidates.length > 0 && (
        <div className="rounded-lg border border-slate-200 overflow-hidden text-xs">
          <div className="bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <UserCheck className="h-3.5 w-3.5 text-slate-600" />
              Kandidat Pencocokan
            </span>
            <span className="text-[11px] text-slate-500 font-normal">
              {matchCandidates.length} kandidat ditemukan
            </span>
          </div>
          <div className="p-3 space-y-3 bg-white">
            {matchCandidates.map((cand) => {
              const isSelected =
                cand.entity_id === selectedCandidateId ||
                cand.entity_id === String(candidate.allocation_target_id ?? '');
              const scorePct = Math.round(Number(cand.score || 0) * 100);
              const details = (cand.scoring_details || {}) as Record<string, unknown>;

              return (
                <div
                  key={cand.entity_id}
                  className={`rounded-lg border p-3 transition-colors ${
                    isSelected ? 'border-blue-500 bg-blue-50/50' : 'border-slate-200 bg-slate-50/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{cand.entity_type}</span>
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                            cand.confidence_band === 'HIGH'
                              ? 'bg-emerald-100 text-emerald-800'
                              : cand.confidence_band === 'MEDIUM'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          Kecocokan {scorePct}% ({cand.confidence_band})
                        </span>
                      </div>
                      <p className="mt-1 text-slate-600">{cand.explanation}</p>
                    </div>
                    <Button
                      size="sm"
                      variant={isSelected ? 'primary' : 'outline'}
                      onClick={() => handleSelectCandidate(cand)}
                      disabled={busy}
                    >
                      {isSelected ? 'Terpilih' : 'Pilih Kandidat'}
                    </Button>
                  </div>

                  {/* Candidate Allocation Breakdown (Step 7) */}
                  {Boolean(details.entity_code) && (
                    <div className="mt-2.5 rounded border border-slate-200 bg-white p-2.5 text-[11px] space-y-1.5">
                      <div className="font-medium text-slate-800">
                        Pembayaran ini kemungkinan terkait:
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-slate-600">
                        <div>
                          <span className="text-slate-400">Kode:</span>{' '}
                          <span className="font-semibold text-slate-800">{String(details.entity_code)}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">{cand.entity_type === 'VENDOR_BILL' ? 'Vendor:' : 'Pelanggan:'}</span>{' '}
                          <span className="font-medium text-slate-800">{String(details.counterparty_name || '-')}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">Nilai Tagihan:</span>{' '}
                          <span className="font-medium text-slate-800">{formatIDR(Number(details.total_amount ?? 0))}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">Sudah Dibayar:</span>{' '}
                          <span className="font-medium text-slate-800">{formatIDR(Number(details.paid_amount ?? 0))}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">Sisa Tagihan:</span>{' '}
                          <span className="font-semibold text-amber-700">{formatIDR(Number(details.outstanding_amount ?? 0))}</span>
                        </div>
                        <div>
                          <span className="text-slate-400">Alokasi Ini:</span>{' '}
                          <span className="font-semibold text-emerald-700">{formatIDR(Number(details.proposed_allocation ?? 0))}</span>
                        </div>
                      </div>
                      {details.after_allocation_outstanding !== undefined && (
                        <div className="border-t border-slate-100 pt-1 text-slate-500 text-[10px]">
                          Sisa setelah alokasi:{' '}
                          <span className="font-semibold text-slate-700">
                            {formatIDR(Number(details.after_allocation_outstanding))}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Signals */}
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(cand.positive_signals || []).map((sig, sIdx) => (
                      <span
                        key={`pos-${sIdx}`}
                        className="inline-flex items-center gap-1 rounded bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 text-[10px] text-emerald-800"
                      >
                        <CheckCircle className="h-3 w-3 text-emerald-600" />
                        {sig}
                      </span>
                    ))}
                    {(cand.negative_signals || []).map((sig, sIdx) => (
                      <span
                        key={`neg-${sIdx}`}
                        className="inline-flex items-center gap-1 rounded bg-rose-50 border border-rose-200 px-1.5 py-0.5 text-[10px] text-rose-800"
                      >
                        <AlertTriangle className="h-3 w-3 text-rose-600" />
                        {sig}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Evidence-Only Informational Alert */}
      {isEvidenceOnly && (
        <div className="rounded-lg bg-blue-50 p-3 border border-blue-200 text-xs text-blue-900">
          <strong className="font-semibold block mb-1">Dokumen pendukung saja</strong>
          <p>
            Dokumen jenis ini disimpan sebagai bukti dan tidak langsung mengubah saldo atau buku besar.
            Persetujuan tidak diperlukan untuk dokumen pendukung non-finansial.
          </p>
        </div>
      )}

      {/* Approval Lookup Error Display */}
      {approvalLookupError && (
        <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          {approvalLookupError}
        </div>
      )}

      {/* Action / Validation Error Display */}
      {(actionError || formValidationError) && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{formValidationError || actionError}</span>
        </div>
      )}

      {/* Form Fields for Review & Correction */}
      <div className="space-y-3">
        <div>
          <label htmlFor="invoice-number" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
            Nomor Faktur / Dokumen
          </label>
          <input
            id="invoice-number"
            type="text"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Contoh: INV-2026-001"
            value={invoiceNumber}
            onChange={(e) => setInvoiceNumber(e.target.value)}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="total-amount" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Total Nominal <span className="text-rose-500">*</span>
            </label>
            <input
              id="total-amount"
              type="text"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="Contoh: 15000000.00"
              value={totalAmount}
              onChange={(e) => setTotalAmount(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="transaction-date" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
              Tanggal Transaksi <span className="text-rose-500">*</span>
            </label>
            <input
              id="transaction-date"
              type="date"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
            />
          </div>
        </div>

        <div>
          <label htmlFor="due-date" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
            Tanggal Jatuh Tempo (Opsional)
          </label>
          <input
            id="due-date"
            type="date"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </div>

        {document.document_type === 'TRANSFER_PROOF' && (
          <div className="space-y-2">
            <label
              htmlFor="recording-category"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
            >
              Jenis Pencatatan {selectedRecording?.requiresProject ? <span className="text-rose-500">*</span> : null}
            </label>
            <Select
              id="recording-category"
              aria-label="Jenis Pencatatan"
              value={recordingCategory}
              onChange={(e) => setRecordingCategory(e.target.value)}
              helperText="Pilih kategori COA laba rugi untuk biaya ini."
            >
              <option value="">— Pilih jenis pencatatan —</option>
              {RECORDING_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
          </div>
        )}

        {requiresPaymentAccount && (
          <div className="space-y-2">
            <label htmlFor="payment-account-select" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
              Asal Dana (Rekening Kas / Bank) <span className="text-rose-500">*</span>
            </label>
            <Select
              id="payment-account-select"
              aria-label="Pilih Asal Dana (Rekening Kas / Bank)"
              disabled={paymentAccountLookupLoading || !!paymentAccountLookupError}
              value={paymentAccountId}
              onChange={(e) => setPaymentAccountId(e.target.value)}
              helperText="Pilih rekening kas/bank milik Anda yang menjadi asal dana transaksi ini."
            >
              <option value="">Pilih rekening kas / bank</option>
              {availablePaymentAccounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.bank_name
                    ? `${account.bank_name} - ${account.name} (${account.account_number || account.coa_account_code})`
                    : `${account.name} (${account.coa_account_code})`}
                </option>
              ))}
            </Select>
            {paymentAccountLookupError && (
              <p className="text-xs text-rose-600">{paymentAccountLookupError}</p>
            )}
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="project-search" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
            Proyek
          </label>
          <input
            id="project-search"
            type="search"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Cari nama atau kode proyek"
            value={projectSearch}
            onChange={(event) => setProjectSearch(event.target.value)}
            disabled={projectLookupLoading || !!projectLookupError}
          />
          <Select
            aria-label="Pilih Proyek"
            disabled={projectLookupLoading || !!projectLookupError}
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            helperText="Pilih nama proyek yang berkaitan dengan dokumen ini."
          >
            <option value="">Tidak terkait proyek tertentu</option>
            {availableProjects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.project_code} — {project.project_name}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-2">
          <label htmlFor="counterparty-search" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
            Vendor / Pelanggan
          </label>
          <input
            id="counterparty-search"
            type="search"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Cari nama vendor atau pelanggan"
            value={counterpartySearch}
            onChange={(event) => setCounterpartySearch(event.target.value)}
            disabled={counterpartyLookupLoading || !!counterpartyLookupError}
          />
          <Select
            aria-label="Pilih Vendor / Pelanggan"
            disabled={counterpartyLookupLoading || !!counterpartyLookupError}
            value={counterpartyId}
            onChange={(e) => setCounterpartyId(e.target.value)}
            helperText="Pilih vendor, pelanggan, atau pihak penerima dana yang tertulis pada dokumen."
          >
            <option value="">Belum diketahui atau tidak terkait</option>
            {availableCounterparties.map((counterparty) => (
              <option key={counterparty.id} value={counterparty.id}>
                {counterparty.name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-2">
        {isEvidenceOnly ? (
          <Button onClick={save} isLoading={busy}>
            Simpan Dokumen
          </Button>
        ) : (
          <>
            <Button
              variant="secondary"
              onClick={handleApprove}
              isLoading={busy}
              disabled={approvalLookupLoading || !!approvalLookupError}
            >
              Setujui untuk Diposting
            </Button>
            <Button variant="danger" onClick={() => onReject(reason)}>
              Tolak Kandidat
            </Button>
          </>
        )}
      </div>
    </section>
  );
};
