import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
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
import { Scale, AlertCircle } from 'lucide-react';

export const AgingComparisonChart: React.FC = () => {
  const {
    data: arData,
    isLoading: isArLoading,
    isError: isArError,
    refetch: refetchAr,
  } = useQuery({
    queryKey: ['dashboard-ar-aging'],
    queryFn: () => reportsApi.getARAging(),
  });

  const {
    data: apData,
    isLoading: isApLoading,
    isError: isApError,
    refetch: refetchAp,
  } = useQuery({
    queryKey: ['dashboard-ap-aging'],
    queryFn: () => reportsApi.getAPAging(),
  });

  const isLoading = isArLoading || isApLoading;
  const isError = isArError || isApError;

  const arSummary = arData?.summary;
  const apSummary = apData?.summary;

  const chartData = [
    {
      bucket: '0–30 Hari',
      ar: (Number(arSummary?.current) || 0) + (Number(arSummary?.days_1_30) || 0),
      ap: (Number(apSummary?.current) || 0) + (Number(apSummary?.days_1_30) || 0),
    },
    {
      bucket: '31–60 Hari',
      ar: Number(arSummary?.days_31_60) || 0,
      ap: Number(apSummary?.days_31_60) || 0,
    },
    {
      bucket: '61–90 Hari',
      ar: Number(arSummary?.days_61_90) || 0,
      ap: Number(apSummary?.days_61_90) || 0,
    },
    {
      bucket: '>90 Hari',
      ar: Number(arSummary?.days_over_90) || 0,
      ap: Number(apSummary?.days_over_90) || 0,
    },
  ];

  const hasData = chartData.some((d) => d.ar > 0 || d.ap > 0);

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

  return (
    <Card className="p-5 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            <Scale className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm md:text-base font-bold text-slate-900">Umur Piutang & Utang (Aging)</h3>
            <p className="text-[11px] text-slate-500">Perbandingan jatuh tempo piutang pelanggan vs utang vendor</p>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="h-64 flex flex-col justify-center">
          <SkeletonLoader count={4} className="h-10 w-full mb-2" />
        </div>
      ) : isError ? (
        <div className="h-64 flex flex-col items-center justify-center text-center p-4">
          <AlertCircle className="h-8 w-8 text-rose-500 mb-2" />
          <p className="text-xs font-semibold text-slate-700">Gagal memuat umur piutang & utang</p>
          <button
            onClick={() => {
              refetchAr();
              refetchAp();
            }}
            className="mt-2 text-xs text-blue-600 hover:underline font-medium cursor-pointer"
          >
            Coba lagi
          </button>
        </div>
      ) : !hasData ? (
        <div className="h-64 flex flex-col items-center justify-center text-center p-4 bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
          <p className="text-xs font-medium text-slate-600">Tidak ada piutang atau utang outstanding</p>
          <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
            Seluruh invoice pelanggan dan bill vendor saat ini sudah lunas atau belum ada tagihan berjalan.
          </p>
        </div>
      ) : (
        <div className="h-64 w-full" data-testid="aging-comparison-chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis
                tickFormatter={formatYAxis}
                tick={{ fontSize: 10, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                formatter={(val: any, name: any) => [
                  formatIDR(val),
                  name === 'ar' ? 'Piutang (AR)' : 'Utang (AP)',
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
                    {val === 'ar' ? 'Piutang Pelanggan' : 'Utang Vendor'}
                  </span>
                )}
                wrapperStyle={{ paddingTop: '8px' }}
              />
              <Bar dataKey="ar" fill="#2563eb" radius={[4, 4, 0, 0]} maxBarSize={36} />
              <Bar dataKey="ap" fill="#e11d48" radius={[4, 4, 0, 0]} maxBarSize={36} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
};
