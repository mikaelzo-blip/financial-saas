import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Receipt } from 'lucide-react';
import { transactionsApi } from '../../api/transactions';
import { TransactionResponse, WorkflowStatus } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { DataTable, Column } from '../../components/tables/DataTable';

export const TransactionListPage: React.FC = () => {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<WorkflowStatus | ''>('');

  const { data: transactions = [], isLoading } = useQuery({
    queryKey: ['transactions', statusFilter],
    queryFn: () => transactionsApi.list(statusFilter ? { status: statusFilter } : undefined),
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
      key: 'workflow_status',
      header: 'Status',
      align: 'center',
      render: (t) => (
        <div className="flex flex-col items-center gap-1">
          <StatusBadge status={t.workflow_status} size="sm" />
          {t.review_flags && t.review_flags.length > 0 && (
            <span className="text-[10px] text-amber-600 font-medium">
              {t.review_flags.length} flag review
            </span>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Riwayat Transaksi</h2>
          <p className="text-xs text-slate-500 mt-1">
            Daftar seluruh transaksi operasional perusahaan, status verifikasi, dan posting buku besar.
          </p>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => navigate('/transactions/new')}
        >
          Catat Transaksi Baru
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-slate-200 pb-2">
        {[
          { label: 'Semua Transaksi', value: '' },
          { label: 'Siap Posting', value: 'STAGED' },
          { label: 'Terposting', value: 'POSTED' },
          { label: 'Perlu Review', value: 'REVIEW_REQUIRED' },
          { label: 'Dibatalkan (Reversed)', value: 'REVERSED' },
        ].map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value as any)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              statusFilter === tab.value
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <DataTable
        columns={columns}
        data={transactions}
        keyExtractor={(t) => t.id}
        isLoading={isLoading}
        searchPlaceholder="Cari kode, keterangan, atau pihak..."
        searchKeys={['transaction_code', 'description', 'transaction_type']}
        emptyTitle="Belum ada transaksi"
        emptyDescription="Mulai mencatat transaksi operasional untuk memicu pencatatan akuntansi otomatis."
        emptyAction={
          <Button
            size="sm"
            leftIcon={<Receipt className="h-4 w-4" />}
            onClick={() => navigate('/transactions/new')}
          >
            Catat Transaksi Pertama
          </Button>
        }
        onRowClick={(t) => navigate(`/transactions/${t.id}`)}
      />
    </div>
  );
};
