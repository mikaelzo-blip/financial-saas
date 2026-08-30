import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ReportHeader } from '../../components/reports/ReportHeader';

export const ProfitLossPage: React.FC = () => {
  const navigate = useNavigate();
  const today = new Date().toISOString().split('T')[0];
  const firstDayOfMonth = `${today.substring(0, 7)}-01`;

  const [startDate, setStartDate] = useState<string>(firstDayOfMonth);
  const [endDate, setEndDate] = useState<string>(today);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['profit-loss', startDate, endDate],
    queryFn: () => reportsApi.getProfitLoss(startDate, endDate),
  });

  const openLedger = (accountCode?: string | null) => {
    if (!accountCode) return;
    const query = new URLSearchParams({ account_code: accountCode, start_date: startDate, end_date: endDate });
    navigate(`/reports/general-ledger?${query.toString()}`);
  };

  const lineClass = (accountCode?: string | null) =>
    `w-full py-2 flex justify-between text-slate-700 ${accountCode ? 'hover:bg-indigo-50 cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-500' : ''}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Laporan Laba Rugi (Profit & Loss)</h1>
          <p className="text-sm text-slate-500">
            Kinerja keuangan operasional dan laba bersih standar SAK Kontraktor.
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
            Hitung Ulang
          </Button>
          <ReportHeader reportType="profit-loss" params={{ start_date: startDate, end_date: endDate }} disabled={!data} />
        </div>
      </div>

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          {/* Header Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="p-4 bg-emerald-50/60 border-emerald-200">
              <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Total Pendapatan</span>
              <div className="text-xl font-bold font-mono text-emerald-950 mt-1">
                {formatIDR(data.revenue_section.subtotal)}
              </div>
            </Card>
            <Card className="p-4 bg-indigo-50/60 border-indigo-200">
              <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider">Laba Kotor (Gross Profit)</span>
              <div className="text-xl font-bold font-mono text-indigo-950 mt-1 flex items-baseline justify-between">
                <span>{formatIDR(data.gross_profit)}</span>
                <span className="text-xs font-normal text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded">
                  Margin: {data.gross_margin_percentage}%
                </span>
              </div>
            </Card>
            <Card className="p-4 bg-blue-50/60 border-blue-200">
              <span className="text-xs font-semibold text-blue-800 uppercase tracking-wider">Laba Bersih (Net Profit)</span>
              <div className="text-xl font-bold font-mono text-blue-950 mt-1">
                {formatIDR(data.net_profit)}
              </div>
            </Card>
          </div>

          {/* Statement Sheet */}
          <Card className="overflow-hidden p-0">
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center text-xs text-slate-600">
              <span>Entitas: <strong className="text-slate-900">{data.organization_name}</strong></span>
              <span>Periode: <strong className="text-slate-900">{data.period_label}</strong></span>
            </div>

            <div className="p-6 space-y-6 text-sm">
              {/* 1. PENDAPATAN */}
              <div>
                <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                  <span>I. PENDAPATAN USAHA</span>
                  <span className="font-mono">{formatIDR(data.revenue_section.subtotal)}</span>
                </h3>
                <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                  {data.revenue_section.lines.map((l) => (
                    <button type="button" key={l.account_code || l.line_name} className={lineClass(l.account_code)} onClick={() => openLedger(l.account_code)} disabled={!l.account_code}>
                      <span className="font-sans text-slate-800 pl-4">{l.account_code} — {l.line_name}</span>
                      <span>{formatIDR(l.amount)}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* 2. HPP */}
              <div>
                <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                  <span>II. HARGA POKOK PROYEK (HPP)</span>
                  <span className="font-mono text-red-700">({formatIDR(data.cogs_section.subtotal)})</span>
                </h3>
                <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                  {data.cogs_section.lines.map((l) => (
                    <button type="button" key={l.account_code || l.line_name} className={lineClass(l.account_code)} onClick={() => openLedger(l.account_code)} disabled={!l.account_code}>
                      <span className="font-sans text-slate-800 pl-4">{l.account_code} — {l.line_name}</span>
                      <span>{formatIDR(l.amount)}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* LABA KOTOR SUB-BAR */}
              <div className="bg-slate-100 p-3 rounded flex justify-between font-bold text-slate-900">
                <span>LABA KOTOR (GROSS PROFIT):</span>
                <span className="font-mono text-emerald-800">{formatIDR(data.gross_profit)}</span>
              </div>

              {/* 3. BEBAN OPERASIONAL */}
              <div>
                <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                  <span>III. BEBAN OPERASIONAL KANTOR</span>
                  <span className="font-mono text-red-700">({formatIDR(data.operating_expenses_section.subtotal)})</span>
                </h3>
                <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                  {data.operating_expenses_section.lines.map((l) => (
                    <button type="button" key={l.account_code || l.line_name} className={lineClass(l.account_code)} onClick={() => openLedger(l.account_code)} disabled={!l.account_code}>
                      <span className="font-sans text-slate-800 pl-4">{l.account_code} — {l.line_name}</span>
                      <span>{formatIDR(l.amount)}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* LABA USAHA SUB-BAR */}
              <div className="bg-slate-100 p-3 rounded flex justify-between font-bold text-slate-900">
                <span>LABA USAHA (OPERATING PROFIT):</span>
                <span className="font-mono text-indigo-900">{formatIDR(data.operating_profit)}</span>
              </div>

              {/* 4. PENDAPATAN / BEBAN LAIN */}
              {data.other_income_expense_section.lines.length > 0 && (
                <div>
                  <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wide border-b border-slate-200 pb-2 flex justify-between">
                    <span>IV. PENDAPATAN / (BEBAN) LAIN-LAIN</span>
                    <span className="font-mono">{formatIDR(data.other_income_expense_section.subtotal)}</span>
                  </h3>
                  <div className="divide-y divide-slate-100 text-xs font-mono mt-2">
                    {data.other_income_expense_section.lines.map((l) => (
                      <button type="button" key={l.account_code || l.line_name} className={lineClass(l.account_code)} onClick={() => openLedger(l.account_code)} disabled={!l.account_code}>
                        <span className="font-sans text-slate-800 pl-4">{l.account_code} — {l.line_name}</span>
                        <span>{formatIDR(l.amount)}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* FINAL NET PROFIT BAR */}
              <div className="bg-slate-900 text-white p-4 rounded-lg flex justify-between items-center font-bold">
                <span className="text-base uppercase tracking-wider">LABA BERSIH TAHUN/PERIODE BERJALAN:</span>
                <span className="text-xl font-mono text-emerald-400">{formatIDR(data.net_profit)}</span>
              </div>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
};
