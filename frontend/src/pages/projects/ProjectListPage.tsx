import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Building2 } from 'lucide-react';
import { projectsApi } from '../../api/projects';
import { ProjectResponse, ProjectStatus } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { DataTable, Column } from '../../components/tables/DataTable';

export const ProjectListPage: React.FC = () => {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | ''>('');

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects', statusFilter],
    queryFn: () => projectsApi.list(statusFilter || undefined),
  });

  const columns: Column<ProjectResponse>[] = [
    {
      key: 'project_code',
      header: 'Kode Proyek',
      sortable: true,
      render: (p) => (
        <span className="font-semibold text-blue-600 font-mono text-xs">
          {p.project_code}
        </span>
      ),
    },
    {
      key: 'project_name',
      header: 'Nama Proyek',
      sortable: true,
      render: (p) => (
        <div>
          <p className="font-medium text-slate-900">{p.project_name}</p>
          {p.po_spk_no && <p className="text-[11px] text-slate-400">PO: {p.po_spk_no}</p>}
        </div>
      ),
    },
    {
      key: 'revised_contract_value',
      header: 'Nilai Kontrak',
      sortable: true,
      align: 'right',
      render: (p) => (
        <div className="text-right">
          <p className="font-semibold text-slate-900 font-mono tabular-nums">
            {formatIDR(p.revised_contract_value)}
          </p>
          {Number(p.variation_order_value) > 0 && (
            <p className="text-[10px] text-emerald-600 font-medium">
              + VO: {formatIDR(p.variation_order_value)}
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'start_date',
      header: 'Mulai',
      sortable: true,
      render: (p) => <span className="text-xs text-slate-600">{formatDate(p.start_date)}</span>,
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
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Daftar Proyek</h2>
          <p className="text-xs text-slate-500 mt-1">
            Kelola data master proyek, nilai kontrak, dan progres biaya konstruksi.
          </p>
        </div>
        <Button
          leftIcon={<Plus className="h-4 w-4" />}
          onClick={() => navigate('/projects/new')}
        >
          Tambah Proyek Baru
        </Button>
      </div>

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
                ? 'bg-blue-600 text-white shadow-xs'
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
        data={projects}
        keyExtractor={(p) => p.id}
        isLoading={isLoading}
        searchPlaceholder="Cari kode atau nama proyek..."
        searchKeys={['project_code', 'project_name', 'po_spk_no']}
        emptyTitle="Belum ada proyek terdaftar"
        emptyDescription="Mulai dengan menambahkan proyek konstruksi baru untuk mengorganisir anggaran dan biaya."
        emptyAction={
          <Button
            size="sm"
            leftIcon={<Building2 className="h-4 w-4" />}
            onClick={() => navigate('/projects/new')}
          >
            Buat Proyek Pertama
          </Button>
        }
        onRowClick={(p) => navigate(`/projects/${p.id}`)}
      />
    </div>
  );
};
