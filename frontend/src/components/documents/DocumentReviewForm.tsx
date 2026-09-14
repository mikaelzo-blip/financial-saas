import React, { useState } from 'react';
import { Button } from '../ui/Button';
import { Select } from '../ui/Select';
import { CounterpartyResponse, DocumentResponse, MatchCandidateResponse, ProjectResponse } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { ShieldCheck, FileText, CheckCircle, AlertTriangle, UserCheck, Layers, History } from 'lucide-react';

interface Props {
  document: DocumentResponse;
  projects: ProjectResponse[];
  counterparties: CounterpartyResponse[];
  projectLookupLoading?: boolean;
  counterpartyLookupLoading?: boolean;
  projectLookupError?: string;
  counterpartyLookupError?: string;
  approvalLookupLoading?: boolean;
  approvalLookupError?: string;
  onSave: (changes: Record<string, unknown>, reason: string) => Promise<void>;
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
  projectLookupLoading = false,
  counterpartyLookupLoading = false,
  projectLookupError,
  counterpartyLookupError,
  approvalLookupLoading = false,
  approvalLookupError,
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
  const [reason, setReason] = useState('Verifikasi dokumen sumber');
  const [busy, setBusy] = useState(false);

  const transactionType = String(
    candidate.proposed_transaction_type ??
      (document.document_type === 'VENDOR_INVOICE'
        ? 'VENDOR_BILL'
        : document.document_type === 'CUSTOMER_INVOICE'
        ? 'CUSTOMER_INVOICE'
        : ''),
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

  const save = async () => {
    setBusy(true);
    try {
      const changes: Record<string, unknown> = {
        project_id: projectId || null,
        counterparty_id: counterpartyId || null,
        invoice_number: invoiceNumber || null,
        amount: totalAmount || null,
        transaction_date: transactionDate || null,
        due_date: dueDate || null,
      };
      if (selectedCandidateId) {
        changes.selected_candidate_id = selectedCandidateId;
      }
      await onSave(changes, reason);
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
        selected_candidate_id: cand.entity_id,
      };
      await onSave(changes, reason || 'Memilih kandidat pencocokan');
    } finally {
      setBusy(false);
    }
  };

  const isEvidenceOnly =
    ['SPK', 'CONTRACT', 'BAST', 'SURAT_JALAN', 'PROGRESS_REPORT', 'TAX_INVOICE'].includes(document.document_type) &&
    !candidate.proposed_transaction_type;
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
  const corrections = document.corrections || [];

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
            document.processing_status === 'PROCESSED' || document.processing_status === 'READY_TO_POST'
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
              {extracted.total_amount ? formatIDR(Number(extracted.total_amount)) : <span className="text-slate-400 italic">Tidak terdeteksi</span>}
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
      </div>

