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

export const CashFlowPage: React.FC = () => {
  const today = new Date().toISOString().split('T')[0];
  const firstDayOfMonth = `${today.substring(0, 7)}-01`;

  const [startDate, setStartDate] = useState<string>(firstDayOfMonth);
  const [endDate, setEndDate] = useState<string>(today);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['cash-flow', startDate, endDate],
    queryFn: () => reportsApi.getCashFlow(startDate, endDate),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Laporan Arus Kas (Cash Flow)</h1>
          <p className="text-sm text-slate-500">
            Metode Langsung (Direct Method) penerimaan dan pengeluaran kas riil operasional, investasi, & pendanaan.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-40"
          />
          <span className="text-slate-400">s/d</span>
          <Input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-40"
          />
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
            Perbarui
          </Button>
          <ReportHeader reportType="cash-flow" params={{ start_date: startDate, end_date: endDate }} disabled={!data} />
        </div>
      </div>

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <Card className="p-4 bg-slate-50 border-slate-200">
              <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Saldo Awal Kas</span>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                {formatIDR(data.opening_cash_balance)}
              </div>
            </Card>
            <Card className="p-4 bg-emerald-50/60 border-emerald-200">
              <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Arus Kas Operasi</span>
              <div className="text-lg font-bold font-mono text-emerald-950 mt-1">
                {formatIDR(data.net_operating_cash)}
              </div>
            </Card>
            <Card className="p-4 bg-blue-50/60 border-blue-200">
              <span className="text-xs font-semibold text-blue-800 uppercase tracking-wider">Kenaikan / Penurunan Bersih</span>
              <div className="text-lg font-bold font-mono text-blue-950 mt-1">
                {formatIDR(data.net_cash_change)}
              </div>
            </Card>
            <Card className="p-4 bg-indigo-50/60 border-indigo-200">
              <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider">Saldo Akhir Kas & Bank</span>
              <div className="text-lg font-bold font-mono text-indigo-950 mt-1">
                {formatIDR(data.closing_cash_balance)}
              </div>
            </Card>
          </div>

          <Card className="overflow-hidden p-0">
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center text-xs text-slate-600">
              <span>Entitas: <strong className="text-slate-900">{data.organization_name}</strong></span>
              <span>Periode: <strong className="text-slate-900">{data.period_label}</strong></span>
            </div>

            <div className="p-6 space-y-6 text-sm">
              {/* OPERASI */}
              <div>
                <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                  <span>I. ARUS KAS DARI AKTIVITAS OPERASI</span>
                  <span className="font-mono">{formatIDR(data.net_operating_cash)}</span>
                </h3>
                <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                  {data.operating_activities.lines.map((l, i) => (
                    <div key={i} className="py-2 flex justify-between text-slate-700">
                      <span className="font-sans text-slate-800 pl-4">{l.line_name}</span>
                      <span className={Number(l.amount) < 0 ? 'text-rose-700' : 'text-slate-900'}>
                        {formatIDR(l.amount)}
                      </span>
                    </div>
                  ))}
                  {data.operating_activities.lines.length === 0 && (
                    <div className="py-2 text-slate-400 pl-4 text-xs italic">Tidak ada mutasi kas operasi pada periode ini.</div>
                  )}
                </div>
              </div>

              {/* INVESTASI */}
              <div>
                <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                  <span>II. ARUS KAS DARI AKTIVITAS INVESTASI</span>
                  <span className="font-mono">{formatIDR(data.net_investing_cash)}</span>
                </h3>
                <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                  {data.investing_activities.lines.map((l, i) => (
                    <div key={i} className="py-2 flex justify-between text-slate-700">
                      <span className="font-sans text-slate-800 pl-4">{l.line_name}</span>
                      <span className={Number(l.amount) < 0 ? 'text-rose-700' : 'text-slate-900'}>
                        {formatIDR(l.amount)}
                      </span>
                    </div>
                  ))}
                  {data.investing_activities.lines.length === 0 && (
                    <div className="py-2 text-slate-400 pl-4 text-xs italic">Tidak ada mutasi kas investasi pada periode ini.</div>
                  )}
                </div>
              </div>

              {/* PENDANAAN */}
              <div>
                <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                  <span>III. ARUS KAS DARI AKTIVITAS PENDANAAN</span>
                  <span className="font-mono">{formatIDR(data.net_financing_cash)}</span>
                </h3>
                <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                  {data.financing_activities.lines.map((l, i) => (
                    <div key={i} className="py-2 flex justify-between text-slate-700">
                      <span className="font-sans text-slate-800 pl-4">{l.line_name}</span>
                      <span className={Number(l.amount) < 0 ? 'text-rose-700' : 'text-slate-900'}>
                        {formatIDR(l.amount)}
                      </span>
                    </div>
                  ))}
                  {data.financing_activities.lines.length === 0 && (
                    <div className="py-2 text-slate-400 pl-4 text-xs italic">Tidak ada mutasi kas pendanaan pada periode ini.</div>
                  )}
                </div>
              </div>

              {/* RECONCILIATION SUMMARY */}
              <div className="bg-slate-900 text-white p-4 rounded-lg space-y-2 text-xs font-mono">
                <div className="flex justify-between font-sans text-slate-300">
                  <span>Kenaikan / (Penurunan) Kas Bersih:</span>
                  <span className="font-mono font-bold text-white">{formatIDR(data.net_cash_change)}</span>
                </div>
                <div className="flex justify-between font-sans text-slate-300">
                  <span>Saldo Awal Kas & Bank:</span>
                  <span className="font-mono text-slate-200">{formatIDR(data.opening_cash_balance)}</span>
                </div>
                <div className="border-t border-slate-700 pt-2 flex justify-between text-sm font-bold">
                  <span className="font-sans text-emerald-400 uppercase tracking-wider">Saldo Akhir Kas & Bank:</span>
                  <span className="text-emerald-400 text-base">{formatIDR(data.closing_cash_balance)}</span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
};
