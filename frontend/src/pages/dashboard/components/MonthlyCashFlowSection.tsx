import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowDownLeft, ArrowUpRight, Scale, AlertCircle } from 'lucide-react';
import { reportsApi } from '../../../api/reports';
import { formatIDR } from '../../../utils/formatters';
import { Card } from '../../../components/ui/Card';
import { SkeletonLoader } from '../../../components/feedback/SkeletonLoader';

export const MonthlyCashFlowSection: React.FC = () => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-cash-flow-trend'],
    queryFn: () => reportsApi.getCashFlowTrend(6),
  });

  const items = data?.items || [];
  const currentMonth = items.length > 0 ? items[items.length - 1] : null;
  const cashIn = currentMonth ? Number(currentMonth.cash_in) : 0;
  const cashOut = currentMonth ? Number(currentMonth.cash_out) : 0;
  const netCash = currentMonth ? Number(currentMonth.net_cash) : (cashIn - cashOut);
  const periodLabel = currentMonth?.month_label || 'Bulan Ini';

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="monthly-cash-flow-loading">
        <div className="h-4 w-40 bg-slate-200 animate-pulse rounded-sm" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <SkeletonLoader count={3} className="h-20 w-full" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-slate-600">
          <AlertCircle className="h-4 w-4 text-rose-500" />
          <span>Data arus kas bulan ini belum dapat dimuat.</span>
        </div>
        <button
          onClick={() => refetch()}
          className="text-blue-600 hover:underline font-medium cursor-pointer"
        >
          Coba lagi
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="monthly-cash-flow-section">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Arus Kas Bulan Ini
          </h3>
          <span className="text-[11px] font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
            {periodLabel}
          </span>
        </div>
        <p className="text-[11px] text-slate-400">
          Mutasi kas & bank riil (Uang Masuk ≠ Pendapatan, Uang Keluar ≠ Biaya)
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 1. Uang Masuk */}
        <Card className="p-4 bg-white border border-emerald-200 shadow-xs" data-testid="card-uang-masuk">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase text-emerald-800 tracking-wider">
              Uang Masuk
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
              <ArrowDownLeft className="h-3.5 w-3.5" />
            </div>
          </div>
          <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-emerald-700">
            {formatIDR(cashIn)}
          </p>
          <div className="text-[10px] text-slate-500 mt-1">
            Penerimaan riil ke kas & bank periode ini
          </div>
        </Card>

        {/* 2. Uang Keluar */}
        <Card className="p-4 bg-white border border-rose-200 shadow-xs" data-testid="card-uang-keluar">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase text-rose-800 tracking-wider">
              Uang Keluar
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-rose-50 text-rose-600">
              <ArrowUpRight className="h-3.5 w-3.5" />
            </div>
          </div>
          <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-rose-700">
            {formatIDR(cashOut)}
          </p>
          <div className="text-[10px] text-slate-500 mt-1">
            Pengeluaran riil dari kas & bank periode ini
          </div>
        </Card>

        {/* 3. Arus Kas Bersih */}
        <Card className="p-4 bg-white border border-slate-200 shadow-xs" data-testid="card-arus-kas-bersih">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase text-slate-600 tracking-wider">
              Arus Kas Bersih
            </span>
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 text-slate-600">
              <Scale className="h-3.5 w-3.5" />
            </div>
          </div>
          <p className={`text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 ${
            netCash >= 0 ? 'text-emerald-700' : 'text-rose-700'
          }`}>
            {formatIDR(netCash)}
          </p>
          <div className="text-[10px] text-slate-500 mt-1">
            Surplus / defisit kas (Uang Masuk − Uang Keluar)
          </div>
        </Card>
      </div>
    </div>
  );
};
