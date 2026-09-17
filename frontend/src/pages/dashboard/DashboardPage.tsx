import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Wallet,
  ArrowDownLeft,
  ArrowUpRight,
  ShieldCheck,
  ShieldAlert,
  Scale,
  Sparkles,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { formatIDR } from '../../utils/formatters';
import { Card } from '../../components/ui/Card';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { ActionItemsSection } from './components/ActionItemsSection';
import { MonthlyCashFlowSection } from './components/MonthlyCashFlowSection';
import { CashFlowTrendChart } from './components/CashFlowTrendChart';
import { ProjectPerformanceChart } from './components/ProjectPerformanceChart';
import { AgingComparisonChart } from './components/AgingComparisonChart';
import { QuickActionsPanel } from './components/QuickActionsPanel';
import { RecentActivityTable } from './components/RecentActivityTable';
import { ExecutiveSummaryCard } from '../../components/ai/ExecutiveSummaryCard';
import { FinancialQABox } from '../../components/ai/FinancialQABox';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [aiSectionOpen, setAiSectionOpen] = useState(false);

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['dashboard-financial-summary'],
    queryFn: () => reportsApi.getDashboardSummary(),
  });

  const netLiquidityPosition = metrics
    ? Number(metrics.cash_and_bank_balance) +
      Number(metrics.accounts_receivable_outstanding) -
      Number(metrics.accounts_payable_outstanding)
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">
            Dashboard Keuangan & Operasional
          </h2>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Ringkasan posisi kas riil, piutang, utang, kinerja proyek, dan tindakan operasional harian.
          </p>
        </div>
        {metrics && (
          <div className="flex items-center gap-2">
            {metrics.integrity_status === 'VALID' ? (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                Integritas: SEIMBANG (Debet = Kredit)
              </span>
            ) : (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-300">
                <ShieldAlert className="w-3.5 h-3.5 mr-1 text-rose-600 animate-pulse" />
                PERINGATAN: NERACA TIDAK SEIMBANG
              </span>
            )}
          </div>
        )}
      </div>

      {/* SECTION A — PERLU TINDAKAN (Highest Priority) */}
      <ActionItemsSection />

      {/* SECTION B — POSISI KEUANGAN (Compact 4 Cards) */}
      <div className="space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Posisi Keuangan Utama
        </h3>
        {isLoading || !metrics ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <SkeletonLoader count={4} className="h-24 w-full" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Kas & Bank */}
            <Card
              className="p-4 bg-slate-900 text-white cursor-pointer hover:border-blue-500 transition-colors shadow-xs"
              onClick={() => navigate('/payment-accounts')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-400">Total Kas & Bank</span>
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-600/30 text-blue-400">
                  <Wallet className="h-3.5 w-3.5" />
                </div>
              </div>
              <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-white">
                {formatIDR(metrics.cash_and_bank_balance)}
              </p>
              <div className="text-[10px] text-slate-400 mt-1 flex items-center justify-between">
                <span>
                  {metrics.cash_runway_months !== null
                    ? `Runway: ${metrics.cash_runway_months} bln`
                    : 'Saldo likuid'}
                </span>
                <span className="text-blue-400 hover:underline">Detail &rarr;</span>
              </div>
            </Card>

            {/* 2. Piutang Usaha (AR) */}
            <Card
              className="p-4 bg-white border border-slate-200 cursor-pointer hover:border-blue-400 transition-colors shadow-xs"
              onClick={() => navigate('/receivables')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-500">Piutang Usaha (AR)</span>
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                  <ArrowDownLeft className="h-3.5 w-3.5" />
                </div>
              </div>
              <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-blue-700">
                {formatIDR(metrics.accounts_receivable_outstanding)}
              </p>
              <div className="text-[10px] text-slate-500 mt-1 flex items-center justify-between">
                <span>Tagihan belum tertagih</span>
                <span className="text-blue-600 hover:underline">Tagihan &rarr;</span>
              </div>
            </Card>

            {/* 3. Utang Usaha (AP) */}
            <Card
              className="p-4 bg-white border border-slate-200 cursor-pointer hover:border-rose-400 transition-colors shadow-xs"
              onClick={() => navigate('/payables')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-500">Utang Vendor (AP)</span>
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-rose-50 text-rose-600">
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </div>
              </div>
              <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-rose-700">
                {formatIDR(metrics.accounts_payable_outstanding)}
              </p>
              <div className="text-[10px] text-slate-500 mt-1 flex items-center justify-between">
                <span>Kewajiban vendor & subkon</span>
                <span className="text-rose-600 hover:underline">Tagihan &rarr;</span>
              </div>
            </Card>

            {/* 4. Posisi Bersih (Kas + AR - AP) */}
            <Card
              className="p-4 bg-white border border-slate-200 cursor-pointer hover:border-emerald-400 transition-colors shadow-xs"
              onClick={() => navigate('/reports/balance-sheet')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-500">Posisi Bersih Likuid</span>
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
                  <Scale className="h-3.5 w-3.5" />
                </div>
              </div>
              <p className={`text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 ${
                netLiquidityPosition >= 0 ? 'text-emerald-700' : 'text-rose-700'
              }`}>
                {formatIDR(netLiquidityPosition)}
              </p>
              <div className="text-[10px] text-slate-500 mt-1 flex items-center justify-between">
                <span>Likuiditas: Kas + AR - AP</span>
                <span className="text-emerald-600 hover:underline">Laporan &rarr;</span>
              </div>
            </Card>
          </div>
        )}
      </div>

      {/* SECTION C — ARUS KAS BULAN INI (Compact Cash In, Cash Out, Net) */}
      <MonthlyCashFlowSection />

      {/* SECTION D — GRAFIK KEPUTUSAN BISNIS (Exactly 3 Real Business Charts) */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Grafik Keputusan Bisnis
        </h3>

        {/* Top Charts Row: Arus Kas & Aging */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <CashFlowTrendChart />
          <AgingComparisonChart />
        </div>

        {/* Bottom Chart: Kinerja Proyek */}
        <div>
          <ProjectPerformanceChart />
        </div>
      </div>

      {/* SECTION D — QUICK ACTIONS & RECENT ACTIVITY */}
      <QuickActionsPanel reviewCount={metrics?.review_queue_pending_count || 0} />
      <RecentActivityTable />

      {/* SECTION E — COLLAPSIBLE AI ADVISORY SECTION */}
      <Card className="p-4 border border-slate-200 bg-slate-50/50">
        <div
          onClick={() => setAiSectionOpen(!aiSectionOpen)}
          className="flex items-center justify-between cursor-pointer select-none"
        >
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h4 className="text-xs md:text-sm font-bold text-slate-900">
                Wawasan & Asisten Keuangan AI (Advisory)
              </h4>
              <p className="text-[11px] text-slate-500">
                Ringkasan eksekutif, analisis tren, dan tanya-jawab keuangan otomatis
              </p>
            </div>
          </div>
          <button
            className="flex items-center gap-1 text-xs text-indigo-600 font-semibold hover:text-indigo-800"
            aria-label={aiSectionOpen ? 'Tutup Analisis AI' : 'Buka Analisis AI'}
          >
            <span>{aiSectionOpen ? 'Sembunyikan' : 'Buka Analisis'}</span>
            {aiSectionOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>

        {aiSectionOpen && (
          <div className="mt-4 pt-4 border-t border-slate-200 space-y-4">
            <ExecutiveSummaryCard />
            <FinancialQABox />
          </div>
        )}
      </Card>
    </div>
  );
};
