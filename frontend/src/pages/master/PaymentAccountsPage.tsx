import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building, Banknote, ArrowDownLeft, ArrowUpRight, History } from 'lucide-react';
import { masterApi } from '../../api/master';
import { moneyMovementsApi, MoneyMovementDTO } from '../../api/moneyMovements';
import { PaymentAccountResponse } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Card } from '../../components/ui/Card';
import { DataTable, Column } from '../../components/tables/DataTable';
import { Badge } from '../../components/ui/Badge';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';

export const PaymentAccountsPage: React.FC = () => {
  const [selectedAccount, setSelectedAccount] = useState<string>('');

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ['payment-accounts'],
    queryFn: masterApi.getPaymentAccounts,
  });

  const { data: movements = [], isLoading: isMovementsLoading } = useQuery({
    queryKey: ['money-movements', selectedAccount],
    queryFn: () => moneyMovementsApi.listMovements(selectedAccount || undefined),
  });

  const columns: Column<PaymentAccountResponse>[] = [
    {
      key: 'coa_account_code',
      header: 'Kode Akun',
      sortable: true,
      render: (a) => (
        <span className="font-mono text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
          {a.coa_account_code}
        </span>
      ),
    },
    {
      key: 'name',
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
            <p className="font-semibold text-slate-900">{a.name}</p>
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
          searchKeys={['name', 'coa_account_code', 'bank_name']}
          emptyTitle="Belum ada akun kas/bank terdaftar"
          emptyDescription="Akun kas dan bank dibuat melalui inisialisasi master data."
        />
      </Card>

      {/* Money Movements History */}
      <div className="pt-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-3">
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-bold text-slate-900">Riwayat Arus Kas (Money Movement)</h3>
          </div>
          <select
            value={selectedAccount}
            onChange={(e) => setSelectedAccount(e.target.value)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 focus:ring-2 focus:ring-blue-500 outline-hidden"
          >
            <option value="">Semua Akun Kas/Bank</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.coa_account_code})
              </option>
            ))}
          </select>
        </div>

        <Card>
          {isMovementsLoading ? (
            <div className="p-6">
              <SkeletonLoader count={3} className="h-12 w-full" />
            </div>
          ) : movements.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              Belum ada mutasi arus kas riil tercatat.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase">
                  <tr>
                    <th className="py-2.5 px-4">Tanggal</th>
                    <th className="py-2.5 px-4">Kode Mutasi</th>
                    <th className="py-2.5 px-4">Tipe</th>
                    <th className="py-2.5 px-4">Keterangan / Ref</th>
                    <th className="py-2.5 px-4 text-right">Nominal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {movements.map((m: MoneyMovementDTO) => (
                    <tr key={m.id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-4 text-slate-600">{formatDate(m.movement_date)}</td>
                      <td className="py-2.5 px-4 font-mono font-bold text-blue-600">{m.movement_code}</td>
                      <td className="py-2.5 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                            m.direction === 'IN'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-rose-50 text-rose-700 border border-rose-200'
                          }`}
                        >
                          {m.direction === 'IN' ? (
                            <ArrowDownLeft className="w-3 h-3 mr-1" />
                          ) : (
                            <ArrowUpRight className="w-3 h-3 mr-1" />
                          )}
                          {m.direction === 'IN' ? 'KAS MASUK' : 'KAS KELUAR'}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-slate-700">
                        <p className="font-medium">{m.description || '-'}</p>
                        {m.reference_no && (
                          <p className="text-[10px] text-slate-400">Ref: {m.reference_no}</p>
                        )}
                      </td>
                      <td
                        className={`py-2.5 px-4 text-right font-mono font-bold tabular-nums ${
                          m.direction === 'IN' ? 'text-emerald-700' : 'text-rose-700'
                        }`}
                      >
                        {m.direction === 'IN' ? '+' : '-'} {formatIDR(m.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};
