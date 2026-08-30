import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { IntegrityAlertBanner } from '../../components/reports/IntegrityAlertBanner';
import { formatIDR } from '../../utils/formatters';
import { ReportHeader } from '../../components/reports/ReportHeader';

export const BalanceSheetPage: React.FC = () => {
  const today = new Date().toISOString().split('T')[0];
  const [asOfDate, setAsOfDate] = useState<string>(today);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['balance-sheet', asOfDate],
    queryFn: () => reportsApi.getBalanceSheet(asOfDate),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Laporan Neraca (Balance Sheet)</h1>
          <p className="text-sm text-slate-500">
            Posisi aset, kewajiban, dan ekuitas perusahaan per tanggal penutupan.
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
          <ReportHeader reportType="balance-sheet" params={{ as_of_date: asOfDate }} disabled={!data || !data.is_balanced} />
        </div>
      </div>

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          <IntegrityAlertBanner
            isBalanced={data.is_balanced}
            difference={data.balancing_difference}
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* SISI KIRI: ASET */}
            <div className="space-y-6">
              <Card className="overflow-hidden p-0 border-t-4 border-t-emerald-600">
                <div className="p-4 bg-slate-50 border-b border-slate-200">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">Aset (Aktiva)</h2>
                </div>
                <div className="p-6 space-y-6 text-sm">
                  {/* ASET LANCAR */}
                  <div>
                    <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                      <span>ASET LANCAR</span>
                      <span className="font-mono text-emerald-800">{formatIDR(data.current_assets.subtotal)}</span>
                    </h3>
                    <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                      {data.current_assets.lines.map((l) => (
                        <div key={l.account_code || l.line_name} className="py-2 flex justify-between text-slate-700">
                          <span className="font-sans text-slate-800 pl-2">{l.account_code} — {l.line_name}</span>
                          <span>{formatIDR(l.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* ASET TETAP */}
                  <div>
                    <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                      <span>ASET TETAP</span>
                      <span className="font-mono text-emerald-800">{formatIDR(data.fixed_assets.subtotal)}</span>
                    </h3>
                    <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                      {data.fixed_assets.lines.map((l) => (
                        <div key={l.account_code || l.line_name} className="py-2 flex justify-between text-slate-700">
                          <span className="font-sans text-slate-800 pl-2">{l.account_code} — {l.line_name}</span>
                          <span>{formatIDR(l.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* TOTAL ASET */}
                  <div className="bg-emerald-50 border border-emerald-200 p-4 rounded-lg flex justify-between items-center font-bold text-emerald-950">
                    <span className="text-xs uppercase tracking-wider">TOTAL ASET:</span>
                    <span className="text-lg font-mono">{formatIDR(data.total_assets)}</span>
                  </div>
                </div>
              </Card>
            </div>

            {/* SISI KANAN: KEWAJIBAN & EKUITAS */}
            <div className="space-y-6">
              <Card className="overflow-hidden p-0 border-t-4 border-t-indigo-600">
                <div className="p-4 bg-slate-50 border-b border-slate-200">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">Kewajiban & Ekuitas (Pasiva)</h2>
                </div>
                <div className="p-6 space-y-6 text-sm">
                  {/* KEWAJIBAN */}
                  <div>
                    <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                      <span>KEWAJIBAN JANGKA PENDEK</span>
                      <span className="font-mono text-indigo-900">{formatIDR(data.current_liabilities.subtotal)}</span>
                    </h3>
                    <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                      {data.current_liabilities.lines.map((l) => (
                        <div key={l.account_code || l.line_name} className="py-2 flex justify-between text-slate-700">
                          <span className="font-sans text-slate-800 pl-2">{l.account_code} — {l.line_name}</span>
                          <span>{formatIDR(l.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* EKUITAS */}
                  <div>
                    <h3 className="font-bold text-slate-900 text-xs uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                      <span>EKUITAS</span>
                      <span className="font-mono text-indigo-900">{formatIDR(data.equity.subtotal)}</span>
                    </h3>
                    <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                      {data.equity.lines.map((l) => (
                        <div key={l.account_code || l.line_name} className="py-2 flex justify-between text-slate-700">
                          <span className="font-sans text-slate-800 pl-2">{l.account_code} — {l.line_name}</span>
                          <span>{formatIDR(l.amount)}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* TOTAL KEWAJIBAN + EKUITAS */}
                  <div className="bg-indigo-50 border border-indigo-200 p-4 rounded-lg flex justify-between items-center font-bold text-indigo-950">
                    <span className="text-xs uppercase tracking-wider">TOTAL KEWAJIBAN + EKUITAS:</span>
                    <span className="text-lg font-mono">{formatIDR(data.total_liabilities_and_equity)}</span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
