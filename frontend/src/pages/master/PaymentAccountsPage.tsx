import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Building,
  Banknote,
  ArrowDownLeft,
  ArrowUpRight,
  History,
  Wallet,
  Landmark,
  AlertTriangle,
  ChevronRight,
} from 'lucide-react';
import { masterApi } from '../../api/master';
import { reportsApi } from '../../api/reports';
import { moneyMovementsApi, MoneyMovementDTO } from '../../api/moneyMovements';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Card } from '../../components/ui/Card';
import { DataTable, Column } from '../../components/tables/DataTable';
import { Badge } from '../../components/ui/Badge';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { CashFlowTrendChart } from '../dashboard/components/CashFlowTrendChart';

interface AccountDisplayRow {
  id: string;
  name: string;
  bank_name?: string | null;
  account_number?: string | null;
  account_type: string;
  coa_account_code: string;
  balance: number | string;
  is_active: boolean;
  last_movement_date?: string | null;
}

export const PaymentAccountsPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedAccount, setSelectedAccount] = useState<string>('');

  // 1. Operational Overview
  const { data: overview, isLoading: isOverviewLoading } = useQuery({
    queryKey: ['cash-bank-overview'],
    queryFn: () => reportsApi.getCashBankOverview(),
  });

  // 2. Master Accounts fallback
  const { data: rawAccounts = [], isLoading: isRawAccountsLoading } = useQuery({
    queryKey: ['payment-accounts'],
    queryFn: masterApi.getPaymentAccounts,
  });

  // 3. Money movements
  const { data: movements = [], isLoading: isMovementsLoading } = useQuery({
    queryKey: ['money-movements', selectedAccount],
    queryFn: () => moneyMovementsApi.listMovements(selectedAccount || undefined),
  });

  const isAccountsLoading = isOverviewLoading || isRawAccountsLoading;

  // Build merged accounts display list
  const accountRows: AccountDisplayRow[] = React.useMemo(() => {
    if (overview?.accounts && overview.accounts.length > 0) {
      return overview.accounts.map((acc) => ({
        id: acc.id,
        name: acc.name,
        bank_name: acc.bank_name,
        account_number: acc.account_number,
        account_type: acc.account_type,
        coa_account_code: acc.coa_account_code,
        balance: acc.balance,
        is_active: acc.is_active,
        last_movement_date: acc.last_movement_date,
      }));
    }

    return rawAccounts.map((a) => ({
      id: a.id,
      name: a.name,
      bank_name: a.bank_name,
      account_number: a.account_number,
      account_type: a.account_type,
      coa_account_code: a.coa_account_code,
      balance: '0.00',
      is_active: a.is_active,
      last_movement_date: null,
    }));
  }, [overview, rawAccounts]);

  const totalCashBank = overview ? overview.total_cash_and_bank : '0.00';
  const totalBank = overview ? overview.total_bank : '0.00';
  const totalCash = overview ? overview.total_cash : '0.00';
  const unmatchedCount = overview ? overview.unmatched_movements_count : 0;
  const unmatchedAmount = overview ? overview.unmatched_amount : '0.00';

  const accountColumns: Column<AccountDisplayRow>[] = [
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
      header: 'Nama Rekening / Kas',
      sortable: true,
      render: (a) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-700 shrink-0">
            {a.account_type === 'CASH' || a.name.toLowerCase().includes('kas') ? (
              <Banknote className="h-4 w-4 text-emerald-600" />
            ) : (
              <Building className="h-4 w-4 text-blue-600" />
            )}
          </div>
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
      header: 'Tipe',
      align: 'center',
      render: (a) => (
        <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
          {a.account_type === 'CASH' || a.name.toLowerCase().includes('kas') ? 'KAS' : 'BANK'}
        </span>
      ),
    },
    {
      key: 'balance',
      header: 'Saldo Riil Saat Ini',
      sortable: true,
      align: 'right',
      render: (a) => (
        <span className="font-bold text-slate-900 font-mono tabular-nums text-xs md:text-sm">
          {formatIDR(a.balance)}
        </span>
      ),
    },
    {
      key: 'last_movement_date',
      header: 'Mutasi Terakhir',
      render: (a) => (
        <span className="text-xs text-slate-500">
          {a.last_movement_date ? formatDate(a.last_movement_date) : 'Belum ada'}
        </span>
      ),
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
      {/* Header */}
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">
          Workspace Kas & Bank
        </h2>
        <p className="text-xs md:text-sm text-slate-500 mt-1">
          Monitoring likuiditas riil, saldo per rekening bank, mutasi kas, dan rekonsiliasi pembayaran.
        </p>
      </div>

      {/* Top 4 KPI Summary Cards */}
      {isOverviewLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SkeletonLoader count={4} className="h-24 w-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Kas & Bank */}
          <Card className="p-4 bg-slate-900 text-white shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-400">Total Kas & Bank</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-600/30 text-blue-400">
                <Wallet className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-white">
              {formatIDR(totalCashBank)}
            </p>
            <p className="text-[10px] text-slate-400 mt-1">Saldo likuid seluruh akun</p>
          </Card>

          {/* Saldo Bank */}
          <Card className="p-4 bg-white border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Saldo Rekening Bank</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                <Landmark className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-blue-700">
              {formatIDR(totalBank)}
            </p>
            <p className="text-[10px] text-slate-500 mt-1">Akumulasi saldo perbankan</p>
          </Card>

          {/* Saldo Kas */}
          <Card className="p-4 bg-white border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Saldo Kas Tunai</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
                <Banknote className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-emerald-700">
              {formatIDR(totalCash)}
            </p>
            <p className="text-[10px] text-slate-500 mt-1">Kas operasional & kas kecil</p>
          </Card>

          {/* Mutasi Belum Cocok */}
          <Card
            className={`p-4 border transition-colors shadow-xs ${
              unmatchedCount > 0
                ? 'bg-amber-50/70 border-amber-200 cursor-pointer hover:border-amber-300'
                : 'bg-white border-slate-200'
            }`}
            onClick={() => unmatchedCount > 0 && navigate('/bank-reconciliation')}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-600">Mutasi Belum Cocok</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-100 text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-amber-900">
              {unmatchedCount} Mutasi
            </p>
            <div className="text-[10px] text-amber-800 mt-1 flex items-center justify-between">
              <span>{formatIDR(unmatchedAmount)}</span>
              {unmatchedCount > 0 && (
                <span className="font-semibold underline flex items-center">
                  Cocokkan <ChevronRight className="h-3 w-3" />
                </span>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Middle: Live Account Balances Table */}
      <div className="space-y-3">
        <h3 className="text-sm md:text-base font-bold text-slate-900">
          Daftar Akun & Saldo Berjalan
        </h3>
        <DataTable
          columns={accountColumns}
          data={accountRows}
          keyExtractor={(a) => a.id}
          isLoading={isAccountsLoading}
          searchPlaceholder="Cari nama akun, nomor rekening, atau bank..."
          searchKeys={['name', 'coa_account_code', 'bank_name', 'account_number']}
          emptyTitle="Belum ada akun kas atau bank"
          emptyDescription="Inisialisasi akun kas dan rekening bank melalui data master bagan akun."
        />
      </div>

      {/* Cash Flow Trend Chart */}
      <div className="space-y-3">
        <CashFlowTrendChart />
      </div>

      {/* Recent Movements Section */}
      <div className="space-y-3 pt-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-blue-600" />
            <h3 className="text-sm md:text-base font-bold text-slate-900">
              Riwayat Mutasi Arus Kas
            </h3>
          </div>
          <select
            value={selectedAccount}
            onChange={(e) => setSelectedAccount(e.target.value)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 focus:ring-2 focus:ring-blue-500 outline-hidden"
          >
            <option value="">Semua Rekening Kas & Bank</option>
            {accountRows.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.coa_account_code})
              </option>
            ))}
          </select>
        </div>

        <Card className="overflow-hidden">
          {isMovementsLoading ? (
            <div className="p-6">
              <SkeletonLoader count={3} className="h-12 w-full" />
            </div>
          ) : movements.length === 0 ? (
            <div className="p-8 text-center bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
              <p className="text-xs font-semibold text-slate-700">Belum ada mutasi arus kas tercatat</p>
              <p className="text-[11px] text-slate-500 mt-1 max-w-sm mx-auto">
                Mutasi otomatis tercatat saat Anda mengimpor rekening koran bank atau mencatat transaksi penerimaan/pengeluaran kas.
              </p>
              <button
                onClick={() => navigate('/bank-reconciliation')}
                className="mt-3 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-semibold cursor-pointer"
              >
                <span>Buka Rekonsiliasi Bank</span>
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-3 px-4">Tanggal</th>
                    <th className="py-3 px-4">Kode Mutasi</th>
                    <th className="py-3 px-4">Arah</th>
                    <th className="py-3 px-4">Keterangan / Ref</th>
                    <th className="py-3 px-4 text-right">Nominal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {movements.map((m: MoneyMovementDTO) => (
                    <tr key={m.id} className="hover:bg-slate-50">
                      <td className="py-3 px-4 text-slate-600">{formatDate(m.movement_date)}</td>
                      <td className="py-3 px-4 font-mono font-bold text-blue-600">{m.movement_code}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
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
                      <td className="py-3 px-4 text-slate-700">
                        <p className="font-medium">{m.description || '-'}</p>
                        {m.reference_no && (
                          <p className="text-[10px] text-slate-400">Ref: {m.reference_no}</p>
                        )}
                      </td>
                      <td
                        className={`py-3 px-4 text-right font-mono font-bold tabular-nums text-xs ${
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
