import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { reportsApi } from '../../../api/reports';
import { formatIDR } from '../../../utils/formatters';
import { SkeletonLoader } from '../../../components/feedback/SkeletonLoader';
import { Card } from '../../../components/ui/Card';
import { TrendingUp, AlertCircle } from 'lucide-react';

export const CashFlowTrendChart: React.FC = () => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-cash-flow-trend'],
    queryFn: () => reportsApi.getCashFlowTrend(6),
  });

  const items = data?.items || [];
  const hasData = items.some(
    (it) => Number(it.cash_in) > 0 || Number(it.cash_out) > 0 || Number(it.net_cash) !== 0
  );

  const formatYAxis = (val: number) => {
    if (val === 0) return '0';
    const absVal = Math.abs(val);
    if (absVal >= 1_000_000_000) {
      return `${(val / 1_000_000_000).toFixed(1)}M`;
    }
    if (absVal >= 1_000_000) {
      return `${(val / 1_000_000).toFixed(0)}jt`;
    }
    return val.toLocaleString('id-ID');
  };

  const chartData = items.map((item) => ({
    period: item.period,
    label: item.month_label,
    cash_in: Number(item.cash_in) || 0,
    cash_out: Number(item.cash_out) || 0,
    net_cash: Number(item.net_cash) || 0,
  }));

  return (
    <Card className="p-5 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
            <TrendingUp className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm md:text-base font-bold text-slate-900">Arus Kas 6 Bulan Terakhir</h3>
            <p className="text-[11px] text-slate-500">Perbandingan penerimaan vs pengeluaran riil per bulan</p>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="h-56 flex flex-col justify-center">
          <SkeletonLoader count={3} className="h-8 w-full mb-2" />
        </div>
      ) : isError ? (
        <div className="h-56 flex flex-col items-center justify-center text-center p-4 bg-rose-50/30 rounded-lg border border-rose-100">
          <AlertCircle className="h-6 w-6 text-rose-500 mb-1.5" />
          <p className="text-xs font-semibold text-slate-700">Gagal memuat tren arus kas</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-xs text-blue-600 hover:underline font-medium cursor-pointer"
          >
            Coba lagi
          </button>
        </div>
      ) : !hasData ? (
        <div className="h-56 flex flex-col items-center justify-center text-center p-4 bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
          <p className="text-xs font-medium text-slate-600">Data arus kas belum tersedia</p>
          <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
            Belum ada mutasi kas atau bank yang tercatat dalam 6 bulan terakhir.
          </p>
        </div>
      ) : (
        <div className="h-56 w-full" data-testid="cash-flow-trend-chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={formatYAxis}
                tick={{ fontSize: 10, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                formatter={(val: any, name: any) => [
                  formatIDR(val),
                  name === 'cash_in'
                    ? 'Kas Masuk'
                    : name === 'cash_out'
                    ? 'Kas Keluar'
                    : 'Arus Kas Bersih',
                ]}
                labelStyle={{ fontWeight: 600, color: '#0f172a' }}
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderColor: '#e2e8f0',
                  borderRadius: '0.5rem',
                  fontSize: '12px',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                }}
              />
              <Legend
                formatter={(val) => (
                  <span className="text-xs text-slate-600 font-medium">
                    {val === 'cash_in'
                      ? 'Kas Masuk'
                      : val === 'cash_out'
                      ? 'Kas Keluar'
                      : 'Arus Kas Bersih'}
                  </span>
                )}
                wrapperStyle={{ paddingTop: '8px' }}
              />
              <Bar dataKey="cash_in" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={32} />
              <Bar dataKey="cash_out" fill="#f43f5e" radius={[4, 4, 0, 0]} maxBarSize={32} />
              <Line
                type="monotone"
                dataKey="net_cash"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ r: 3, fill: '#3b82f6' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
};
