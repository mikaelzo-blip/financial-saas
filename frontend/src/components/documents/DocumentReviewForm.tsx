import React, { useState } from 'react';
import { Button } from '../ui/Button';
import { Select } from '../ui/Select';
import { CounterpartyResponse, DocumentResponse, ProjectResponse } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { ShieldCheck, FileText } from 'lucide-react';

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
  EXTRACTING: 'Sedang membaca dokumen',
  EXTRACTED: 'Dokumen selesai dibaca',
  MATCHING: 'Sedang mencari data terkait',
  REVIEW_REQUIRED: 'Perlu Diperiksa',
  READY_FOR_APPROVAL: 'Siap disetujui',
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
  const candidate = document.candidate_transaction || {};
  const extracted = document.extracted_data || {};
  const confScores = document.confidence_scores || {};

  const [projectId, setProjectId] = useState(String(candidate.project_id ?? ''));
  const [counterpartyId, setCounterpartyId] = useState(String(candidate.counterparty_id ?? ''));
  const [projectSearch, setProjectSearch] = useState('');
  const [counterpartySearch, setCounterpartySearch] = useState('');
  const [reason, setReason] = useState('Verifikasi dokumen sumber');
  const [busy, setBusy] = useState(false);
  const transactionType = String(
    candidate.proposed_transaction_type ??
      (document.document_type === 'VENDOR_INVOICE' ? 'VENDOR_BILL' :
        document.document_type === 'CUSTOMER_INVOICE' ? 'CUSTOMER_INVOICE' : ''),
  );
  const customerTypes = new Set(['CUSTOMER_INVOICE', 'CUSTOMER_PAYMENT', 'CUSTOMER_ADVANCE', 'CUSTOMER_REFUND']);
  const vendorTypes = new Set([
    'VENDOR_BILL', 'PAY_VENDOR_BILL', 'VENDOR_ADVANCE', 'SETTLE_VENDOR_ADVANCE',
    'SUBCONTRACTOR_BILL', 'PAY_SUBCONTRACTOR', 'VENDOR_REFUND',
  ]);
  const availableProjects = projects.filter(({ id, project_code, project_name, project_status }) =>
    ['PLANNED', 'ACTIVE', 'ON_HOLD'].includes(project_status) && (
      id === projectId || `${project_code} ${project_name}`.toLowerCase().includes(projectSearch.toLowerCase())
    ),
  );
  const availableCounterparties = counterparties.filter((counterparty) =>
    (customerTypes.has(transactionType) ? counterparty.is_customer
      : vendorTypes.has(transactionType) ? counterparty.is_vendor
        : true) && (
      counterparty.id === counterpartyId || counterparty.name.toLowerCase().includes(counterpartySearch.toLowerCase())
    ),
  );

  const save = async () => {
    setBusy(true);
    try {
      const changes: Record<string, unknown> = {
        project_id: projectId || null,
        counterparty_id: counterpartyId || null,
      };
      await onSave(changes, reason);
    } finally {
      setBusy(false);
    }
  };

  const isEvidenceOnly =
    ['SPK', 'CONTRACT', 'BAST', 'SURAT_JALAN', 'PROGRESS_REPORT', 'TAX_INVOICE'].includes(document.document_type) &&
    !candidate.proposed_transaction_type;
  const candidateStatus = String(candidate.status ?? 'PROPOSED');
  const approvalStatus = candidateStatus === 'CONVERTED'
    ? 'Disetujui'
    : candidateStatus === 'REJECTED'
      ? 'Ditolak'
      : candidateStatus === 'READY_FOR_APPROVAL'
        ? 'Menunggu persetujuan'
        : 'Belum disetujui';
  const postingStatus = candidate.converted_transaction_id ? 'Terposting' : 'Belum diposting';

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
            document.processing_status === 'PROCESSED'
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
          <div className="flex justify-between items-center">
            <span className="text-slate-500">Nominal Total:</span>
            <span className="font-semibold text-slate-900">
              {extracted.total_amount ? formatIDR(Number(extracted.total_amount)) : <span className="text-slate-400 italic">Tidak terdeteksi</span>}
            </span>
          </div>
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
        </div>
      </div>

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

      {/* Form Fields for Candidate Modification */}
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

      {/* JSON Viewer */}
      <details className="rounded border border-slate-200 p-3 text-xs">
        <summary className="cursor-pointer font-semibold text-slate-700">Detail Teknis</summary>
        <p className="mt-2 text-slate-500">Bagian ini hanya untuk pemeriksaan lanjutan. “null” berarti data tidak ditemukan pada dokumen.</p>
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
