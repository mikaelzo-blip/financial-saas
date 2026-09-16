import { transferExecutionLabels, type TransferDetails } from '../../utils/transferReview';

export function TransferEvidence({ extracted }: { extracted: Record<string, unknown> }) {
  const details = (extracted.transfer_details || {}) as TransferDetails;
  const rows = [
    ['Nominal valas', details.foreign],
    ['Pokok transfer', details.principal],
    ['Biaya bank', details.fee],
    ['Total debit rekening', details.debit],
  ] as const;
  return (
    <section aria-label="Rincian transfer dari sumber" className="rounded-lg border border-slate-200 p-3 space-y-3 text-sm">
      <h4 className="font-semibold text-slate-900">Rincian transfer dari sumber</h4>
      <dl className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-slate-600">{label}</dt>
            <dd className="font-medium text-slate-900 break-words">
              {value ? `${value.currency_code} ${value.amount}` : 'Tidak terdeteksi'}
            </dd>
            {value?.evidence && <dd className="text-xs text-slate-600 break-words">Bukti: {value.evidence}</dd>}
          </div>
        ))}
        {!details.principal && !details.foreign && extracted.total_amount != null && (
          <div>
            <dt className="text-slate-600">Nominal lama (peran perlu diperiksa)</dt>
            <dd>{`${extracted.currency_code || 'Mata uang belum diketahui'} ${extracted.total_amount}`}</dd>
          </div>
        )}
        <div><dt className="text-slate-600">Tujuan / berita transfer</dt><dd>{details.purpose || 'Tidak terdeteksi'}</dd></div>
        <div><dt className="text-slate-600">Pelaksanaan menurut sumber</dt><dd>{transferExecutionLabels[details.execution_status || 'UNKNOWN'] || transferExecutionLabels.UNKNOWN}</dd></div>
        {extracted.invoice_number ? (
          <div><dt className="text-slate-600">Referensi invoice dalam konteks pembayaran</dt><dd>{String(extracted.invoice_number)}</dd></div>
        ) : null}
      </dl>
      <p className="text-xs text-slate-700">Nominal ditampilkan dalam mata uang sumber, tanpa konversi atau penjumlahan otomatis. Biaya dan selisih debit memerlukan pemeriksaan terpisah.</p>
      <p className="text-xs text-slate-700">Transfer bukan otomatis biaya atau uang muka. Invoice terkait adalah konteks pencocokan, bukan rincian barang dari slip ini. Persetujuan belum berarti posting.</p>
    </section>
  );
}
