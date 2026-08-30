import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DollarSign } from 'lucide-react';
import { receivablesApi, CustomerInvoiceResponse } from '../../api/receivables';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { DataTable, Column } from '../../components/tables/DataTable';
import { Card } from '../../components/ui/Card';
import { CustomerPaymentAllocationModal } from './components/CustomerPaymentAllocationModal';

export const ReceivablesPage: React.FC = () => {
  const [selectedInvoice, setSelectedInvoice] = useState<CustomerInvoiceResponse | null>(null);

  const { data: invoices = [], isLoading, refetch } = useQuery({
    queryKey: ['customer-invoices'],
    queryFn: receivablesApi.list,
  });

  const totalOutstanding = invoices.reduce(
    (sum, inv) => sum + (parseFloat(inv.outstanding_amount) || 0),
    0
  );

  const overdueCount = invoices.filter((inv) => inv.collection_status === 'OVERDUE').length;

  const columns: Column<CustomerInvoiceResponse>[] = [
    {
      key: 'invoice_number',
      header: 'No. Invoice',
      sortable: true,
      render: (inv) => (
        <span className="font-mono text-xs font-semibold text-blue-600">
          {inv.invoice_number}
        </span>
      ),
    },
    {
      key: 'customer_name',
      header: 'Pelanggan & Proyek',
      sortable: true,
      render: (inv) => (
        <div>
          <p className="font-semibold text-slate-900">{inv.customer_name || 'Pelanggan'}</p>
          <p className="text-[11px] text-slate-500">{inv.project_name || 'Proyek Umum'}</p>
        </div>
      ),
    },
    {
      key: 'due_date',
      header: 'Jatuh Tempo',
      sortable: true,
      render: (inv) => <span className="text-xs text-slate-600">{formatDate(inv.due_date)}</span>,
    },
    {
      key: 'total_amount',
      header: 'Total Tagihan',
      sortable: true,
      align: 'right',
      render: (inv) => (
        <span className="font-mono text-xs text-slate-600 tabular-nums">
          {formatIDR(inv.total_amount)}
        </span>
      ),
    },
    {
      key: 'outstanding_amount',
      header: 'Sisa Piutang',
      sortable: true,
      align: 'right',
      render: (inv) => (
        <span className="font-mono text-xs font-bold text-slate-900 tabular-nums">
          {formatIDR(inv.outstanding_amount)}
        </span>
      ),
    },
    {
      key: 'collection_status',
      header: 'Status',
      align: 'center',
      render: (inv) => <StatusBadge status={inv.collection_status} size="sm" />,
    },
    {
      key: 'actions',
      header: 'Aksi',
      align: 'right',
      render: (inv) =>
        parseFloat(inv.outstanding_amount) > 0 ? (
          <Button
            size="sm"
            variant="outline"
            leftIcon={<DollarSign className="h-3.5 w-3.5 text-emerald-600" />}
            onClick={() => setSelectedInvoice(inv)}
          >
            Terima Bayar
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
            Piutang Usaha (Accounts Receivable)
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Pantau tagihan invoice termin proyek yang belum dibayar oleh pelanggan. Nilai saldo berasal mutlak dari sub-ledger backend.
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card className="p-4 bg-slate-900 text-white">
          <p className="text-[11px] font-semibold uppercase text-slate-400">Total Sisa Piutang Berjalan</p>
          <p className="text-2xl font-bold font-mono tabular-nums mt-1 text-white">
            {formatIDR(totalOutstanding)}
          </p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-semibold uppercase text-slate-500">Invoice Lewat Jatuh Tempo</p>
          <p className="text-2xl font-bold font-mono tabular-nums mt-1 text-rose-600">
            {overdueCount} Invoice
          </p>
        </Card>
      </div>

      <DataTable
        columns={columns}
        data={invoices}
        keyExtractor={(inv) => inv.id}
        isLoading={isLoading}
        searchPlaceholder="Cari nomor invoice atau pelanggan..."
        searchKeys={['invoice_number', 'customer_name', 'project_name']}
        emptyTitle="Tidak ada piutang aktif"
        emptyDescription="Seluruh invoice pelanggan telah tertagih dan lunas."
      />

      <CustomerPaymentAllocationModal
        invoice={selectedInvoice}
        isOpen={!!selectedInvoice}
        onClose={() => setSelectedInvoice(null)}
        onSuccess={() => refetch()}
      />
    </div>
  );
};
