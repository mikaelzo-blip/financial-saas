import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Landmark,
  Upload,
  CheckCircle2,
  AlertCircle,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { bankReconciliationApi } from '../../api/bankReconciliation';
import { masterApi } from '../../api/master';
import { formatIDR } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { useToast } from '../../components/feedback/Toast';

export const BankReconciliationPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);

  // 1. Fetch Payment Accounts
  const { data: paymentAccounts } = useQuery({
    queryKey: ['payment-accounts'],
    queryFn: () => masterApi.getPaymentAccounts(),
  });

  // 2. Fetch Cash Completeness Dashboard
  const { data: dashboard, isLoading: isDashboardLoading } = useQuery({
    queryKey: ['cash-completeness-dashboard', selectedAccountId],
    queryFn: () => bankReconciliationApi.getCashCompletenessDashboard(selectedAccountId || undefined),
  });

  // 3. Upload Statement Mutation
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedAccountId || !fileToUpload) {
        throw new Error('Pilih rekening dan pilih file rekening koran.');
      }
      return bankReconciliationApi.uploadStatement(selectedAccountId, fileToUpload);
    },
    onSuccess: (res) => {
      setFileToUpload(null);
      queryClient.invalidateQueries({ queryKey: ['cash-completeness-dashboard'] });
      success(`Rekening koran berhasil di-import (${res.line_count} baris mutasi). Menjalankan auto-match...`);
      // Auto run match
      autoMatchMutation.mutate(res.id);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || err.message || 'Gagal mengunggah rekening koran.');
    },
  });

  // 4. Auto Match Mutation
  const autoMatchMutation = useMutation({
    mutationFn: (importId: string) => bankReconciliationApi.autoMatch(importId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['cash-completeness-dashboard'] });
      success(`Auto-match selesai: ${JSON.stringify(data.stats)}`);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Gagal menjalankan auto-match.');
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
              <Landmark className="h-4 w-4" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Rekonsiliasi Bank & Kelengkapan Kas
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Impor rekening koran bank (CSV/XLSX), deteksi mutasi otomatis, dan rekonsiliasikan dengan pembukuan kas.
          </p>
        </div>

        {/* Account Selector */}
        <div className="flex items-center gap-3">
          <select
            value={selectedAccountId}
            onChange={(e) => setSelectedAccountId(e.target.value)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-700 focus:ring-2 focus:ring-blue-500 outline-hidden"
          >
            <option value="">Semua Rekening Bank</option>
            {paymentAccounts?.map((pa) => (
              <option key={pa.id} value={pa.id}>
                {pa.name} {pa.account_number ? `(${pa.account_number})` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Cash Completeness Dashboard Cards */}
      {isDashboardLoading || !dashboard ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <SkeletonLoader count={4} className="h-28 w-full" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Bank Inflow */}
          <Card className="p-4 bg-emerald-50/40 border-emerald-200">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-emerald-800">Total Masuk (Bank)</span>
              <div className="flex h-7 w-7 items-center justify-center rounded bg-emerald-100 text-emerald-700">
                <TrendingUp className="h-4 w-4" />
              </div>
            </div>
            <p className="text-xl font-bold font-mono tabular-nums mt-2 text-emerald-950">
              {formatIDR(dashboard.total_bank_inflow)}
            </p>
            <p className="text-[10px] text-emerald-700 mt-1">Total mutasi kredit bank</p>
          </Card>

          {/* Total Bank Outflow */}
          <Card className="p-4 bg-rose-50/40 border-rose-200">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-rose-800">Total Keluar (Bank)</span>
              <div className="flex h-7 w-7 items-center justify-center rounded bg-rose-100 text-rose-700">
                <TrendingDown className="h-4 w-4" />
              </div>
            </div>
            <p className="text-xl font-bold font-mono tabular-nums mt-2 text-rose-950">
              {formatIDR(dashboard.total_bank_outflow)}
            </p>
            <p className="text-[10px] text-rose-700 mt-1">Total mutasi debet bank</p>
          </Card>

          {/* Matched Amount */}
          <Card className="p-4 bg-blue-50/40 border-blue-200">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-blue-800">Ter-Rekonsiliasi</span>
              <div className="flex h-7 w-7 items-center justify-center rounded bg-blue-100 text-blue-700">
                <CheckCircle2 className="h-4 w-4" />
              </div>
            </div>
            <p className="text-xl font-bold font-mono tabular-nums mt-2 text-blue-950">
              {formatIDR(dashboard.matched_amount)}
            </p>
            <p className="text-[10px] text-blue-700 mt-1">
              Kelengkapan: {dashboard.completeness_percentage.toFixed(1)}%
            </p>
          </Card>

          {/* Unallocated / Unmatched Cash */}
          <Card className="p-4 bg-amber-50/40 border-amber-200">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase text-amber-800">Kas Belum Teralokasi</span>
              <div className="flex h-7 w-7 items-center justify-center rounded bg-amber-100 text-amber-700">
                <AlertCircle className="h-4 w-4" />
              </div>
            </div>
            <p className="text-xl font-bold font-mono tabular-nums mt-2 text-amber-950">
              {formatIDR(dashboard.unallocated_cash_total)}
            </p>
            <p className="text-[10px] text-amber-700 mt-1">
              Belum dicocokkan ke proyek / invoice
            </p>
          </Card>
        </div>
      )}

      {/* Upload Statement Section */}
      <Card className="p-6 bg-white border-slate-200">
        <h3 className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
          <Upload className="w-4 h-4 text-blue-600" />
          Unggah Rekening Koran (Bank Statement)
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Unggah file rekening koran dalam format CSV atau XLSX. Sistem akan memverifikasi hash dokumen untuk mencegah duplikasi.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1 w-full">
            <input
              type="file"
              accept=".csv,.xlsx,.xls,.pdf"
              onChange={(e) => setFileToUpload(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
            />
          </div>

          <Button
            variant="primary"
            size="sm"
            onClick={() => uploadMutation.mutate()}
            isLoading={uploadMutation.isPending || autoMatchMutation.isPending}
            disabled={!fileToUpload || !selectedAccountId}
            leftIcon={<Upload className="w-4 h-4" />}
          >
            Impor & Rekonsiliasi Otomatis
          </Button>
        </div>
        {!selectedAccountId && (
          <p className="text-[11px] text-amber-600 mt-2 font-medium">
            * Harap pilih rekening bank di atas sebelum mengunggah rekening koran.
          </p>
        )}
      </Card>
    </div>
  );
};
