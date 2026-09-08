import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '../../../api/projects';
import { formatIDR } from '../../../utils/formatters';
import { Card } from '../../../components/ui/Card';
import { SkeletonLoader } from '../../../components/feedback/SkeletonLoader';
import { Info } from 'lucide-react';

export const ProjectProfitabilityTab: React.FC<{ projectId: string }> = ({ projectId }) => {
  const { data: summary, isLoading } = useQuery({
    queryKey: ['project-profitability', projectId],
    queryFn: () => projectsApi.getProfitability(projectId),
  });

  if (isLoading) {
    return <SkeletonLoader count={4} className="h-24 w-full" />;
  }

  if (!summary) {
    return (
      <div className="p-8 text-center text-xs text-slate-500">
        Data biaya dan profitabilitas belum tersedia.
      </div>
    );
  }

  const pnl = summary.pnl || {
    recognized_revenue: '0.00',
    actual_project_cost: '0.00',
    gross_profit: '0.00',
    margin_percentage: '0.00',
  };

  const cash = summary.cash_and_billing || {
    total_invoiced: '0.00',
    total_cash_received: '0.00',
    outstanding_receivable: '0.00',
    cash_spent: '0.00',
    net_cash_flow: '0.00',
    project_cash_surplus: '0.00',
  };

  const marginNum = parseFloat(pnl.margin_percentage || '0');
  const costCategories = Object.entries(summary.cost_categories || {});

  return (
    <div className="space-y-6">
      <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3 text-xs text-amber-900">
        <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <strong className="font-semibold block">Ringkasan manajemen, bukan laporan keuangan formal.</strong>
          <span>Belum termasuk alokasi biaya kantor umum dan pajak perusahaan.</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 bg-slate-900 text-white">
          <p className="text-[11px] font-semibold uppercase text-slate-400">
            Pendapatan Proyek (4101)
          </p>
          <p className="text-xl font-bold font-mono tabular-nums mt-1 text-white">
            {formatIDR(pnl.recognized_revenue)}
          </p>
          <p className="text-[10px] text-slate-400 mt-2">Basis sementara: invoice terposting</p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-semibold uppercase text-slate-500">
            Total Biaya Aktual (5101)
          </p>
          <p className="text-xl font-bold font-mono tabular-nums mt-1 text-rose-600">
            {formatIDR(pnl.actual_project_cost)}
          </p>
          <p className="text-[10px] text-slate-400 mt-2">Akumulasi buku besar proyek</p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-semibold uppercase text-slate-500">Laba Kotor Proyek</p>
          <p
            className={`text-xl font-bold font-mono tabular-nums mt-1 ${
              Number(pnl.gross_profit) >= 0 ? 'text-emerald-600' : 'text-rose-600'
            }`}
          >
            {formatIDR(pnl.gross_profit)}
          </p>
          <p className="text-[10px] text-slate-400 mt-2">Pendapatan - Biaya aktual</p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-semibold uppercase text-slate-500">Margin Laba Kotor</p>
          <p
            className={`text-xl font-bold font-mono tabular-nums mt-1 ${
              marginNum >= 15 ? 'text-emerald-600' : marginNum >= 0 ? 'text-amber-600' : 'text-rose-600'
            }`}
          >
            {marginNum.toFixed(2)}%
          </p>
          <p className="text-[10px] text-slate-400 mt-2">Persentase laba proyek</p>
        </Card>
      </div>

      {/* Cash Flow Summary */}
      <Card title="Posisi Arus Kas Proyek (Cash Basis)">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-6 text-sm">
          <div>
            <p className="text-xs text-slate-500">Total Ditagihkan</p>
            <p className="text-base font-semibold font-mono text-slate-900 mt-1">
              {formatIDR(cash.total_invoiced)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Total Diterima</p>
            <p className="text-base font-semibold font-mono text-emerald-600 mt-1">
              {formatIDR(cash.total_cash_received)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Sisa Piutang</p>
            <p className="text-base font-semibold font-mono text-blue-600 mt-1">
              {formatIDR(cash.outstanding_receivable)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Posisi Kas Bersih</p>
            <p className={`text-base font-semibold font-mono mt-1 ${Number(cash.net_cash_flow) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {formatIDR(cash.net_cash_flow)}
            </p>
          </div>
        </div>
      </Card>

      {/* Breakdown per Kategori Biaya */}
      <Card title="Rincian Biaya per Kategori">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="border-b border-slate-200 bg-slate-50/80 text-xs font-semibold uppercase text-slate-700">
              <tr>
                <th className="px-4 py-3">Kategori Biaya</th>
                <th className="px-4 py-3 text-right">Biaya Aktual</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-xs">
              {costCategories.map(([category, amount]) => (
                <tr key={category} className="hover:bg-slate-50/80">
                  <td className="px-4 py-3 font-sans font-medium text-slate-900">{category}</td>
                  <td className="px-4 py-3 text-right tabular-nums font-semibold text-slate-900">
                    {formatIDR(amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
