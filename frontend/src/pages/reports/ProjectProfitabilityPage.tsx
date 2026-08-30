import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { projectsApi } from '../../api/projects';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Select } from '../../components/ui/Select';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ProjectResponse } from '../../types/api';
import { ReportHeader } from '../../components/reports/ReportHeader';

export const ProjectProfitabilityPage: React.FC = () => {
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  const { data: projectsList } = useQuery({
    queryKey: ['projects-list-reporting'],
    queryFn: () => projectsApi.list(),
  });

  useEffect(() => {
    if (projectsList && projectsList.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projectsList[0].id);
    }
  }, [projectsList, selectedProjectId]);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['project-profitability', selectedProjectId],
    queryFn: () => reportsApi.getProjectProfitability(selectedProjectId),
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
          <h1 className="text-2xl font-bold text-slate-900">Profitabilitas Proyek (Project P&L)</h1>
          <p className="text-sm text-slate-500">
            Analisis laba rugi berbasis akrual (Revenue vs 9 Kategori Biaya Langsung Proyek).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isFetching || !selectedProjectId}>
            <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />Perbarui
          </Button>
          <ReportHeader reportType="project-profitability" params={{ project_id: selectedProjectId }} disabled={!data || !selectedProjectId} />
        </div>
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

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <Card className="p-4 bg-slate-50 border-slate-200">
              <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Nilai Kontrak Revisi</span>
              <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                {formatIDR(data.revised_contract_value)}
              </div>
              <div className="text-[11px] text-slate-500 mt-1 font-mono">
                VO: +{formatIDR(data.variation_orders_value)}
              </div>
            </Card>
            <Card className="p-4 bg-emerald-50/60 border-emerald-200">
              <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Pendapatan Diakui</span>
              <div className="text-lg font-bold font-mono text-emerald-950 mt-1">
                {formatIDR(data.revenue_recognized)}
              </div>
            </Card>
            <Card className="p-4 bg-rose-50/60 border-rose-200">
              <span className="text-xs font-semibold text-rose-800 uppercase tracking-wider">Total Biaya Riil (COGS)</span>
              <div className="text-lg font-bold font-mono text-rose-950 mt-1">
                {formatIDR(data.total_project_cost)}
              </div>
            </Card>
            <Card className="p-4 bg-indigo-50/60 border-indigo-200">
              <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider">Laba Kotor Proyek</span>
              <div className="text-lg font-bold font-mono text-indigo-950 mt-1">
                {formatIDR(data.gross_profit)}
              </div>
              <div className="text-[11px] text-indigo-700 font-semibold mt-1">
                Margin: {data.gross_margin_percentage}%
              </div>
            </Card>
          </div>

          {/* Cost Breakdown Table */}
          <Card className="overflow-hidden p-0">
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center text-xs text-slate-600">
              <span>Proyek: <strong className="text-slate-900">{data.project_code} — {data.project_name}</strong></span>
              <span>Klien: <strong className="text-slate-900">{data.client_name || 'Umum'}</strong></span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100 text-slate-700 text-xs font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 border-b border-r border-slate-200">Kode</th>
                    <th className="px-4 py-3 border-b border-r border-slate-200">Kategori Biaya Langsung</th>
                    <th className="px-4 py-3 border-b border-slate-200 text-right">Realisasi Beban (Rp)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs font-mono">
                  {data.cost_breakdown.map((c) => (
                    <tr key={c.cost_category} className="hover:bg-slate-50">
                      <td className="px-4 py-2.5 font-bold text-slate-700 border-r border-slate-100">{c.cost_category}</td>
                      <td className="px-4 py-2.5 font-sans font-medium text-slate-900 border-r border-slate-100">{c.category_name}</td>
                      <td className="px-4 py-2.5 text-right text-slate-900 font-bold">
                        {Number(c.amount) > 0 ? formatIDR(c.amount) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-slate-100 font-mono text-xs font-bold text-slate-900">
                  <tr>
                    <td colSpan={2} className="px-4 py-3 text-right uppercase border-r border-slate-200">Total Biaya Pokok Proyek:</td>
                    <td className="px-4 py-3 text-right text-rose-800">{formatIDR(data.total_project_cost)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Card>
        </div>
      ) : (
        <Card className="p-8 text-center text-slate-500">
          Pilih proyek untuk melihat laporan laba rugi proyek.
        </Card>
      )}
    </div>
  );
};
