import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, CheckCircle2, RotateCcw, Lock } from 'lucide-react';
import { transactionsApi } from '../../api/transactions';
import { useAuth } from '../../store/AuthContext';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { useToast } from '../../components/feedback/Toast';
import { TransactionReversalModal } from '../../components/transactions/TransactionReversalModal';

export const TransactionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasRole } = useAuth();
  const { success, error } = useToast();
  const [reversalModalOpen, setReversalModalOpen] = useState(false);

  const { data: trx, isLoading } = useQuery({
    queryKey: ['transaction', id],
    queryFn: () => transactionsApi.get(id!),
    enabled: !!id,
  });

  const postMutation = useMutation({
    mutationFn: () => transactionsApi.postDirect(id!),
    onSuccess: (updated) => {
      queryClient.setQueryData(['transaction', id], updated);
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      success(`Transaksi ${updated.transaction_code} berhasil diposting ke buku besar.`);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Gagal memposting transaksi.');
    },
  });

  const reverseMutation = useMutation({
    mutationFn: (reason: string) => transactionsApi.reverse(id!, reason),
    onSuccess: (updated) => {
      queryClient.setQueryData(['transaction', id], updated);
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      success(`Transaksi ${updated.transaction_code} berhasil dibatalkan (Reversed).`);
      setReversalModalOpen(false);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Gagal membatalkan transaksi.');
    },
  });

  if (isLoading) {
    return <SkeletonLoader count={4} className="h-28 w-full" />;
  }

  if (!trx) {
    return (
      <div className="text-center p-12">
        <p className="text-sm text-slate-500">Transaksi tidak ditemukan.</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => navigate('/transactions')}>
          Kembali ke Riwayat Transaksi
        </Button>
      </div>
    );
  }

  const isPosted = trx.workflow_status === 'POSTED';
  const isStaged = trx.workflow_status === 'STAGED';
  const canReverse = isPosted && hasRole(['ADMIN', 'MANAGER']);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/transactions')}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-200/60 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-2.5">
              <span className="font-mono text-sm font-bold text-blue-600">
                {trx.transaction_code}
              </span>
              <StatusBadge status={trx.workflow_status} />
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {trx.transaction_type} • Tanggal: {formatDate(trx.transaction_date)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isStaged && (
            <Button
              size="sm"
              variant="primary"
              leftIcon={<CheckCircle2 className="h-4 w-4" />}
              onClick={() => postMutation.mutate()}
              isLoading={postMutation.isPending}
            >
              Posting ke Buku Besar
            </Button>
          )}
          {canReverse && (
            <Button
              size="sm"
              variant="danger"
              leftIcon={<RotateCcw className="h-4 w-4" />}
              onClick={() => setReversalModalOpen(true)}
            >
              Batalkan / Reverse Transaksi
            </Button>
          )}
        </div>
      </div>

      {/* Immutability Alert Banner for Posted Transactions */}
      {isPosted && (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 text-xs text-emerald-900">
          <Lock className="h-5 w-5 shrink-0 text-emerald-600" />
          <div>
            <p className="font-semibold">Transaksi Ini Bersifat Read-Only (Terposting)</p>
            <p className="mt-0.5 text-emerald-700">
              Sesuai prinsip keabadian transaksi akuntansi, transaksi yang telah dibukukan tidak dapat diubah langsung di tempat. Untuk koreksi, gunakan alur pembatalan (Reverse) resmi.
            </p>
          </div>
        </div>
      )}

      {/* Transaction Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="Informasi Transaksi">
          <dl className="divide-y divide-slate-100 text-xs">
            <div className="flex justify-between py-2.5">
              <dt className="text-slate-500">Nominal Transaksi</dt>
              <dd className="font-bold font-mono text-sm text-slate-900">
                {formatIDR(trx.amount)}
              </dd>
            </div>
            <div className="flex justify-between py-2.5">
              <dt className="text-slate-500">Pihak Terkait (Counterparty)</dt>
              <dd className="font-semibold text-slate-800">
                {trx.counterparty_name || '-'}
              </dd>
            </div>
            <div className="flex justify-between py-2.5">
              <dt className="text-slate-500">Akun Kas / Bank</dt>
              <dd className="font-medium text-slate-800">{trx.payment_account_name || '-'}</dd>
            </div>
            <div className="flex justify-between py-2.5">
              <dt className="text-slate-500">Nomor Referensi Nota</dt>
              <dd className="font-mono text-slate-800">{trx.reference_no || '-'}</dd>
            </div>
            <div className="flex justify-between py-2.5">
              <dt className="text-slate-500">Keterangan</dt>
              <dd className="font-medium text-slate-800 text-right max-w-[60%]">{trx.description}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Alokasi Proyek & Biaya">
          {trx.allocations && trx.allocations.length > 0 ? (
            <div className="space-y-3">
              {trx.allocations.map((alloc, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100 text-xs">
                  <div>
                    <p className="font-semibold text-slate-900">
                      {alloc.project_id ? `Proyek ID: ${alloc.project_id.substring(0, 8)}...` : 'Umum / Overhead'}
                    </p>
                    <p className="text-[10px] text-slate-500 mt-0.5">Kategori: {alloc.cost_category || 'MAT'}</p>
                  </div>
                  <p className="font-bold font-mono text-slate-900">{formatIDR(alloc.amount)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500">Alokasi default operasional umum.</p>
          )}
        </Card>
      </div>

      <TransactionReversalModal
        isOpen={reversalModalOpen}
        onClose={() => setReversalModalOpen(false)}
        onConfirm={async (reason) => {
          await reverseMutation.mutateAsync(reason);
        }}
        transactionCode={trx.transaction_code}
        isLoading={reverseMutation.isPending}
      />
    </div>
  );
};
