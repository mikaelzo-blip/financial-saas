import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DollarSign } from 'lucide-react';
import { payablesApi, VendorBillResponse } from '../../api/payables';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { DataTable, Column } from '../../components/tables/DataTable';
import { Card } from '../../components/ui/Card';
import { VendorPaymentAllocationModal } from './components/VendorPaymentAllocationModal';

export const PayablesPage: React.FC = () => {
  const [selectedBill, setSelectedBill] = useState<VendorBillResponse | null>(null);

  const { data: bills = [], isLoading, refetch } = useQuery({
    queryKey: ['vendor-bills'],
    queryFn: payablesApi.list,
  });

  const totalOutstanding = bills.reduce(
    (sum, bill) => sum + (parseFloat(bill.outstanding_amount) || 0),
    0
  );

  const overdueCount = bills.filter((bill) => bill.status === 'OVERDUE').length;

  const columns: Column<VendorBillResponse>[] = [
    {
      key: 'bill_number',
      header: 'No. Tagihan (Bill)',
      sortable: true,
      render: (b) => (
        <span className="font-mono text-xs font-semibold text-blue-600">
          {b.bill_number}
        </span>
      ),
    },
    {
      key: 'vendor_name',
      header: 'Vendor & Proyek Terkait',
      sortable: true,
      render: (b) => (
        <div>
          <p className="font-semibold text-slate-900">{b.vendor_name || 'Vendor'}</p>
          <p className="text-[11px] text-slate-500">{b.project_name || 'Proyek Umum'}</p>
        </div>
      ),
    },
    {
      key: 'due_date',
      header: 'Jatuh Tempo',
      sortable: true,
      render: (b) => <span className="text-xs text-slate-600">{formatDate(b.due_date)}</span>,
    },
    {
      key: 'total_amount',
      header: 'Total Tagihan',
      sortable: true,
      align: 'right',
      render: (b) => (
        <span className="font-mono text-xs text-slate-600 tabular-nums">
          {formatIDR(b.total_amount)}
        </span>
      ),
    },
    {
      key: 'outstanding_amount',
      header: 'Sisa Utang',
      sortable: true,
      align: 'right',
      render: (b) => (
        <span className="font-mono text-xs font-bold text-rose-600 tabular-nums">
          {formatIDR(b.outstanding_amount)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      align: 'center',
      render: (b) => <StatusBadge status={b.status} size="sm" />,
    },
    {
      key: 'actions',
      header: 'Aksi',
      align: 'right',
      render: (b) =>
        parseFloat(b.outstanding_amount) > 0 ? (
          <Button
            size="sm"
            variant="outline"
            leftIcon={<DollarSign className="h-3.5 w-3.5 text-rose-600" />}
            onClick={() => setSelectedBill(b)}
          >
            Bayar Tagihan
          </Button>
        ) : (
          <span className="text-xs text-emerald-600 font-medium">Lunas</span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Utang Usaha (Accounts Payable)
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Daftar kewajiban pembayaran kepada vendor material, mandor, dan subkontraktor.
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card className="p-4 bg-slate-900 text-white">
          <p className="text-[11px] font-semibold uppercase text-slate-400">Total Sisa Utang Vendor</p>
          <p className="text-2xl font-bold font-mono tabular-nums mt-1 text-white">
            {formatIDR(totalOutstanding)}
          </p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-semibold uppercase text-slate-500">Tagihan Jatuh Tempo</p>
          <p className="text-2xl font-bold font-mono tabular-nums mt-1 text-rose-600">
            {overdueCount} Tagihan
          </p>
        </Card>
      </div>

      <DataTable
        columns={columns}
        data={bills}
        keyExtractor={(b) => b.id}
        isLoading={isLoading}
        searchPlaceholder="Cari nomor tagihan atau vendor..."
        searchKeys={['bill_number', 'vendor_name', 'project_name']}
        emptyTitle="Tidak ada tagihan utang"
        emptyDescription="Semua kewajiban tagihan vendor telah diselesaikan."
      />

      <VendorPaymentAllocationModal
        bill={selectedBill}
        isOpen={!!selectedBill}
        onClose={() => setSelectedBill(null)}
        onSuccess={() => refetch()}
      />
    </div>
  );
};
