import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  FileText,
  Landmark,
  ArrowDownLeft,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import { reportsApi } from '../../../api/reports';
import { formatIDR } from '../../../utils/formatters';
import { Card } from '../../../components/ui/Card';
import { SkeletonLoader } from '../../../components/feedback/SkeletonLoader';

export const ActionItemsSection: React.FC = () => {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-action-items'],
    queryFn: () => reportsApi.getActionItems(),
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        <div className="h-5 w-48 bg-slate-200 animate-pulse rounded-sm" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <SkeletonLoader count={4} className="h-20 w-full" />
        </div>
      </div>
    );
  }

  const items = data || {
    documents_requires_review: 0,
    documents_failed: 0,
    documents_ready_to_post: 0,
    unmatched_bank_movements: 0,
    overdue_ar_count: 0,
    overdue_ar_amount: '0.00',
    overdue_ap_count: 0,
    overdue_ap_amount: '0.00',
    projects_with_warning: 0,
    total_action_count: 0,
  };

  const hasActions = items.total_action_count > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`flex h-6 w-6 items-center justify-center rounded-md ${
            hasActions ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
          }`}>
            {hasActions ? <AlertTriangle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
          </div>
          <h3 className="text-sm md:text-base font-bold text-slate-900 tracking-tight">
            Perlu Tindakan Operasional
          </h3>
          {hasActions && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-700">
              {items.total_action_count} butuh respon
            </span>
          )}
        </div>
      </div>

      {!hasActions ? (
        <Card className="p-4 bg-emerald-50/50 border-emerald-200/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-emerald-950">Semua Tugas Operasional Tuntas</p>
              <p className="text-[11px] text-emerald-700">
                Tidak ada dokumen tertunda, mutasi bank yang belum dicocokkan, atau tagihan yang lewat jatuh tempo saat ini.
              </p>
            </div>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {/* Dokumen Perlu Review */}
          {items.documents_requires_review > 0 && (
            <div
              onClick={() => navigate('/review-queue')}
              className="group p-3.5 rounded-xl border border-amber-200 bg-amber-50/70 hover:bg-amber-50 hover:border-amber-300 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-100 text-amber-800 shrink-0">
                  <AlertTriangle className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-amber-950">Dokumen Perlu Review</p>
                  <p className="text-[11px] text-amber-800">
                    <span className="font-semibold text-amber-900">{items.documents_requires_review} dokumen</span> butuh konfirmasi
                  </p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-amber-600 group-hover:translate-x-0.5 transition-transform shrink-0" />
            </div>
          )}

          {/* Mutasi Bank Belum Cocok */}
          {items.unmatched_bank_movements > 0 && (
            <div
              onClick={() => navigate('/bank-reconciliation')}
              className="group p-3.5 rounded-xl border border-blue-200 bg-blue-50/70 hover:bg-blue-50 hover:border-blue-300 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-100 text-blue-800 shrink-0">
                  <Landmark className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-blue-950">Mutasi Belum Cocok</p>
                  <p className="text-[11px] text-blue-800">
                    <span className="font-semibold text-blue-900">{items.unmatched_bank_movements} mutasi</span> belum direkonsiliasi
                  </p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-blue-600 group-hover:translate-x-0.5 transition-transform shrink-0" />
            </div>
          )}

          {/* Dokumen Siap Posting */}
          {items.documents_ready_to_post > 0 && (
            <div
              onClick={() => navigate('/documents')}
              className="group p-3.5 rounded-xl border border-indigo-200 bg-indigo-50/70 hover:bg-indigo-50 hover:border-indigo-300 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-800 shrink-0">
                  <FileText className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-indigo-950">Dokumen Siap Posting</p>
                  <p className="text-[11px] text-indigo-800">
                    <span className="font-semibold text-indigo-900">{items.documents_ready_to_post} dokumen</span> siap dijurnal
                  </p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-indigo-600 group-hover:translate-x-0.5 transition-transform shrink-0" />
            </div>
          )}

          {/* Piutang Jatuh Tempo */}
          {Number(items.overdue_ar_count) > 0 && (
            <div
              onClick={() => navigate('/receivables')}
              className="group p-3.5 rounded-xl border border-rose-200 bg-rose-50/70 hover:bg-rose-50 hover:border-rose-300 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-100 text-rose-800 shrink-0">
                  <ArrowDownLeft className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-rose-950">Piutang Jatuh Tempo</p>
                  <p className="text-[11px] text-rose-800">
                    <span className="font-semibold text-rose-900">{items.overdue_ar_count} invoice</span> ({formatIDR(items.overdue_ar_amount)})
                  </p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-rose-600 group-hover:translate-x-0.5 transition-transform shrink-0" />
            </div>
          )}

          {/* Utang Jatuh Tempo */}
          {Number(items.overdue_ap_count) > 0 && (
            <div
              onClick={() => navigate('/payables')}
              className="group p-3.5 rounded-xl border border-orange-200 bg-orange-50/70 hover:bg-orange-50 hover:border-orange-300 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-orange-100 text-orange-800 shrink-0">
                  <ArrowUpRight className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-orange-950">Utang Vendor Jatuh Tempo</p>
                  <p className="text-[11px] text-orange-800">
                    <span className="font-semibold text-orange-900">{items.overdue_ap_count} tagihan</span> ({formatIDR(items.overdue_ap_amount)})
                  </p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-orange-600 group-hover:translate-x-0.5 transition-transform shrink-0" />
            </div>
          )}

          {/* Proyek Warning / Over-budget */}
          {items.projects_with_warning > 0 && (
            <div
              onClick={() => navigate('/projects')}
              className="group p-3.5 rounded-xl border border-purple-200 bg-purple-50/70 hover:bg-purple-50 hover:border-purple-300 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-100 text-purple-800 shrink-0">
                  <Building2 className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-purple-950">Peringatan Biaya Proyek</p>
                  <p className="text-[11px] text-purple-800">
                    <span className="font-semibold text-purple-900">{items.projects_with_warning} proyek</span> biaya mendekati/lebihi kontrak
                  </p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-purple-600 group-hover:translate-x-0.5 transition-transform shrink-0" />
            </div>
          )}

          {/* Dokumen Gagal */}
          {items.documents_failed > 0 && (
            <div
              onClick={() => navigate('/documents')}
              className="group p-3.5 rounded-xl border border-rose-200 bg-rose-50/70 hover:bg-rose-50 hover:border-rose-300 transition-all cursor-pointer flex items-center justify-between shadow-2xs"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-100 text-rose-800 shrink-0">
                  <AlertTriangle className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-xs font-bold text-rose-950">Dokumen Gagal Diproses</p>
                  <p className="text-[11px] text-rose-800">
                    <span className="font-semibold text-rose-900">{items.documents_failed} dokumen</span> perlu perbaikan
                  </p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-rose-600 group-hover:translate-x-0.5 transition-transform shrink-0" />
            </div>
          )}
        </div>
      )}
    </div>
  );
};
