import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
import { masterApi } from '../../api/master';
import { ChartOfAccountResponse } from '../../types/api';
import { Card } from '../../components/ui/Card';
import { DataTable, Column } from '../../components/tables/DataTable';
import { Badge } from '../../components/ui/Badge';

export const ChartOfAccountsPage: React.FC = () => {
  const { data: coa = [], isLoading } = useQuery({
    queryKey: ['coa'],
    queryFn: masterApi.getCOA,
  });

  const columns: Column<ChartOfAccountResponse>[] = [
    {
      key: 'account_code',
      header: 'Kode Akun',
      sortable: true,
      render: (a) => (
        <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-md">
          {a.account_code}
        </span>
      ),
    },
    {
      key: 'account_name',
      header: 'Nama Akun / Bagan Akun Standar',
      sortable: true,
      render: (a) => (
        <div>
          <p className="font-semibold text-slate-900">{a.account_name}</p>
        </div>
      ),
    },
    {
      key: 'account_type',
      header: 'Klasifikasi (Tipe Akun)',
      sortable: true,
      render: (a) => {
        const typeVariants: Record<string, 'info' | 'warning' | 'purple' | 'success' | 'danger'> = {
          ASSET: 'info',
          LIABILITY: 'warning',
          EQUITY: 'purple',
          REVENUE: 'success',
          EXPENSE: 'danger',
        };
        return (
          <Badge variant={typeVariants[a.account_type] || 'neutral'} size="sm">
            {a.account_type}
          </Badge>
        );
      },
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Bagan Akun Standar (COA)
            </h2>
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
              <ShieldCheck className="h-3 w-3" /> Standar SAK Konstruksi
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Struktur buku besar standar yang digunakan oleh mesin akuntansi otomatis di backend.
          </p>
        </div>
      </div>

      <Card>
        <DataTable
          columns={columns}
          data={coa}
          keyExtractor={(a) => a.id}
          isLoading={isLoading}
          searchPlaceholder="Cari kode atau nama akun..."
          searchKeys={['account_name', 'account_code', 'account_type']}
          emptyTitle="Bagan akun belum diinisialisasi"
          emptyDescription="Bagan akun standar akan dimuat secara otomatis dari master seeder."
        />
      </Card>
    </div>
  );
};
