import React from 'react';
import { transferExecutionLabels, type TransferDetails } from '../../utils/transferReview';
import { formatDate } from '../../utils/formatters';

interface Props {
  extracted: Record<string, unknown>;
}

export const TransferEvidence: React.FC<Props> = ({ extracted }) => {
  const details = (extracted.transfer_details || {}) as TransferDetails;

  return (
    <section aria-label="Rincian transfer dari sumber" className="rounded-lg border border-slate-200 overflow-hidden text-xs">
      <div className="bg-slate-100 px-3 py-1.5 font-semibold text-slate-700 flex justify-between">
        <span>Data yang dibaca dari bukti transfer</span>
        <span>Hasil pembacaan</span>
      </div>
      <div className="p-3 space-y-2 bg-white">
        {Boolean(extracted.transfer_reference || extracted.document_number || extracted.invoice_number) && (
          <div className="flex justify-between items-center">
            <span className="text-slate-500">Referensi Transfer / Dokumen:</span>
            <span className="font-semibold text-slate-900">
              {String(extracted.transfer_reference ?? extracted.document_number ?? extracted.invoice_number)}
            </span>
          </div>
        )}

        {Boolean(extracted.origin_bank || extracted.issuer_name) && (
          <div className="flex justify-between items-center">
            <span className="text-slate-500">Bank / Penerbit:</span>
            <span className="text-slate-900 font-medium">{String(extracted.origin_bank ?? extracted.issuer_name)}</span>
          </div>
        )}

        {/* Nominal Terdeteksi / Pokok Transfer */}
        <div className="flex justify-between items-center">
          <span className="text-slate-500">Pokok transfer:</span>
          <span className="font-semibold text-slate-900">
            {details.principal
              ? `${details.principal.currency_code} ${details.principal.amount}`
              : extracted.total_amount
              ? `${extracted.currency_code || 'IDR'} ${extracted.total_amount}`
              : <span className="text-slate-400 italic">Tidak terdeteksi</span>}
          </span>
        </div>

        {/* Valas jika ada */}
        {details.foreign && (
          <div className="flex justify-between items-center text-[11px]">
            <span className="text-slate-500">Nominal valas:</span>
            <span className="font-medium text-slate-800">{`${details.foreign.currency_code} ${details.foreign.amount}`}</span>
          </div>
        )}

        {/* Biaya bank jika ada */}
        {details.fee && (
          <div className="flex justify-between items-center text-[11px]">
            <span className="text-slate-500">Biaya bank:</span>
            <span className="text-slate-700">{`${details.fee.currency_code} ${details.fee.amount}`}</span>
          </div>
        )}

        {/* Total debit jika ada */}
        {details.debit && (
          <div className="flex justify-between items-center text-[11px]">
            <span className="text-slate-500">Total debit rekening:</span>
            <span className="text-slate-700 font-medium">{`${details.debit.currency_code} ${details.debit.amount}`}</span>
          </div>
        )}

        {/* Tanggal transaksi */}
        <div className="flex justify-between items-center">
          <span className="text-slate-500">Tanggal Transfer / Aplikasi:</span>
          <span className="text-slate-900 font-medium">
            {extracted.transaction_date ? formatDate(String(extracted.transaction_date)) : <span className="text-slate-400 italic">Tidak terdeteksi</span>}
          </span>
        </div>

        {/* Tujuan / Berita */}
        {details.purpose && (
          <div className="flex justify-between items-center text-[11px]">
            <span className="text-slate-500">Tujuan / Berita:</span>
            <span className="text-slate-700">{details.purpose}</span>
          </div>
        )}

        {/* Status eksekusi sumber */}
        <div className="flex justify-between items-center text-[11px] pt-1 border-t border-slate-100">
          <span className="text-slate-500">Status Pelaksanaan pada Sumber:</span>
          <span className="font-medium text-slate-800">
            {transferExecutionLabels[details.execution_status || 'UNKNOWN'] || transferExecutionLabels.UNKNOWN}
          </span>
        </div>
      </div>
    </section>
  );
};
