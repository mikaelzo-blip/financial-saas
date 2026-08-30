import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, AlertCircle } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { projectsApi } from '../../api/projects';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Select } from '../../components/ui/Select';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ProjectResponse } from '../../types/api';

export const ProjectCashPositionPage: React.FC = () => {
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  const { data: projectsList } = useQuery({
    queryKey: ['projects-list-cash-position'],
    queryFn: () => projectsApi.list(),
  });

  useEffect(() => {
    if (projectsList && projectsList.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projectsList[0].id);
    }
  }, [projectsList, selectedProjectId]);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['project-cash-position', selectedProjectId],
    queryFn: () => reportsApi.getProjectCashPosition(selectedProjectId),
    enabled: !!selectedProjectId,
  });

  const projectOptions = projectsList
    ? projectsList.map((p: ProjectResponse) => ({
        value: p.id,
        label: `${p.project_code} — ${p.project_name}`,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Posisi Kas Proyek (Project Cash Position)</h1>
          <p className="text-sm text-slate-500">
            Likuiditas riil proyek (Penerimaan Kas Riil vs Pengeluaran Kas Riil).
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => refetch()}
          disabled={isFetching || !selectedProjectId}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
          Perbarui
        </Button>
      </div>

      <Card className="p-4">
        <div className="max-w-md">
          <Select
            label="Pilih Proyek Kontraktor"
            options={projectOptions}
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
          />
        </div>
      </Card>

      {/* Distinction Alert Banner */}
      <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg flex items-start space-x-3 text-xs text-blue-900">
        <AlertCircle className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold">Prinsip Akuntansi Kontraktor:</span> Laba Proyek (Akrual) tidak sama dengan Posisi Kas Proyek (Likuiditas). Proyek yang membukukan laba dapat mengalami defisit kas apabila termin belum cair atau piutang belum tertagih.
        </div>
      </div>

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <Card className="p-4 bg-slate-50 border-slate-200">
              <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Total Ditagihkan</span>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                {formatIDR(data.invoiced_amount)}
              </div>
              <div className="text-[11px] text-amber-700 mt-1 font-mono">
                Sisa Piutang: {formatIDR(data.receivable_outstanding)}
              </div>
            </Card>
            <Card className="p-4 bg-emerald-50/60 border-emerald-200">
              <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Kas Masuk Riil (Inflow)</span>
              <div className="text-lg font-bold font-mono text-emerald-950 mt-1">
                {formatIDR(data.cash_received)}
              </div>
            </Card>
            <Card className="p-4 bg-rose-50/60 border-rose-200">
              <span className="text-xs font-semibold text-rose-800 uppercase tracking-wider">Kas Keluar Riil (Outflow)</span>
              <div className="text-lg font-bold font-mono text-rose-950 mt-1">
                {formatIDR(data.cash_spent)}
              </div>
            </Card>
            <Card className={`p-4 border ${data.is_surplus ? 'bg-emerald-100/60 border-emerald-300' : 'bg-rose-100/60 border-rose-300'}`}>
              <span className={`text-xs font-semibold uppercase tracking-wider ${data.is_surplus ? 'text-emerald-900' : 'text-rose-900'}`}>
                Posisi Kas Bersih (Net)
              </span>
              <div className={`text-xl font-bold font-mono mt-1 ${data.is_surplus ? 'text-emerald-950' : 'text-rose-950'}`}>
                {formatIDR(data.net_cash_position)}
              </div>
              <div className="text-[11px] font-semibold mt-1">
                Status: {data.is_surplus ? 'SURPLUS KAS' : 'DEFISIT KAS'}
              </div>
            </Card>
          </div>

          <Card className="p-6 space-y-4">
            <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wide border-b border-slate-200 pb-2">
              Rincian Arus Likuiditas Proyek: {data.project_code} — {data.project_name}
            </h3>
            <div className="divide-y divide-slate-100 text-xs font-mono">
              <div className="py-2.5 flex justify-between">
                <span className="font-sans text-slate-700">Total Penagihan Termin (Invoice Diterbitkan):</span>
                <span className="font-bold text-slate-900">{formatIDR(data.invoiced_amount)}</span>
              </div>
              <div className="py-2.5 flex justify-between">
                <span className="font-sans text-slate-700">Penerimaan Pembayaran Kas dari Pelanggan:</span>
                <span className="font-bold text-emerald-700">+{formatIDR(data.cash_received)}</span>
              </div>
              <div className="py-2.5 flex justify-between">
                <span className="font-sans text-slate-700">Pengeluaran Kas / Biaya Proyek Dibayar:</span>
                <span className="font-bold text-rose-700">-{formatIDR(data.cash_spent)}</span>
              </div>
              <div className="py-3 flex justify-between font-bold text-sm bg-slate-50 px-2 rounded">
                <span className="font-sans text-slate-900 uppercase">Posisi Kas Bersih Proyek:</span>
                <span className={data.is_surplus ? 'text-emerald-700' : 'text-rose-700'}>
                  {formatIDR(data.net_cash_position)}
                </span>
              </div>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
};