      {/* Line Items Table (Slice 2 extracted items) */}
      {lineItems.length > 0 && (
        <div className="rounded-lg border border-slate-200 overflow-hidden text-xs">
          <div className="bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-slate-600" />
            <span>Daftar Rincian Barang / Jasa</span>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left">
              <thead className="bg-slate-50 text-[11px] text-slate-600">
                <tr>
                  <th className="px-3 py-1.5">Deskripsi</th>
                  <th className="px-3 py-1.5 text-right">Kuantitas</th>
                  <th className="px-3 py-1.5 text-right">Harga Satuan</th>
                  <th className="px-3 py-1.5 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {lineItems.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="px-3 py-1.5 text-slate-900">{String(item.description ?? '-')}</td>
                    <td className="px-3 py-1.5 text-right text-slate-700">{String(item.quantity ?? '-')}</td>
                    <td className="px-3 py-1.5 text-right text-slate-700">
                      {item.unit_price ? formatIDR(Number(item.unit_price)) : '-'}
                    </td>
                    <td className="px-3 py-1.5 text-right font-medium text-slate-900">
                      {item.total_amount ? formatIDR(Number(item.total_amount)) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
                              : 'bg-slate-200 text-slate-700'
                          }`}
                        >
                          Skor: {scorePct}% ({cand.confidence_band})
                        </span>
                      </div>
                      <p className="mt-1 text-slate-700">{cand.explanation}</p>
                    </div>
                    <Button
                      size="sm"
                      variant={isSelected ? 'secondary' : 'primary'}
                      onClick={() => handleSelectCandidate(cand)}
                      disabled={busy}
                    >
                      {isSelected ? 'Terpilih' : 'Pilih Kandidat'}
                    </Button>
                  </div>

                  {/* Signals & Conflicts */}
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

      {/* Supporting Document Message */}
      {isEvidenceOnly && (
        <div className="rounded-lg bg-blue-50 p-3 border border-blue-200 text-xs text-blue-900">
          <div className="font-semibold flex items-center gap-1">
            <ShieldCheck className="h-4 w-4 text-blue-600" />
            Dokumen pendukung saja
          </div>
          <p className="mt-1 text-blue-800">
            Dokumen ini disimpan sebagai bukti dan tidak langsung mengubah saldo atau membuat transaksi keuangan.
          </p>
        </div>
      )}

      {/* Form Alerts */}
      {projectLookupError && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
          {projectLookupError}
        </div>
      )}
      {counterpartyLookupError && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
          {counterpartyLookupError}
        </div>
      )}
      {approvalLookupError && (
        <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          {approvalLookupError}
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
              Total Nominal
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
              Tanggal Transaksi
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

        <label className="block text-sm">
          Mengapa data ini diubah?
          <input
            className="mt-1 w-full rounded border p-2 text-xs"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <span className="mt-1 block text-xs text-slate-500">
            Tuliskan alasan singkat agar perubahan dapat ditelusuri kembali.
          </span>
        </label>
      </div>

      {/* Corrections Audit History */}
      {corrections.length > 0 && (
        <div className="rounded-lg border border-slate-200 overflow-hidden text-xs">
          <div className="bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 flex items-center gap-1.5">
            <History className="h-3.5 w-3.5 text-slate-600" />
            <span>Riwayat Koreksi</span>
          </div>
          <div className="p-3 divide-y divide-slate-100 bg-white">
            {corrections.map((corr) => (
              <div key={corr.id} className="py-2 first:pt-0 last:pb-0">
                <div className="flex justify-between items-center text-slate-700">
                  <strong className="font-semibold text-slate-900">{corr.field_path}</strong>
                  <span className="text-[11px] text-slate-500">{formatDate(corr.corrected_at)}</span>
                </div>
                <div className="text-[11px] text-slate-600 mt-0.5">
                  <span className="line-through text-slate-400">{String(corr.old_value ?? 'kosong')}</span> →{' '}
                  <span className="font-medium text-slate-900">{String(corr.new_value ?? 'kosong')}</span>
                </div>
                <div className="text-[11px] text-slate-500 italic mt-0.5">Alasan: {corr.reason}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* JSON Viewer */}
      <details className="rounded border border-slate-200 p-3 text-xs">
        <summary className="cursor-pointer font-semibold text-slate-700">Detail Teknis</summary>
        <p className="mt-2 text-slate-500">
          Bagian ini hanya untuk pemeriksaan lanjutan. “null” berarti data tidak ditemukan pada dokumen.
        </p>
        <pre className="mt-2 max-h-56 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100 font-mono">
          {JSON.stringify(document.extracted_data, null, 2)}
        </pre>
      </details>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-2">
        <Button onClick={save} isLoading={busy}>
          Simpan Koreksi
        </Button>
        <Button
          variant="secondary"
          onClick={onApprove}
          disabled={
            document.review_flags.length > 0 ||
            isEvidenceOnly ||
            approvalLookupLoading ||
            !!approvalLookupError
          }
        >
          Setujui & Buat Transaksi
        </Button>
        <Button variant="danger" onClick={() => onReject(reason)}>
          Tolak Kandidat
        </Button>
      </div>
    </section>
  );
};
