import React, { useState } from 'react';
import { X, CheckCircle2, FileText, CheckSquare } from 'lucide-react';
import { TransactionResponse, ReviewFlagResponse } from '../../../types/api';
import { reviewApi } from '../../../api/review';
import { formatIDR, formatDate } from '../../../utils/formatters';
import { StatusBadge } from '../../../components/ui/StatusBadge';
import { Button } from '../../../components/ui/Button';
import { ApprovalActionControls } from './ApprovalActionControls';
import { ResolveFlagModal } from './ResolveFlagModal';
import { useToast } from '../../../components/feedback/Toast';

export interface ReviewDrawerProps {
  transaction: TransactionResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

export const ReviewDrawer: React.FC<ReviewDrawerProps> = ({
  transaction,
  isOpen,
  onClose,
  onRefresh,
}) => {
  const { success, error } = useToast();
  const [selectedFlag, setSelectedFlag] = useState<ReviewFlagResponse | null>(null);
  const [isApproving, setIsApproving] = useState(false);

  if (!isOpen || !transaction) return null;

  const unresolvedFlags = (transaction.review_flags || []).filter((f) => !f.resolved_at);

  const handleApprove = async () => {
    setIsApproving(true);
    try {
      await reviewApi.approveAndPost(transaction.id);
      success(`Transaksi ${transaction.transaction_code} berhasil disetujui dan diposting.`);
      onRefresh();
      onClose();
    } catch (err: any) {
      error(err.response?.data?.detail || 'Gagal menyetujui transaksi.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async () => {
    setIsApproving(true);
    try {
      await reviewApi.reject(transaction.id, 'Ditolak oleh peninjau.');
      success(`Transaksi ${transaction.transaction_code} ditolak.`);
      onRefresh();
      onClose();
    } catch (err: any) {
      error(err.response?.data?.detail || 'Gagal menolak transaksi.');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs" onClick={onClose} />

      <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
        <div className="w-screen max-w-4xl bg-white shadow-2xl flex flex-col">
          {/* Drawer Header */}
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-sm font-bold text-blue-600">
                  {transaction.transaction_code}
                </span>
                <StatusBadge status={transaction.workflow_status} />
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {transaction.transaction_type} • {formatDate(transaction.transaction_date)}
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Drawer Body - Split View */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Top Approval Controls */}
            <ApprovalActionControls
              onApprove={handleApprove}
              onReject={handleReject}
              isLoading={isApproving}
              unresolvedFlagsCount={unresolvedFlags.length}
            />

            {/* Ambiguity Review Flags Section */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Temuan Flag Ketidakpastian (Review Flags)
              </h4>
              {transaction.review_flags && transaction.review_flags.length > 0 ? (
                <div className="space-y-2">
                  {transaction.review_flags.map((flag) => (
                    <div
                      key={flag.id}
                      className={`flex items-start justify-between p-4 rounded-xl border transition-all ${
                        flag.resolved_at
                          ? 'border-emerald-200 bg-emerald-50/40 text-slate-700'
                          : 'border-amber-200 bg-amber-50/60 text-amber-900'
                      }`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center gap-2">
                          <StatusBadge status={flag.flag} size="sm" />
                          <span className="text-[11px] font-semibold">
                            Tingkat: {flag.severity}
                          </span>
                          {flag.resolved_at && (
                            <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700 font-medium">
                              <CheckCircle2 className="h-3 w-3" /> Terselesaikan (
                              {formatDate(flag.resolved_at)})
                            </span>
                          )}
                        </div>
                        <p className="text-xs font-medium">{flag.message}</p>
                        {flag.resolution_notes && (
                          <p className="text-[11px] text-slate-600 bg-white/80 p-2 rounded border border-slate-200 mt-1">
                            Catatan: {flag.resolution_notes}
                          </p>
                        )}
                      </div>

                      {!flag.resolved_at && (
                        <Button
                          size="sm"
                          variant="outline"
                          leftIcon={<CheckSquare className="h-3.5 w-3.5" />}
                          onClick={() => setSelectedFlag(flag)}
                        >
                          Selesaikan Flag
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">Tidak ada flag pada transaksi ini.</p>
              )}
            </div>

            {/* Side-by-side transaction metadata & document preview */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Left Column: Transaction Metadata */}
              <div className="rounded-xl border border-slate-200 p-4 space-y-3 bg-slate-50/50">
                <h5 className="text-xs font-bold text-slate-900 uppercase">Detail Transaksi</h5>
                <dl className="divide-y divide-slate-200 text-xs">
                  <div className="flex justify-between py-2">
                    <dt className="text-slate-500">Nominal</dt>
                    <dd className="font-mono font-bold text-slate-900">
                      {formatIDR(transaction.amount)}
                    </dd>
                  </div>
                  <div className="flex justify-between py-2">
                    <dt className="text-slate-500">Pihak Terkait</dt>
                    <dd className="font-semibold text-slate-800">
                      {transaction.counterparty_name || '-'}
                    </dd>
                  </div>
                  <div className="flex justify-between py-2">
                    <dt className="text-slate-500">Akun Kas/Bank</dt>
                    <dd className="font-medium text-slate-800">
                      {transaction.payment_account_name || '-'}
                    </dd>
                  </div>
                  <div className="flex justify-between py-2">
                    <dt className="text-slate-500">Keterangan</dt>
                    <dd className="font-medium text-slate-800 text-right">{transaction.description}</dd>
                  </div>
                </dl>
              </div>

              {/* Right Column: Evidence Document */}
              <div className="rounded-xl border border-slate-200 p-4 flex flex-col items-center justify-center text-center bg-slate-100/50">
                <FileText className="h-12 w-12 text-slate-400 stroke-[1]" />
                <p className="mt-2 text-xs font-semibold text-slate-800">Dokumen Bukti Terlampir</p>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  Bukti nota fisik / kwitansi yang diunggah
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ResolveFlagModal
        flag={selectedFlag}
        isOpen={!!selectedFlag}
        onClose={() => setSelectedFlag(null)}
        onSuccess={() => onRefresh()}
      />
    </div>
  );
};
