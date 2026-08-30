import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Eye } from 'lucide-react';
import { reviewApi } from '../../api/review';
import { TransactionResponse, ReviewFlag } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { DataTable, Column } from '../../components/tables/DataTable';
import { ReviewDrawer } from './components/ReviewDrawer';

export const ReviewQueuePage: React.FC = () => {
  const [flagFilter, setFlagFilter] = useState<ReviewFlag | ''>('');
  const [selectedTrx, setSelectedTrx] = useState<TransactionResponse | null>(null);

  const { data: queueItems = [], isLoading, refetch } = useQuery({
    queryKey: ['review-queue', flagFilter],
    queryFn: () => reviewApi.list(flagFilter || undefined),
  });

  const columns: Column<TransactionResponse>[] = [
    {
      key: 'transaction_code',
      header: 'Kode Transaksi',
      sortable: true,
      render: (t) => (
        <span className="font-mono text-xs font-semibold text-blue-600">
          {t.transaction_code}
        </span>
      ),
    },
    {
      key: 'transaction_date',
      header: 'Tanggal',
      sortable: true,
      render: (t) => <span className="text-xs text-slate-600">{formatDate(t.transaction_date)}</span>,
    },
    {
      key: 'description',
      header: 'Keterangan & Pihak Terkait',
      sortable: true,
      render: (t) => (
        <div>
          <p className="font-medium text-slate-900">{t.description}</p>
          <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-400">
            <span>{t.transaction_type}</span>
            {t.counterparty_name && <span>• {t.counterparty_name}</span>}
          </div>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Nominal',
      sortable: true,
      align: 'right',
      render: (t) => (
        <span className="font-semibold font-mono text-slate-900 tabular-nums">
          {formatIDR(t.amount)}
        </span>
      ),
    },
    {
      key: 'review_flags',
      header: 'Flag Review (Ambiguity)',
      render: (t) => (
        <div className="flex flex-wrap gap-1">
          {t.review_flags && t.review_flags.length > 0 ? (
            t.review_flags.map((f) => (
              <span key={f.id} title={f.message}>
                <StatusBadge status={f.flag} size="sm" />
              </span>
            ))
          ) : (
            <span className="text-xs text-slate-400">-</span>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: 'Aksi',
      align: 'right',
      render: (t) => (
        <Button
          size="sm"
          variant="outline"
          leftIcon={<Eye className="h-3.5 w-3.5" />}
          onClick={(e) => {
            e.stopPropagation();
            setSelectedTrx(t);
          }}
        >
          Tinjau
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Antrean Review Transaksi
            </h2>
            {queueItems.length > 0 && (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-700 bg-amber-100 px-2.5 py-0.5 rounded-full">
                <AlertTriangle className="h-3.5 w-3.5" /> {queueItems.length} Perlu Review
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Daftar transaksi yang memiliki selisih nominal, indikasi duplikasi, atau memerlukan persetujuan manajer sebelum diposting.
          </p>
        </div>
      </div>

      {/* Flag Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-slate-200 pb-2">
        {[
          { label: 'Semua Antrean', value: '' },
          { label: 'Selisih Nominal', value: 'AMOUNT_MISMATCH' },
          { label: 'Dugaan Duplikasi', value: 'DUPLICATE_SUSPECTED' },
          { label: 'Proyek Tidak Dikenal', value: 'PROJECT_UNKNOWN' },
          { label: 'Review Akun', value: 'ACCOUNT_REVIEW' },
          { label: 'Bukti Belum Lengkap', value: 'MISSING_DOCUMENT' },
        ].map((tab) => (
          <button
            key={tab.value}
            onClick={() => setFlagFilter(tab.value as any)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              flagFilter === tab.value
                ? 'bg-blue-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <DataTable
        columns={columns}
        data={queueItems}
        keyExtractor={(t) => t.id}
        isLoading={isLoading}
        searchPlaceholder="Cari kode atau pihak..."
        searchKeys={['transaction_code', 'description', 'counterparty_name']}
        emptyTitle="Antrean review bersih"
        emptyDescription="Seluruh transaksi operasional telah ditinjau dan lolos verifikasi."
        onRowClick={(t) => setSelectedTrx(t)}
      />

      <ReviewDrawer
        transaction={selectedTrx}
        isOpen={!!selectedTrx}
        onClose={() => setSelectedTrx(null)}
        onRefresh={() => refetch()}
      />
    </div>
  );
};
