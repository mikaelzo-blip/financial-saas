import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Calendar, FileText, CheckCircle2 } from 'lucide-react';
import { projectsApi } from '../../api/projects';
import { ProjectStatus } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { useToast } from '../../components/feedback/Toast';
import { ProjectProfitabilityTab } from './components/ProjectProfitabilityTab';

export const ProjectDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { success, error } = useToast();
  const [activeTab, setActiveTab] = useState<'overview' | 'profitability'>('profitability');

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => projectsApi.get(id!),
    enabled: !!id,
  });

  const statusMutation = useMutation({
    mutationFn: (newStatus: ProjectStatus) => projectsApi.updateStatus(id!, newStatus),
    onSuccess: (updated) => {
      queryClient.setQueryData(['project', id], updated);
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      success(`Status proyek berhasil diubah ke ${updated.project_status}.`);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Gagal mengubah status proyek.');
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <SkeletonLoader count={1} className="h-8 w-64" />
        <SkeletonLoader count={4} className="h-32 w-full" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center p-12">
        <p className="text-sm text-slate-500">Proyek tidak ditemukan.</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => navigate('/projects')}>
          Kembali ke Daftar Proyek
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/projects')}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-200/60 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-2.5">
              <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
                {project.project_code}
              </span>
              <h2 className="text-xl font-bold text-slate-900 tracking-tight">
                {project.project_name}
              </h2>
              <StatusBadge status={project.project_status} />
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Pelanggan: <span className="font-semibold text-slate-700">{project.customer_name || 'PT Pemberi Tugas'}</span>
            </p>
          </div>
        </div>

        {/* Status Actions */}
        <div className="flex items-center gap-2">
          {project.project_status === 'PLANNED' && (
            <Button
              size="sm"
              variant="success"
              leftIcon={<CheckCircle2 className="h-4 w-4" />}
              onClick={() => statusMutation.mutate('ACTIVE')}
              isLoading={statusMutation.isPending}
            >
              Mulai Proyek (Aktifkan)
            </Button>
          )}
          {project.project_status === 'ACTIVE' && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => statusMutation.mutate('COMPLETED')}
              isLoading={statusMutation.isPending}
            >
              Tandai Selesai
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-6">
        <button
          onClick={() => setActiveTab('profitability')}
          className={`pb-3 text-xs font-semibold tracking-wide uppercase transition-colors cursor-pointer ${
            activeTab === 'profitability'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          Biaya & Profitabilitas
        </button>
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-3 text-xs font-semibold tracking-wide uppercase transition-colors cursor-pointer ${
            activeTab === 'overview'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          Informasi Kontrak
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'profitability' ? (
        <ProjectProfitabilityTab projectId={project.id} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card title="Rincian Nilai Kontrak">
            <dl className="divide-y divide-slate-100 text-xs">
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Nilai Kontrak Awal</dt>
                <dd className="font-semibold font-mono text-slate-900">
                  {formatIDR(project.original_contract_value)}
                </dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Variation Order (VO) Disetujui</dt>
                <dd className="font-semibold font-mono text-emerald-600">
                  {formatIDR(project.variation_order_value)}
                </dd>
              </div>
              <div className="flex justify-between py-2.5 font-bold text-sm bg-slate-50 px-2 rounded-md">
                <dt className="text-slate-900">Total Nilai Kontrak Revisi</dt>
                <dd className="font-mono text-blue-600">
                  {formatIDR(project.revised_contract_value)}
                </dd>
              </div>
            </dl>
          </Card>

          <Card title="Jadwal & Dokumen Kontrak">
            <dl className="divide-y divide-slate-100 text-xs">
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5" /> Nomor PO / SPK
                </dt>
                <dd className="font-medium text-slate-900">{project.po_spk_no || '-'}</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" /> Tanggal Mulai
                </dt>
                <dd className="font-medium text-slate-900">{formatDate(project.start_date)}</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500 flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" /> Target Selesai
                </dt>
                <dd className="font-medium text-slate-900">{formatDate(project.target_end_date)}</dd>
              </div>
            </dl>
          </Card>
        </div>
      )}
    </div>
  );
};
