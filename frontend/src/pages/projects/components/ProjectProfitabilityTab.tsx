import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '../../../api/projects';
import { formatIDR } from '../../../utils/formatters';
import { Card } from '../../../components/ui/Card';
import { SkeletonLoader } from '../../../components/feedback/SkeletonLoader';

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
    total_actual_cost: '0.00',
    gross_profit: '0.00',
    gross_margin_percentage: '0.00',
  };

  const cash = summary.cash || {
    total_invoiced: '0.00',
    total_received: '0.00',
    outstanding_receivables: '0.00',
    net_cash_position: '0.00',
  };

  const marginNum = parseFloat(pnl.gross_margin_percentage || '0');

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 bg-slate-900 text-white">
          <p className="text-[11px] font-semibold uppercase text-slate-400">
            Pendapatan Diakui (4101)
          </p>
          <p className="text-xl font-bold font-mono tabular-nums mt-1 text-white">
            {formatIDR(pnl.recognized_revenue)}
          </p>
          <p className="text-[10px] text-slate-400 mt-2">Berdasarkan termin invoice</p>
        </Card>

        <Card className="p-4">
          <p className="text-[11px] font-semibold uppercase text-slate-500">
            Total Biaya Aktual (5101)
          </p>
          <p className="text-xl font-bold font-mono tabular-nums mt-1 text-rose-600">
            {formatIDR(pnl.total_actual_cost)}
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
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 text-sm">
          <div>
            <p className="text-xs text-slate-500">Total Ditagihkan (Invoiced)</p>
            <p className="text-base font-semibold font-mono text-slate-900 mt-1">
              {formatIDR(cash.total_invoiced)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Total Diterima (Cash Inflow)</p>
            <p className="text-base font-semibold font-mono text-emerald-600 mt-1">
              {formatIDR(cash.total_received)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Sisa Piutang (AR)</p>
            <p className="text-base font-semibold font-mono text-blue-600 mt-1">
              {formatIDR(cash.outstanding_receivables)}
            </p>
          </div>
        </div>
      </Card>

      {/* Breakdown per Kategori Biaya */}
      <Card title="Rincian Biaya per Kategori (Cost Categories)">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="border-b border-slate-200 bg-slate-50/80 text-xs font-semibold uppercase text-slate-700">
              <tr>
                <th className="px-4 py-3">Kategori Biaya</th>
                <th className="px-4 py-3 text-right">Anggaran (Budget)</th>
                <th className="px-4 py-3 text-right">Biaya Aktual</th>
                <th className="px-4 py-3 text-right">Selisih (Variance)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-xs">
              {(summary.cost_breakdown || []).map((row) => (
                <tr key={row.cost_category} className="hover:bg-slate-50/80">
                  <td className="px-4 py-3 font-sans font-medium text-slate-900">
                    {row.cost_category}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                    {formatIDR(row.budget_amount)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-semibold text-slate-900">
                    {formatIDR(row.actual_cost)}
                  </td>
                  <td
                    className={`px-4 py-3 text-right tabular-nums font-semibold ${
                      Number(row.variance_amount) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}
                  >
                    {formatIDR(row.variance_amount)}
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
