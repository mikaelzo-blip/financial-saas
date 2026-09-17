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
import { Building2, AlertCircle } from 'lucide-react';

export const ProjectPerformanceChart: React.FC = () => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-project-performance'],
    queryFn: () => reportsApi.getProjectPerformance('ACTIVE', 5),
  });

  const items = data?.items || [];
  const hasData = items.length > 0 && items.some(
    (p) => Number(p.contract_value) > 0 || Number(p.actual_cost) > 0
  );

  const formatXAxis = (val: number) => {
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

  const chartData = items.map((p) => ({
    id: p.project_id,
    name: p.project_name,
    shortName: p.project_name.length > 20 ? `${p.project_name.substring(0, 18)}...` : p.project_name,
    code: p.project_code,
    customer: p.customer_name || '-',
    contract: Number(p.contract_value) || 0,
    cost: Number(p.actual_cost) || 0,
    marginPct: Number(p.gross_margin_percentage) || 0,
    progressPct: Number(p.financial_progress_percentage) || 0,
  }));

  const chartHeight = Math.max(180, Math.min(chartData.length * 48 + 48, 320));

  return (
    <Card className="p-5 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <Building2 className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm md:text-base font-bold text-slate-900">Kinerja Proyek Aktif</h3>
            <p className="text-[11px] text-slate-500">Perbandingan nilai kontrak vs realisasi biaya proyek</p>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="h-44 flex flex-col justify-center">
          <SkeletonLoader count={3} className="h-8 w-full mb-2" />
        </div>
      ) : isError ? (
        <div className="h-44 flex flex-col items-center justify-center text-center p-4 bg-rose-50/30 rounded-lg border border-rose-100">
          <AlertCircle className="h-6 w-6 text-rose-500 mb-1.5" />
          <p className="text-xs font-semibold text-slate-700">Gagal memuat data kinerja proyek</p>
          <button
            onClick={() => refetch()}
            className="mt-2 text-xs text-blue-600 hover:underline font-medium cursor-pointer"
          >
            Coba lagi
          </button>
        </div>
      ) : !hasData ? (
        <div className="h-44 flex flex-col items-center justify-center text-center p-4 bg-slate-50/50 rounded-lg border border-dashed border-slate-200">
          <p className="text-xs font-medium text-slate-600">Belum ada proyek aktif dengan data keuangan.</p>
          <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
            Data perbandingan kontrak dan biaya akan tampil saat proyek aktif memiliki pembukuan.
          </p>
        </div>
      ) : (
        <div style={{ height: `${chartHeight}px` }} className="w-full" data-testid="project-performance-chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={chartData}
              margin={{ top: 10, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis
                type="number"
                tickFormatter={formatXAxis}
                tick={{ fontSize: 10, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="shortName"
                tick={{ fontSize: 11, fill: '#334155' }}
                axisLine={false}
                tickLine={false}
                width={120}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const dataPoint = payload[0].payload;
                    return (
                      <div className="bg-white p-3 border border-slate-200 rounded-lg shadow-md text-xs space-y-1">
                        <p className="font-bold text-slate-900">{dataPoint.name}</p>
                        <p className="text-[11px] text-slate-500">Klien: {dataPoint.customer} ({dataPoint.code})</p>
                        <div className="border-t border-slate-100 my-1 pt-1 space-y-0.5">
                          <p className="text-blue-600 font-medium flex justify-between gap-4">
                            <span>Kontrak:</span>
                            <span className="font-mono">{formatIDR(dataPoint.contract)}</span>
                          </p>
                          <p className="text-amber-600 font-medium flex justify-between gap-4">
                            <span>Biaya Aktual:</span>
                            <span className="font-mono">{formatIDR(dataPoint.cost)}</span>
                          </p>
                          <p className="text-emerald-600 font-medium flex justify-between gap-4">
                            <span>Margin:</span>
                            <span className="font-mono">{dataPoint.marginPct}%</span>
                          </p>
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend
                formatter={(val) => (
                  <span className="text-xs text-slate-600 font-medium">
                    {val === 'contract' ? 'Nilai Kontrak' : 'Biaya Aktual'}
                  </span>
                )}
                wrapperStyle={{ paddingTop: '8px' }}
              />
              <Bar dataKey="contract" name="contract" fill="#3b82f6" radius={[0, 4, 4, 0]} maxBarSize={18} />
              <Bar dataKey="cost" name="cost" fill="#f59e0b" radius={[0, 4, 4, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
};
