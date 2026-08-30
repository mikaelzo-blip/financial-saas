import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ReportHeader } from '../../components/reports/ReportHeader';

export const ARAgingPage: React.FC = () => {
  const today = new Date().toISOString().split('T')[0];
  const [asOfDate, setAsOfDate] = useState<string>(today);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['ar-aging', asOfDate],
    queryFn: () => reportsApi.getARAging(asOfDate),
  });

  const getBucketBadge = (bucket: string, days: number) => {
    if (bucket === 'CURRENT') {
      return <span className="bg-emerald-100 text-emerald-800 text-xs px-2 py-0.5 rounded font-medium">Belum Jatuh Tempo</span>;
    }
    if (bucket === '1_30') {
      return <span className="bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded font-medium">{days} Hari (1-30)</span>;
    }
    if (bucket === '31_60') {
      return <span className="bg-orange-100 text-orange-800 text-xs px-2 py-0.5 rounded font-medium">{days} Hari (31-60)</span>;
    }
    return <span className="bg-rose-100 text-rose-800 text-xs px-2 py-0.5 rounded font-bold">{days} Hari (&gt;60)</span>;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Umur Piutang Usaha (AR Aging)</h1>
          <p className="text-sm text-slate-500">
            Analisis jatuh tempo dan aging bucket piutang pelanggan kontraktor.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="w-44"
          />
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
            Perbarui
          </Button>
          <ReportHeader reportType="receivables-aging" params={{ as_of_date: asOfDate }} disabled={!data} />
        </div>
      </div>

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          {/* Summary Buckets */}
          <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
            <Card className="p-3 bg-emerald-50/70 border-emerald-200">
              <span className="text-[11px] font-semibold text-emerald-800 uppercase">Belum JT</span>
              <div className="text-sm font-bold font-mono text-emerald-950 mt-1">{formatIDR(data.summary.current)}</div>
            </Card>
            <Card className="p-3 bg-amber-50/70 border-amber-200">
              <span className="text-[11px] font-semibold text-amber-800 uppercase">1 - 30 Hari</span>
              <div className="text-sm font-bold font-mono text-amber-950 mt-1">{formatIDR(data.summary.days_1_30)}</div>
            </Card>
            <Card className="p-3 bg-orange-50/70 border-orange-200">
              <span className="text-[11px] font-semibold text-orange-800 uppercase">31 - 60 Hari</span>
              <div className="text-sm font-bold font-mono text-orange-950 mt-1">{formatIDR(data.summary.days_31_60)}</div>
            </Card>
            <Card className="p-3 bg-rose-50/70 border-rose-200">
              <span className="text-[11px] font-semibold text-rose-800 uppercase">61 - 90 Hari</span>
              <div className="text-sm font-bold font-mono text-rose-950 mt-1">{formatIDR(data.summary.days_61_90)}</div>
            </Card>
            <Card className="p-3 bg-rose-100/80 border-rose-300">
              <span className="text-[11px] font-semibold text-rose-900 uppercase">&gt; 90 Hari</span>
              <div className="text-sm font-bold font-mono text-rose-950 mt-1">{formatIDR(data.summary.days_over_90)}</div>
            </Card>
            <Card className="p-3 bg-slate-900 text-white">
              <span className="text-[11px] font-semibold text-slate-300 uppercase">Total Piutang</span>
              <div className="text-sm font-bold font-mono text-emerald-400 mt-1">{formatIDR(data.summary.total)}</div>
            </Card>
          </div>

          {/* Table */}
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100 text-slate-700 text-xs font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 border-b border-r border-slate-200">No. Invoice</th>
                    <th className="px-4 py-3 border-b border-r border-slate-200">Pelanggan & Proyek</th>
                    <th className="px-4 py-3 border-b border-r border-slate-200">Tgl Invoice / JT</th>
                    <th className="px-4 py-3 border-b border-r border-slate-200">Status Aging</th>
                    <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Total Tagihan</th>
                    <th className="px-4 py-3 border-b border-slate-200 text-right">Sisa Piutang</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {data.invoices.map((inv) => (
                    <tr key={inv.invoice_number} className="hover:bg-slate-50">
                      <td className="px-4 py-2.5 font-bold font-mono text-indigo-700 border-r border-slate-100">
                        {inv.invoice_number}
                      </td>
                      <td className="px-4 py-2.5 border-r border-slate-100">
                        <div className="font-semibold text-slate-900">{inv.customer_name}</div>
                        {inv.project_code && (
                          <div className="text-[11px] text-slate-500 font-mono">
                            {inv.project_code} {inv.project_name ? `(${inv.project_name})` : ''}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2.5 border-r border-slate-100 font-mono text-slate-700">
                        <div>Inv: {inv.invoice_date}</div>
                        <div className="text-[11px] text-slate-500">JT: {inv.due_date}</div>
                      </td>
                      <td className="px-4 py-2.5 border-r border-slate-100">
                        {getBucketBadge(inv.bucket, inv.days_overdue)}
                      </td>
                      <td className="px-4 py-2.5 text-right border-r border-slate-100 font-mono text-slate-600">
                        {formatIDR(inv.total_amount)}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono font-bold text-slate-900 bg-slate-50/50">
                        {formatIDR(inv.outstanding_amount)}
                      </td>
                    </tr>
                  ))}
                  {data.invoices.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-400 italic">
                        Tidak ada piutang outstanding per {data.as_of_date}.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
};
