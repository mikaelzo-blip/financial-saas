import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Wallet,
  Building2,
  ArrowDownLeft,
  ArrowUpRight,
  AlertTriangle,
  TrendingUp,
  Flame,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { formatIDR } from '../../utils/formatters';
import { Card } from '../../components/ui/Card';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { QuickActionsPanel } from './components/QuickActionsPanel';
import { RecentActivityTable } from './components/RecentActivityTable';
import { ExecutiveSummaryCard } from '../../components/ai/ExecutiveSummaryCard';
import { FinancialQABox } from '../../components/ai/FinancialQABox';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['dashboard-financial-summary'],
    queryFn: () => reportsApi.getDashboardSummary(),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Dashboard Manajemen & Keuangan
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Ringkasan posisi kas riil, runway, pendapatan YTD, piutang (AR), utang (AP), dan integritas pembukuan.
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

      {/* Metric Cards Grid */}
      {isLoading || !metrics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SkeletonLoader count={4} className="h-28 w-full" />
        </div>
      ) : (
        <div className="space-y-4">
          {/* Row 1: Core Financial KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Kas & Bank */}
            <Card
              className="p-4 bg-slate-900 text-white cursor-pointer hover:border-blue-500 transition-colors"
              onClick={() => navigate('/reports/general-ledger')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-400">Total Kas & Bank</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600/30 text-blue-400">
                  <Wallet className="h-4 w-4" />
                </div>
              </div>
              <p className="text-xl font-bold font-mono tabular-nums mt-2 text-white">
                {formatIDR(metrics.cash_and_bank_balance)}
              </p>
              <p className="text-[10px] text-slate-400 mt-1 flex items-center justify-between">
                <span>Saldo likuid riil</span>
                <span className="text-blue-400 underline">Buka Buku Besar &rarr;</span>
              </p>
            </Card>

            {/* Cash Runway */}
            <Card className="p-4 bg-amber-50/60 border-amber-200">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-amber-800">Estimasi Cash Runway</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
                  <Flame className="h-4 w-4" />
                </div>
              </div>
              <p className="text-xl font-bold font-mono tabular-nums mt-2 text-amber-950">
                {metrics.cash_runway_months !== null ? `${metrics.cash_runway_months} Bulan` : 'N/A'}
              </p>
              <p className="text-[10px] text-amber-700 mt-1">
                Burn rate: {formatIDR(metrics.estimated_monthly_burn_rate)} / bln
              </p>
            </Card>

            {/* Pendapatan YTD */}
            <Card
              className="p-4 bg-emerald-50/60 border-emerald-200 cursor-pointer hover:border-emerald-500 transition-colors"
              onClick={() => navigate('/reports/profit-loss')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-emerald-800">Pendapatan YTD</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
                  <TrendingUp className="h-4 w-4" />
                </div>
              </div>
              <p className="text-xl font-bold font-mono tabular-nums mt-2 text-emerald-950">
                {formatIDR(metrics.revenue_ytd)}
              </p>
              <p className="text-[10px] text-emerald-700 mt-1 flex items-center justify-between">
                <span>Laba Bersih: {formatIDR(metrics.net_profit_ytd)}</span>
                <span className="underline">P&L &rarr;</span>
              </p>
            </Card>

            {/* Proyek Aktif */}
            <Card
              className="p-4 cursor-pointer hover:border-slate-400 transition-colors"
              onClick={() => navigate('/projects')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-500">Proyek Aktif</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                  <Building2 className="h-4 w-4" />
                </div>
              </div>
              <p className="text-xl font-bold font-mono tabular-nums mt-2 text-slate-900">
                {metrics.active_projects_count} Proyek
              </p>
              <p className="text-[10px] text-slate-400 mt-1 flex items-center justify-between">
                <span>Berjalan di lapangan</span>
                <span className="text-blue-600 underline">Lihat Proyek &rarr;</span>
              </p>
            </Card>
          </div>

          {/* Row 2: Sub-ledgers AR, AP, Review Queue */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Piutang Usaha (AR) */}
            <Card
              className="p-4 cursor-pointer hover:border-blue-400 transition-colors"
              onClick={() => navigate('/reports/ar-aging')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-500">Piutang Usaha (AR)</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                  <ArrowDownLeft className="h-4 w-4" />
                </div>
              </div>
              <p className="text-lg font-bold font-mono tabular-nums mt-2 text-blue-600">
                {formatIDR(metrics.accounts_receivable_outstanding)}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">Tagihan belum tertagih &bull; Buka Umur Piutang &rarr;</p>
            </Card>

            {/* Utang Usaha (AP) */}
            <Card
              className="p-4 cursor-pointer hover:border-rose-400 transition-colors"
              onClick={() => navigate('/reports/ap-aging')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-500">Utang Usaha (AP)</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-50 text-rose-600">
                  <ArrowUpRight className="h-4 w-4" />
                </div>
              </div>
              <p className="text-lg font-bold font-mono tabular-nums mt-2 text-rose-600">
                {formatIDR(metrics.accounts_payable_outstanding)}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">Kewajiban tagihan vendor &bull; Buka Umur Utang &rarr;</p>
            </Card>

            {/* Antrean Review */}
            <Card
              className="p-4 cursor-pointer hover:border-amber-400 transition-colors"
              onClick={() => navigate('/review-queue')}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase text-slate-500">Antrean Review</span>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                  <AlertTriangle className="h-4 w-4" />
                </div>
              </div>
              <p className="text-lg font-bold font-mono tabular-nums mt-2 text-amber-600">
                {metrics.review_queue_pending_count} Item Menunggu
              </p>
              <p className="text-[10px] text-slate-400 mt-1">Butuh tindakan resolusi &rarr;</p>
            </Card>
          </div>
        </div>
      )}

      {/* Quick Actions Panel */}
      <ExecutiveSummaryCard />
      <FinancialQABox />
      <QuickActionsPanel reviewCount={metrics?.review_queue_pending_count || 0} />

      {/* Recent Activity */}
      <RecentActivityTable />
    </div>
  );
};
