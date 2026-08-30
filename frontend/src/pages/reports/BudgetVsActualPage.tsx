import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { projectsApi } from '../../api/projects';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Select } from '../../components/ui/Select';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ProjectResponse } from '../../types/api';

export const BudgetVsActualPage: React.FC = () => {
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');

  const { data: projectsList } = useQuery({
    queryKey: ['projects-list-budget-bva'],
    queryFn: () => projectsApi.list(),
  });

  useEffect(() => {
    if (projectsList && projectsList.length > 0 && !selectedProjectId) {
      setSelectedProjectId(projectsList[0].id);
    }
  }, [projectsList, selectedProjectId]);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['budget-vs-actual', selectedProjectId],
    queryFn: () => reportsApi.getBudgetVsActual(selectedProjectId),
    enabled: !!selectedProjectId,
  });

  const projectOptions = projectsList
    ? projectsList.map((p: ProjectResponse) => ({
        value: p.id,
        label: `${p.project_code} — ${p.project_name}`,
      }))
    : [];

  const getStatusBadge = (status: string, pct: number | string) => {
    if (status === 'OVERBUDGET') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-rose-100 text-rose-800">
          <AlertTriangle className="w-3 h-3 mr-1" /> Overbudget ({pct}%)
        </span>
      );
    }
    if (status === 'WARNING') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
          Mendekati Batas ({pct}%)
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">
        Aman ({pct}%)
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Anggaran vs Realisasi (Budget vs Actual)</h1>
          <p className="text-sm text-slate-500">
            Monitoring serapan anggaran per kategori biaya langsung proyek kontraktor.
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

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          {!data.has_budget && (
            <div className="bg-amber-50 border border-amber-200 p-4 rounded-lg flex items-center space-x-3 text-xs text-amber-900">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
              <div>
                <strong>Informasi Anggaran:</strong> Proyek ini belum memiliki data anggaran (RAB) yang ditetapkan di master data. Nilai yang ditampilkan adalah realisasi biaya riil yang tercatat.
              </div>
            </div>
          )}

          {data.has_budget && (
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <Card className="p-4 bg-slate-50 border-slate-200">
                <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Total Anggaran (RAB)</span>
                <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                  {formatIDR(data.total_budget)}
                </div>
              </Card>
              <Card className="p-4 bg-blue-50/60 border-blue-200">
                <span className="text-xs font-semibold text-blue-800 uppercase tracking-wider">Total Realisasi Biaya</span>
                <div className="text-lg font-bold font-mono text-blue-950 mt-1">
                  {formatIDR(data.total_actual)}
                </div>
              </Card>
              <Card className="p-4 bg-emerald-50/60 border-emerald-200">
                <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">Sisa Anggaran (Varians)</span>
                <div className="text-lg font-bold font-mono text-emerald-950 mt-1">
                  {formatIDR(data.total_variance)}
                </div>
              </Card>
              <Card className="p-4 bg-indigo-50/60 border-indigo-200">
                <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider">Tingkat Serapan</span>
                <div className="text-xl font-bold font-mono text-indigo-950 mt-1">
                  {data.consumption_percentage}%
                </div>
              </Card>
            </div>
          )}

          {/* Detailed Lines Table */}
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-100 text-slate-700 text-xs font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 border-b border-r border-slate-200">Kode</th>
                    <th className="px-4 py-3 border-b border-r border-slate-200">Kategori Biaya</th>
                    {data.has_budget && (
                      <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Anggaran (RAB)</th>
                    )}
                    <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Realisasi (Actual)</th>
                    {data.has_budget && (
                      <>
                        <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Sisa / (Lebih)</th>
                        <th className="px-4 py-3 border-b border-slate-200">Status Serapan</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs font-mono">
                  {data.lines.map((l) => (
                    <tr key={l.cost_category} className="hover:bg-slate-50">
                      <td className="px-4 py-2.5 font-bold text-slate-700 border-r border-slate-100">{l.cost_category}</td>
                      <td className="px-4 py-2.5 font-sans font-medium text-slate-900 border-r border-slate-100">{l.category_name}</td>
                      {data.has_budget && (
                        <td className="px-4 py-2.5 text-right text-slate-700 border-r border-slate-100">
                          {formatIDR(l.budget_amount)}
                        </td>
                      )}
                      <td className="px-4 py-2.5 text-right text-slate-900 font-bold border-r border-slate-100">
                        {formatIDR(l.actual_amount)}
                      </td>
                      {data.has_budget && (
                        <>
                          <td className={`px-4 py-2.5 text-right font-bold border-r border-slate-100 ${Number(l.variance_amount) < 0 ? 'text-rose-700' : 'text-emerald-700'}`}>
                            {formatIDR(l.variance_amount)}
                          </td>
                          <td className="px-4 py-2.5 font-sans">
                            {getStatusBadge(l.status, l.variance_percentage)}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
};
