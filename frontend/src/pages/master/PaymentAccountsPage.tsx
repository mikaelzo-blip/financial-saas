import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building, Banknote } from 'lucide-react';
import { masterApi } from '../../api/master';
import { PaymentAccountResponse } from '../../types/api';
import { Card } from '../../components/ui/Card';
import { DataTable, Column } from '../../components/tables/DataTable';
import { Badge } from '../../components/ui/Badge';

export const PaymentAccountsPage: React.FC = () => {
  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ['payment-accounts'],
    queryFn: masterApi.getPaymentAccounts,
  });

  const columns: Column<PaymentAccountResponse>[] = [
    {
      key: 'account_code',
      header: 'Kode Akun',
      sortable: true,
      render: (a) => (
        <span className="font-mono text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
          {a.account_code}
        </span>
      ),
    },
    {
      key: 'account_name',
      header: 'Nama Akun / Rekening',
      sortable: true,
      render: (a) => (
        <div className="flex items-center gap-2">
          {a.account_type === 'CASH' || a.account_type === 'PETTY_CASH' ? (
            <Banknote className="h-4 w-4 text-emerald-600" />
          ) : (
            <Building className="h-4 w-4 text-blue-600" />
          )}
          <div>
            <p className="font-semibold text-slate-900">{a.account_name}</p>
            {a.bank_name && (
              <p className="text-[11px] text-slate-500">
                {a.bank_name} {a.account_number ? `• No: ${a.account_number}` : ''}
              </p>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'account_type',
      header: 'Tipe Akun',
      render: (a) => <span className="text-xs text-slate-600 font-medium">{a.account_type}</span>,
    },
    {
      key: 'is_active',
      header: 'Status',
      align: 'center',
      render: (a) => (
        <Badge variant={a.is_active ? 'success' : 'neutral'} size="sm">
          {a.is_active ? 'Aktif' : 'Non-Aktif'}
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Akun Kas & Bank</h2>
        <p className="text-xs text-slate-500 mt-1">
          Daftar rekening bank operasional dan kas tunai perusahaan untuk penerimaan dan pengeluaran dana.
        </p>
      </div>

      <Card>
        <DataTable
          columns={columns}
          data={accounts}
          keyExtractor={(a) => a.id}
          isLoading={isLoading}
          searchPlaceholder="Cari nama akun atau bank..."
          searchKeys={['account_name', 'account_code', 'bank_name']}
          emptyTitle="Belum ada akun kas/bank terdaftar"
          emptyDescription="Akun kas dan bank dibuat melalui inisialisasi master data."
        />
      </Card>
    </div>
  );
};
