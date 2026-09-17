import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Building2, TrendingUp, Wallet, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { projectsApi } from '../../api/projects';
import { reportsApi } from '../../api/reports';
import { ProjectStatus } from '../../types/api';
import { formatIDR } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Card } from '../../components/ui/Card';
import { DataTable, Column } from '../../components/tables/DataTable';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';

interface EnrichedProjectRow {
  id: string;
  project_code: string;
  project_name: string;
  customer_name?: string | null;
  po_spk_no?: string | null;
  contract_value: number | string;
  actual_cost: number | string;
  invoiced_amount: number | string;
  cash_received: number | string;
  gross_profit: number | string;
  gross_margin_percentage: number | string;
  financial_progress_percentage: number | string;
  project_status: ProjectStatus;
  health_status: 'NORMAL' | 'WARNING' | 'CRITICAL';
}

export const ProjectListPage: React.FC = () => {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | ''>('');

  const { data: rawProjects = [], isLoading: isProjectsLoading } = useQuery({
    queryKey: ['projects', statusFilter],
    queryFn: () => projectsApi.list(statusFilter || undefined),
  });

  const { data: perfData, isLoading: isPerfLoading } = useQuery({
    queryKey: ['projects-performance-summary', statusFilter],
    queryFn: () => reportsApi.getProjectPerformance(statusFilter || undefined),
  });

  const isLoading = isProjectsLoading || isPerfLoading;

  // Build map of performance items by project id or code
  const perfMap = React.useMemo(() => {
    const map = new Map<string, any>();
    if (perfData?.items) {
      for (const item of perfData.items) {
        map.set(item.project_id, item);
        map.set(item.project_code, item);
      }
    }
    return map;
  }, [perfData]);

  // Combine projects master with real financial performance
  const rows: EnrichedProjectRow[] = React.useMemo(() => {
    if (!rawProjects.length && perfData?.items.length) {
      return perfData.items.map((item) => ({
        id: item.project_id,
        project_code: item.project_code,
        project_name: item.project_name,
        customer_name: item.customer_name,
        po_spk_no: null,
        contract_value: item.contract_value,
        actual_cost: item.actual_cost,
        invoiced_amount: item.invoiced_amount,
        cash_received: item.cash_received,
        gross_profit: item.gross_profit,
        gross_margin_percentage: item.gross_margin_percentage,
        financial_progress_percentage: item.financial_progress_percentage,
        project_status: item.status as ProjectStatus,
        health_status: item.health_status,
      }));
    }

    return rawProjects.map((p) => {
      const perf = perfMap.get(p.id) || perfMap.get(p.project_code);
      const contract = perf ? perf.contract_value : p.revised_contract_value;
      const cost = perf ? perf.actual_cost : '0.00';
      const invoiced = perf ? perf.invoiced_amount : '0.00';
      const cash = perf ? perf.cash_received : '0.00';
      const gp = perf ? perf.gross_profit : Number(contract) - Number(cost);
      const marginPct = perf
        ? perf.gross_margin_percentage
        : Number(contract) > 0
        ? ((Number(gp) / Number(contract)) * 100).toFixed(1)
        : '0.0';
      const progressPct = perf
        ? perf.financial_progress_percentage
        : Number(contract) > 0
        ? ((Number(cost) / Number(contract)) * 100).toFixed(1)
        : '0.0';

      return {
        id: p.id,
        project_code: p.project_code,
        project_name: p.project_name,
        customer_name: perf?.customer_name || null,
        po_spk_no: p.po_spk_no,
        contract_value: contract,
        actual_cost: cost,
        invoiced_amount: invoiced,
        cash_received: cash,
        gross_profit: gp,
        gross_margin_percentage: marginPct,
        financial_progress_percentage: progressPct,
        project_status: p.project_status,
        health_status: perf?.health_status || 'NORMAL',
      };
    });
  }, [rawProjects, perfData, perfMap]);

  const totalContract = perfData ? perfData.total_contract_value : '0.00';
  const totalCost = perfData ? perfData.total_actual_cost : '0.00';
  const totalGp = Number(totalContract) - Number(totalCost);
  const avgMargin = perfData ? perfData.average_margin_percentage : '0.0';
  const activeCount = perfData
    ? perfData.total_active_projects
    : rawProjects.filter((p) => p.project_status === 'ACTIVE').length;

  const columns: Column<EnrichedProjectRow>[] = [
    {
      key: 'project_name',
      header: 'Nama Proyek',
      sortable: true,
      render: (p) => (
        <div>
          <p className="font-semibold text-slate-900 hover:text-blue-600 transition-colors">
            {p.project_name}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs font-mono text-slate-500">{p.project_code}</span>
            {p.po_spk_no && (
              <span className="text-[11px] text-slate-400">PO: {p.po_spk_no}</span>
            )}
          </div>
        </div>
      ),
    },
    {
      key: 'customer_name',
      header: 'Klien / Pelanggan',
      sortable: true,
      render: (p) => (
        <span className="text-xs text-slate-700 font-medium">
          {p.customer_name || '-'}
        </span>
      ),
    },
    {
      key: 'contract_value',
      header: 'Nilai Kontrak',
      sortable: true,
      align: 'right',
      render: (p) => (
        <span className="font-semibold text-slate-900 font-mono tabular-nums text-xs md:text-sm">
          {formatIDR(p.contract_value)}
        </span>
      ),
    },
    {
      key: 'actual_cost',
      header: 'Biaya Aktual',
      sortable: true,
      align: 'right',
      render: (p) => (
        <div className="text-right">
          <p className="font-medium text-slate-800 font-mono tabular-nums text-xs md:text-sm">
            {formatIDR(p.actual_cost)}
          </p>
          <p className="text-[10px] text-slate-400">
            Progres: {p.financial_progress_percentage}%
          </p>
        </div>
      ),
    },
    {
      key: 'billing',
      header: 'Tagihan & Terbayar',
      align: 'right',
      render: (p) => (
        <div className="text-right space-y-0.5">
          <p className="text-xs font-mono tabular-nums text-blue-700">
            Tagihan: {formatIDR(p.invoiced_amount)}
          </p>
          <p className="text-[10px] font-mono tabular-nums text-emerald-600">
            Masuk: {formatIDR(p.cash_received)}
          </p>
        </div>
      ),
    },
    {
      key: 'margin',
      header: 'Gross Margin',
      sortable: true,
      align: 'right',
      render: (p) => {
        const marginNum = Number(p.gross_margin_percentage);
        let badgeColor = 'bg-emerald-50 text-emerald-700 border-emerald-200';
        if (p.health_status === 'CRITICAL' || marginNum < 0) {
          badgeColor = 'bg-rose-50 text-rose-700 border-rose-200';
        } else if (p.health_status === 'WARNING' || marginNum < 15) {
          badgeColor = 'bg-amber-50 text-amber-700 border-amber-200';
        }

        return (
          <div className="text-right">
            <p className="font-mono tabular-nums text-xs text-slate-900 font-medium">
              {formatIDR(p.gross_profit)}
            </p>
            <span className={`inline-block mt-0.5 px-2 py-0.5 text-[10px] font-semibold rounded-full border ${badgeColor}`}>
              {p.gross_margin_percentage}%
            </span>
          </div>
        );
      },
    },
    {
      key: 'project_status',
      header: 'Status',
      align: 'center',
      render: (p) => <StatusBadge status={p.project_status} size="sm" />,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">
            Daftar & Kinerja Proyek
          </h2>
          <p className="text-xs md:text-sm text-slate-500 mt-1">
            Monitoring kontrak, realisasi biaya lapangan, tagihan, dan profitabilitas per proyek.
          </p>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => navigate('/projects/new')}
        >
          Tambah Proyek Baru
        </Button>
      </div>

      {/* Top Financial Summary Cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SkeletonLoader count={4} className="h-24 w-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Proyek Aktif */}
          <Card className="p-4 bg-white border border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Proyek Aktif</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-blue-600">
                <Building2 className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-slate-900">
              {activeCount} Proyek
            </p>
            <p className="text-[10px] text-slate-400 mt-1">Berjalan di lapangan</p>
          </Card>

          {/* Total Nilai Kontrak */}
          <Card className="p-4 bg-white border border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Total Nilai Kontrak</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
                <TrendingUp className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-emerald-700">
              {formatIDR(totalContract)}
            </p>
            <p className="text-[10px] text-slate-400 mt-1">Akumulasi kontrak proyek</p>
          </Card>

          {/* Total Biaya Aktual */}
          <Card className="p-4 bg-white border border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Total Biaya Aktual</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-50 text-amber-600">
                <Wallet className="h-3.5 w-3.5" />
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-amber-800">
              {formatIDR(totalCost)}
            </p>
            <p className="text-[10px] text-slate-400 mt-1">Realisasi biaya langsung</p>
          </Card>

          {/* Gross Profit / Average Margin */}
          <Card className="p-4 bg-white border border-slate-200 shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Laba Kotor & Margin</span>
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-indigo-50 text-indigo-600">
                {Number(avgMargin) >= 15 ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
              </div>
            </div>
            <p className="text-lg md:text-xl font-bold font-mono tabular-nums mt-1.5 text-indigo-700">
              {formatIDR(totalGp)}
            </p>
            <p className="text-[10px] text-slate-500 mt-1">
              Rata-rata Margin: <span className="font-semibold">{avgMargin}%</span>
            </p>
          </Card>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-slate-200 pb-2">
        {[
          { label: 'Semua Proyek', value: '' },
          { label: 'Aktif', value: 'ACTIVE' },
          { label: 'Direncanakan', value: 'PLANNED' },
          { label: 'Selesai', value: 'COMPLETED' },
          { label: 'Ditunda', value: 'ON_HOLD' },
        ].map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value as any)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
              statusFilter === tab.value
                ? 'bg-blue-600 text-white shadow-xs font-semibold'
                : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Data Table */}
      <DataTable
        columns={columns}
        data={rows}
        keyExtractor={(p) => p.id}
        isLoading={isLoading}
        searchPlaceholder="Cari nama proyek, kode, atau klien..."
        searchKeys={['project_name', 'project_code', 'customer_name']}
        emptyTitle="Belum ada proyek"
        emptyDescription="Tambahkan proyek baru untuk mulai memantau kontrak dan biaya konstruksi."
        emptyAction={
          <Button
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => navigate('/projects/new')}
          >
            Tambah Proyek Sekarang
          </Button>
        }
        onRowClick={(p) => navigate(`/projects/${p.id}`)}
      />
    </div>
  );
};
