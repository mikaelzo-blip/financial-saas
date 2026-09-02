import React, { useState } from 'react';
import { Button } from '../ui/Button';
import { DocumentResponse } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { ShieldCheck, FileText } from 'lucide-react';

interface Props {
  document: DocumentResponse;
  onSave: (changes: Record<string, unknown>, reason: string) => Promise<void>;
  onApprove: () => Promise<void>;
  onReject: (reason: string) => Promise<void>;
}

export const DocumentReviewForm: React.FC<Props> = ({ document, onSave, onApprove, onReject }) => {
  const candidate = document.candidate_transaction || {};
  const extracted = document.extracted_data || {};
  const confScores = document.confidence_scores || {};

  const [projectId, setProjectId] = useState(String(candidate.project_id ?? ''));
  const [counterpartyId, setCounterpartyId] = useState(String(candidate.counterparty_id ?? ''));
  const [reason, setReason] = useState('Verifikasi dokumen sumber');
  const [busy, setBusy] = useState(false);

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

  return (
    <section className="space-y-4" aria-label="Form koreksi hasil ekstraksi">
      {/* Header Info */}
      <div className="flex items-center justify-between border-b pb-3">
        <div>
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <FileText className="h-4 w-4 text-blue-600" />
            Kandidat Transaksi
          </h3>
          <p className="text-xs text-slate-500">
            Tidak ada pilihan debit atau kredit. Backend accounting rules tetap otoritatif.
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
          {document.processing_status}
        </span>
      </div>

      {/* Review Flags */}
      {document.review_flags.length > 0 && (
        <div className="rounded-lg bg-amber-50 p-3 border border-amber-200" aria-label="Peringatan Review">
          <strong className="text-xs text-amber-900 block mb-1">Flag review</strong>
          <div className="flex flex-wrap gap-1">
            {document.review_flags.map((flag) => (
              <span key={flag} className="rounded bg-amber-200 px-2 py-1 text-xs text-amber-900 font-semibold">
                {flag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Confidence & Evidence Overview */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 rounded-lg bg-slate-50 p-3 border border-slate-200 text-xs">
        <div>
          <span className="text-slate-500 block">OCR / Provider</span>
          <strong className="text-slate-800">
            {confScores.ocr_confidence ? `${(Number(confScores.ocr_confidence) * 100).toFixed(0)}%` : 'N/A'}
          </strong>
        </div>
        <div>
          <span className="text-slate-500 block">Tipe Dokumen</span>
          <strong className="text-slate-800">
            {confScores.document_type_confidence ? `${(Number(confScores.document_type_confidence) * 100).toFixed(0)}%` : 'N/A'}
          </strong>
        </div>
        <div>
          <span className="text-slate-500 block">Entitas / Rekanan</span>
          <strong className="text-slate-800">
            {confScores.entity_confidence ? `${(Number(confScores.entity_confidence) * 100).toFixed(0)}%` : '0%'}
          </strong>
        </div>
        <div>
          <span className="text-slate-500 block">Nominal</span>
          <strong className="text-slate-800">
            {confScores.amount_confidence ? `${(Number(confScores.amount_confidence) * 100).toFixed(0)}%` : '0%'}
          </strong>
        </div>
      </div>

      {/* Extracted Values Overview */}
      <div className="rounded-lg border border-slate-200 overflow-hidden text-xs">
        <div className="bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 flex justify-between">
          <span>Hasil Ekstraksi Terstruktur</span>
          <span>Status Validasi</span>
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
            Dokumen Pendukung / Evidence-Only
          </div>
          <p className="mt-1 text-blue-800">
            Dokumen ini tergolong arsip pembuktian (SPK/BAST/Surat Jalan/Kontrak) dan tidak membentuk mutasi finansial atau jurnal akuntansi secara langsung.
          </p>
        </div>
      )}

      {/* Form Fields for Candidate Modification */}
      <label className="block text-sm">
        Project ID
        <input
          className="mt-1 w-full rounded border p-2 text-xs font-mono"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
        />
      </label>
      <label className="block text-sm">
        Counterparty ID
        <input
          className="mt-1 w-full rounded border p-2 text-xs font-mono"
          value={counterpartyId}
          onChange={(e) => setCounterpartyId(e.target.value)}
        />
      </label>
      <label className="block text-sm">
        Alasan koreksi
        <input
          className="mt-1 w-full rounded border p-2 text-xs"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>

      {/* JSON Viewer */}
      <pre className="max-h-56 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100 font-mono">
        {JSON.stringify(document.extracted_data, null, 2)}
      </pre>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-2">
        <Button onClick={save} isLoading={busy}>
          Simpan Koreksi
        </Button>
        <Button
          variant="secondary"
          onClick={onApprove}
          disabled={document.review_flags.length > 0 || isEvidenceOnly}
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
