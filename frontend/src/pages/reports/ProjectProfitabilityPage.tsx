import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw, Info, HelpCircle } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { projectsApi } from '../../api/projects';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Select } from '../../components/ui/Select';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ProjectResponse } from '../../types/api';
import { ReportHeader } from '../../components/reports/ReportHeader';
import { ProjectHealthCard } from '../../components/ai/ProjectHealthCard';

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
          <h1 className="text-2xl font-bold text-slate-900">Profitabilitas Proyek</h1>
          <p className="text-sm text-slate-500">
            Ringkasan manajemen proyek: Penjualan invoiced, biaya langsung riil, dan posisi kas proyek.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isFetching || !selectedProjectId}>
            <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />Perbarui
          </Button>
          <ReportHeader reportType="project-profitability" params={{ project_id: selectedProjectId }} disabled={!data || !selectedProjectId} />
        </div>
      </div>

      {/* Management Disclaimer Notice */}
      <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3 text-xs text-amber-900">
        <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <strong className="font-semibold block mb-0.5">Catatan Manajemen (Bukan Laporan Keuangan Formal):</strong>
          Laporan ini adalah ringkasan manajemen untuk evaluasi performa proyek. Laporan ini tidak membuat jurnal akuntansi, tidak mengakui pendapatan perusahaan secara mandiri, dan tidak menggantikan Laporan Laba Rugi Resmi perusahaan.
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
      {selectedProjectId && <ProjectHealthCard projectId={selectedProjectId} />}

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <div className="space-y-6">
          {/* Commercial & Invoicing Overview */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">1. Kontrak & Penagihan</h3>
            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              <Card className="p-3.5 bg-slate-50 border-slate-200">
                <span className="text-[11px] font-semibold text-slate-600 uppercase">Nilai Kontrak</span>
                <div className="text-base font-bold font-mono text-slate-900 mt-1">
                  {formatIDR(data.contract_value ?? data.revised_contract_value)}
                </div>
                {Number(data.variation_orders_value) > 0 && (
                  <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
                    VO: +{formatIDR(data.variation_orders_value)}
                  </div>
                )}
              </Card>

              <Card className="p-3.5 bg-blue-50/50 border-blue-200">
                <span className="text-[11px] font-semibold text-blue-700 uppercase">Sudah Diinvoice</span>
                <div className="text-base font-bold font-mono text-blue-900 mt-1">
                  {formatIDR(data.invoiced_amount ?? data.revenue_recognized)}
                </div>
              </Card>

              <Card className="p-3.5 bg-emerald-50/60 border-emerald-200">
                <span className="text-[11px] font-semibold text-emerald-800 uppercase">Cash Diterima</span>
                <div className="text-base font-bold font-mono text-emerald-950 mt-1">
                  {formatIDR(data.cash_received ?? 0)}
                </div>
              </Card>

              <Card className="p-3.5 bg-amber-50/50 border-amber-200">
                <span className="text-[11px] font-semibold text-amber-800 uppercase">Piutang Pelanggan</span>
                <div className="text-base font-bold font-mono text-amber-950 mt-1">
                  {formatIDR(data.receivable_outstanding ?? 0)}
                </div>
              </Card>

              <Card className="p-3.5 bg-purple-50/50 border-purple-200">
                <span className="text-[11px] font-semibold text-purple-800 uppercase">Retensi</span>
                <div className="text-base font-bold font-mono text-purple-950 mt-1">
                  {formatIDR(data.retention_receivable ?? 0)}
                </div>
              </Card>
            </div>
          </div>

          {/* Operational Profitability & Direct Costs */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">2. Biaya Langsung & Profitabilitas Proyek</h3>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <Card className="p-4 bg-rose-50/60 border-rose-200">
                <span className="text-xs font-semibold text-rose-800 uppercase tracking-wider">Biaya Langsung Proyek</span>
                <div className="text-lg font-bold font-mono text-rose-950 mt-1">
                  {formatIDR(data.direct_project_cost ?? data.total_project_cost)}
                </div>
                <div className="text-[11px] text-rose-600 mt-1">
                  Material, upah, subkon, sewa, transport
                </div>
              </Card>

              <Card className="p-4 bg-indigo-50/60 border-indigo-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-indigo-800 uppercase tracking-wider">Laba Kotor Proyek</span>
                  <span title={data.help_texts?.laba_kotor_proyek || "Invoice proyek dikurangi biaya langsung proyek."}>
                    <HelpCircle className="w-3.5 h-3.5 text-indigo-400 cursor-help" />
                  </span>
                </div>
                <div className="text-lg font-bold font-mono text-indigo-950 mt-1">
                  {formatIDR(data.gross_project_profit ?? data.gross_profit)}
                </div>
                <div className="text-[11px] text-indigo-700 font-semibold mt-1">
                  Invoice - Biaya Langsung
                </div>
              </Card>

              <Card className="p-4 bg-violet-50/60 border-violet-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-violet-800 uppercase tracking-wider">Margin Proyek</span>
                  <span title={data.help_texts?.margin_proyek || "Persentase laba kotor dibanding nilai yang sudah diinvoice."}>
                    <HelpCircle className="w-3.5 h-3.5 text-violet-400 cursor-help" />
                  </span>
                </div>
                <div className="text-lg font-bold font-mono text-violet-950 mt-1">
                  {data.gross_margin_percentage || data.gross_margin || '0.00'}%
                </div>
                <div className="text-[11px] text-violet-600 mt-1">
                  Laba Kotor / Tagihan
                </div>
              </Card>

              <Card className="p-4 bg-teal-50/60 border-teal-200">
                <span className="text-xs font-semibold text-teal-800 uppercase tracking-wider">Kontribusi Bersih Proyek</span>
                <div className="text-lg font-bold font-mono text-teal-950 mt-1">
                  {formatIDR(data.project_net_contribution ?? data.gross_profit)}
                </div>
                <div className="text-[11px] text-teal-600 mt-1">
                  Setelah fee, bunga & PPh Final
                </div>
              </Card>
            </div>
          </div>

          {/* Cash Position & Financing */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">3. Arus Kas & Pembiayaan Proyek</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Card className="p-4 bg-slate-50 border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Posisi Kas Proyek</span>
                  <span title={data.help_texts?.posisi_kas_proyek || "Cash yang sudah diterima dikurangi cash yang sudah keluar untuk proyek."}>
                    <HelpCircle className="w-3.5 h-3.5 text-slate-400 cursor-help" />
                  </span>
                </div>
                <div className={`text-lg font-bold font-mono mt-1 ${Number(data.project_cash_position ?? 0) >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                  {formatIDR(data.project_cash_position ?? 0)}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Cash Diterima - Cash Keluar ({formatIDR(data.cash_spent ?? 0)})
                </div>
              </Card>

              <Card className="p-4 bg-slate-50 border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">PPh Dipotong (Kredit Pajak)</span>
                  <span title={data.help_texts?.pph_dipotong || "Pajak yang dipotong saat pelanggan membayar. Tidak selalu merupakan biaya."}>
                    <HelpCircle className="w-3.5 h-3.5 text-slate-400 cursor-help" />
                  </span>
                </div>
                <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                  {formatIDR(data.creditable_pph_withheld ?? 0)}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Uang Muka PPh (Bukan pengurang Laba Kotor)
                </div>
              </Card>

              <Card className="p-4 bg-slate-50 border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">Pokok Pinjaman Proyek</span>
                  <span title={data.help_texts?.pokok_pinjaman || "Pengembalian pokok utang. Mengurangi kas dan utang, bukan laba."}>
                    <HelpCircle className="w-3.5 h-3.5 text-slate-400 cursor-help" />
                  </span>
                </div>
                <div className="text-lg font-bold font-mono text-slate-900 mt-1">
                  {formatIDR(data.loan_principal_repayment ?? 0)}
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Pengembalian Pokok (Non-Biaya Laba Rugi)
                </div>
              </Card>
            </div>
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
                    <td colSpan={2} className="px-4 py-3 text-right uppercase border-r border-slate-200">Total Biaya Langsung Proyek:</td>
                    <td className="px-4 py-3 text-right text-rose-800">{formatIDR(data.direct_project_cost ?? data.total_project_cost)}</td>
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
