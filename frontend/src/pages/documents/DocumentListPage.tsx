import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  FileText,
  UploadCloud,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RotateCw,
  ExternalLink,
  ShieldAlert,
  X,
  Send,
  AlertOctagon,
  Layers,
  MessageSquare,
} from 'lucide-react';
import { documentsApi } from '../../api/documents';
import {
  DocumentOperationalItem,
  DocumentOperationsSummaryResponse,
  DocumentOperationalListResponse,
  DocumentType,
  WhatsAppIntegrationStatusResponse,
} from '../../types/api';
import { formatIDR, formatDate, formatFailureReason } from '../../utils/formatters';
import { formatDocumentType, formatSourceChannel } from '../../utils/labels';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { DocumentPreviewModal } from '../../components/documents/DocumentPreviewModal';
import { Modal } from '../../components/ui/Modal';
import { FileDropzone } from '../../components/forms/FileDropzone';
import { EmptyState } from '../../components/feedback/EmptyState';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';

const FLAG_LABELS: Record<string, string> = {
  AMBIGUOUS_MATCH: 'Pencocokan Ambiguitas',
  PROJECT_UNKNOWN: 'Proyek Tidak Dikenal',
  VENDOR_UNKNOWN: 'Vendor Tidak Dikenal',
  CUSTOMER_UNKNOWN: 'Pelanggan Tidak Dikenal',
  DUPLICATE_SUSPECTED: 'Terduga Duplikat',
  TAX_REVIEW: 'Review Pajak',
  OCR_LOW_CONFIDENCE: 'Keyakinan OCR Rendah',
  AMOUNT_MISMATCH: 'Selisih Nominal',
  MISSING_DOCUMENT: 'Bukti Belum Ada',
  DATE_MISMATCH: 'Tanggal Tidak Cocok',
  ACCOUNT_REVIEW: 'Review Akun',
  RELATED_PARTY_REVIEW: 'Pihak Berelasi',
};

export const DocumentListPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedDoc, setSelectedDoc] = useState<DocumentOperationalItem | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  // Filters & Pagination State initialized from URL query parameters if present
  const [actionFilter, setActionFilter] = useState<string>(searchParams.get('action') || '');
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get('status') || '');
  const [documentTypeFilter, setDocumentTypeFilter] = useState<string>(searchParams.get('document_type') || '');
  const [sourceChannelFilter, setSourceChannelFilter] = useState<string>(searchParams.get('source_channel') || '');
  const [reviewFlagFilter, setReviewFlagFilter] = useState<string>(searchParams.get('review_flag') || '');
  const [searchTerm, setSearchTerm] = useState<string>(searchParams.get('search') || '');
  const [sortBy, setSortBy] = useState<string>(searchParams.get('sort_by') || 'created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>((searchParams.get('sort_dir') as 'asc' | 'desc') || 'desc');
  const [page, setPage] = useState<number>(Number(searchParams.get('page')) || 1);
  const pageSize = 10;

  // Sync state to URL search parameters so returning to /documents preserves filters
  React.useEffect(() => {
    const params = new URLSearchParams();
    if (actionFilter) params.set('action', actionFilter);
    if (statusFilter) params.set('status', statusFilter);
    if (documentTypeFilter) params.set('document_type', documentTypeFilter);
    if (sourceChannelFilter) params.set('source_channel', sourceChannelFilter);
    if (reviewFlagFilter) params.set('review_flag', reviewFlagFilter);
    if (searchTerm) params.set('search', searchTerm);
    if (sortBy && sortBy !== 'created_at') params.set('sort_by', sortBy);
    if (sortDir && sortDir !== 'desc') params.set('sort_dir', sortDir);
    if (page > 1) params.set('page', String(page));
    setSearchParams(params, { replace: true });
  }, [actionFilter, statusFilter, documentTypeFilter, sourceChannelFilter, reviewFlagFilter, searchTerm, sortBy, sortDir, page, setSearchParams]);

  const getReturnUrl = () => {
    const params = new URLSearchParams();
    if (actionFilter) params.set('action', actionFilter);
    if (statusFilter) params.set('status', statusFilter);
    if (documentTypeFilter) params.set('document_type', documentTypeFilter);
    if (sourceChannelFilter) params.set('source_channel', sourceChannelFilter);
    if (reviewFlagFilter) params.set('review_flag', reviewFlagFilter);
    if (searchTerm) params.set('search', searchTerm);
    if (sortBy && sortBy !== 'created_at') params.set('sort_by', sortBy);
    if (sortDir && sortDir !== 'desc') params.set('sort_dir', sortDir);
    if (page > 1) params.set('page', String(page));
    const qs = params.toString();
    return qs ? `/documents?${qs}` : '/documents';
  };

  // Actions loading state
  const [postingId, setPostingId] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Fetch summary metrics
  const {
    data: summary,
    isLoading: isSummaryLoading,
    isError: isSummaryError,
    refetch: refetchSummary,
  } = useQuery<DocumentOperationsSummaryResponse>({
    queryKey: ['document-operations-summary'],
    queryFn: documentsApi.operationsSummary,
    refetchInterval: 30000,
  });

  // Fetch WhatsApp integration status
  const {
    data: waStatus,
    refetch: refetchWaStatus,
  } = useQuery<WhatsAppIntegrationStatusResponse>({
    queryKey: ['whatsapp-integration-status'],
    queryFn: documentsApi.whatsappStatus,
    refetchInterval: 30000,
  });

  // Fetch paginated operational list
  const {
    data: listData,
    isLoading: isListLoading,
    isError: isListError,
    refetch: refetchList,
  } = useQuery<DocumentOperationalListResponse>({
    queryKey: [
      'document-operations-list',
      actionFilter,
      statusFilter,
      documentTypeFilter,
      sourceChannelFilter,
      reviewFlagFilter,
      searchTerm,
      sortBy,
      sortDir,
      page,
      pageSize,
    ],
    queryFn: () =>
      documentsApi.operationsList({
        action_filter: actionFilter || undefined,
        processing_status: statusFilter || undefined,
        document_type: documentTypeFilter || undefined,
        source_channel: sourceChannelFilter || undefined,
        review_flag: reviewFlagFilter || undefined,
        search: searchTerm || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        limit: pageSize,
      }),
    refetchInterval: 30000,
  });

  const handleRefresh = () => {
    refetchSummary();
    refetchList();
    refetchWaStatus();
  };

  const resetFilters = () => {
    setActionFilter('');
    setStatusFilter('');
    setDocumentTypeFilter('');
    setSourceChannelFilter('');
    setReviewFlagFilter('');
    setSearchTerm('');
    setSortBy('created_at');
    setSortDir('desc');
    setPage(1);
  };

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
    setPage(1);
  };

  const handleActionFilterClick = (filter: string) => {
    setActionFilter((prev) => (prev === filter ? '' : filter));
    setPage(1);
  };

  const handleFlagFilterClick = (flag: string) => {
    setReviewFlagFilter((prev) => (prev === flag ? '' : flag));
    setPage(1);
  };

  const handleRetry = async (docId: string) => {
    try {
      setRetryingId(docId);
      setActionFeedback(null);
      await documentsApi.retry(docId);
      setActionFeedback({ message: 'Dokumen dijadwalkan ulang untuk diproses.', type: 'success' });
      handleRefresh();
    } catch (err: any) {
      setActionFeedback({
        message: err?.response?.data?.detail || 'Gagal menjadwalkan ulang dokumen.',
        type: 'error',
      });
    } finally {
      setRetryingId(null);
    }
  };

  const handlePostAccounting = async (docId: string) => {
    try {
      setPostingId(docId);
      setActionFeedback(null);
      const res = await documentsApi.postAccounting(docId);
      setActionFeedback({
        message: `Dokumen berhasil diposting ke Buku Besar (${res.transaction_code || 'Tercatat'}).`,
        type: 'success',
      });
      handleRefresh();
    } catch (err: any) {
      setActionFeedback({
        message: err?.response?.data?.detail || 'Gagal memposting dokumen ke akuntansi.',
        type: 'error',
      });
    } finally {
      setPostingId(null);
    }
  };

  const hasActiveFilters =
    Boolean(actionFilter) ||
    Boolean(statusFilter) ||
    Boolean(documentTypeFilter) ||
    Boolean(sourceChannelFilter) ||
    Boolean(reviewFlagFilter) ||
    Boolean(searchTerm) ||
    sortBy !== 'created_at' ||
    sortDir !== 'desc';

  const items = listData?.items ?? [];
  const total = listData?.total ?? 0;
  const totalPages = listData?.total_pages ?? 1;

  if (isSummaryError || isListError) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center">
        <AlertTriangle className="mx-auto h-8 w-8 text-rose-600 mb-2" />
        <h3 className="text-sm font-semibold text-rose-900">Gagal memuat data operasional dokumen.</h3>
        <p className="text-xs text-rose-700 mt-1 mb-4">
          Periksa koneksi backend atau coba muat ulang halaman.
        </p>
        <Button size="sm" variant="outline" onClick={handleRefresh}>
          Coba Lagi
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Feedback notification */}
      {actionFeedback && (
        <div
          className={`flex items-center justify-between rounded-lg p-3 text-xs ${
            actionFeedback.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
              : 'bg-rose-50 text-rose-800 border border-rose-200'
          }`}
        >
          <div className="flex items-center gap-2">
            {actionFeedback.type === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
            )}
            <span>{actionFeedback.message}</span>
          </div>
          <button
            type="button"
            className="text-slate-400 hover:text-slate-600"
            onClick={() => setActionFeedback(null)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Operasional Pipeline Dokumen</h2>
          <p className="text-xs text-slate-500 mt-1">
            Pemantauan berkas masuk, antrean worker OCR, status review, antrean posting akuntansi, dan deteksi dokumen tertahan.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            leftIcon={<RefreshCw className={`h-3.5 w-3.5 ${isListLoading || isSummaryLoading ? 'animate-spin' : ''}`} />}
            onClick={handleRefresh}
          >
            Refresh
          </Button>
          <Button
            size="sm"
            leftIcon={<UploadCloud className="h-4 w-4" />}
            onClick={() => setUploadModalOpen(true)}
          >
            Unggah Dokumen
          </Button>
        </div>
      </div>

      {/* Actionable Metrics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <button
          type="button"
          onClick={() => handleActionFilterClick('NEEDS_REVIEW')}
          className={`text-left rounded-xl p-3 border transition-all ${
            actionFilter === 'NEEDS_REVIEW'
              ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-500/20 shadow-sm'
              : 'border-slate-200 bg-white hover:border-amber-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Perlu Review</span>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.actionable_counts.needs_review ?? 0}
          </div>
        </button>

        <button
          type="button"
          onClick={() => handleActionFilterClick('READY_TO_POST')}
          className={`text-left rounded-xl p-3 border transition-all ${
            actionFilter === 'READY_TO_POST'
              ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500/20 shadow-sm'
              : 'border-slate-200 bg-white hover:border-blue-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Siap Posting</span>
            <Send className="h-4 w-4 text-blue-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.actionable_counts.ready_to_post ?? 0}
          </div>
        </button>

        <button
          type="button"
          onClick={() => handleActionFilterClick('FAILED')}
          className={`text-left rounded-xl p-3 border transition-all ${
            actionFilter === 'FAILED'
              ? 'border-rose-500 bg-rose-50 ring-2 ring-rose-500/20 shadow-sm'
              : 'border-slate-200 bg-white hover:border-rose-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Gagal</span>
            <AlertOctagon className="h-4 w-4 text-rose-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.actionable_counts.failed ?? 0}
          </div>
        </button>

        <button
          type="button"
          onClick={() => handleActionFilterClick('QUEUED')}
          className={`text-left rounded-xl p-3 border transition-all ${
            actionFilter === 'QUEUED'
              ? 'border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500/20 shadow-sm'
              : 'border-slate-200 bg-white hover:border-indigo-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Dalam Antrean</span>
            <Clock className="h-4 w-4 text-indigo-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.actionable_counts.queued ?? 0}
          </div>
        </button>

        <button
          type="button"
          onClick={() => handleActionFilterClick('PROCESSING')}
          className={`text-left rounded-xl p-3 border transition-all ${
            actionFilter === 'PROCESSING'
              ? 'border-purple-500 bg-purple-50 ring-2 ring-purple-500/20 shadow-sm'
              : 'border-slate-200 bg-white hover:border-purple-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Sedang Diproses</span>
            <RotateCw className="h-4 w-4 text-purple-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.actionable_counts.processing ?? 0}
          </div>
        </button>

        <button
          type="button"
          onClick={() => handleActionFilterClick('POSTED')}
          className={`text-left rounded-xl p-3 border transition-all ${
            actionFilter === 'POSTED'
              ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-500/20 shadow-sm'
              : 'border-slate-200 bg-white hover:border-emerald-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Sudah Diposting</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {summary?.actionable_counts.posted ?? 0}
          </div>
        </button>
      </div>

      {/* Middle Status Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Queue & Background Worker Health */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
            <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="h-4 w-4 text-slate-500" />
              Antrean & Background Worker
            </h3>
            {summary?.queue_health?.is_paused && (
              <span className="text-[10px] bg-rose-100 text-rose-800 font-semibold px-2 py-0.5 rounded">
                Worker Tertunda
              </span>
            )}
          </div>
          <div className="grid grid-cols-4 gap-2 text-center mb-3">
            <button
              type="button"
              onClick={() => handleActionFilterClick('QUEUED')}
              className={`p-2 rounded-lg border transition-all ${
                actionFilter === 'QUEUED'
                  ? 'bg-indigo-50 border-indigo-400 ring-2 ring-indigo-200'
                  : 'bg-slate-50 border-slate-100 hover:bg-indigo-50/50'
              }`}
            >
              <span className="block text-[11px] text-slate-500">Pending</span>
              <span className="text-base font-bold text-slate-800">
                {summary?.queue_health?.pending_count ?? 0}
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleActionFilterClick('PROCESSING')}
              className={`p-2 rounded-lg border transition-all ${
                actionFilter === 'PROCESSING'
                  ? 'bg-purple-50 border-purple-400 ring-2 ring-purple-200'
                  : 'bg-slate-50 border-slate-100 hover:bg-purple-50/50'
              }`}
            >
              <span className="block text-[11px] text-slate-500">Running</span>
              <span className="text-base font-bold text-blue-600">
                {summary?.queue_health?.running_count ?? 0}
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleActionFilterClick('RETRYING')}
              className={`p-2 rounded-lg border transition-all ${
                actionFilter === 'RETRYING'
                  ? 'bg-amber-50 border-amber-400 ring-2 ring-amber-200'
                  : 'bg-slate-50 border-slate-100 hover:bg-amber-50/50'
              }`}
            >
              <span className="block text-[11px] text-slate-500">Retrying</span>
              <span className="text-base font-bold text-amber-600">
                {summary?.queue_health?.retrying_count ?? 0}
              </span>
            </button>
            <button
              type="button"
              onClick={() => handleActionFilterClick('FAILED')}
              className={`p-2 rounded-lg border transition-all ${
                actionFilter === 'FAILED'
                  ? 'bg-rose-50 border-rose-400 ring-2 ring-rose-200'
                  : 'bg-slate-50 border-slate-100 hover:bg-rose-50/50'
              }`}
            >
              <span className="block text-[11px] text-slate-500">Worker Gagal</span>
              <span className="text-base font-bold text-rose-600">
                {summary?.queue_health?.failed_count ?? 0}
              </span>
            </button>
          </div>
          <div className="space-y-1.5 text-xs text-slate-600">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Terlama dalam antrean:</span>
              <span className="font-mono font-medium">
                {summary?.queue_health?.oldest_pending_seconds != null
                  ? `${summary.queue_health.oldest_pending_seconds} detik`
                  : '-'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Terakhir gagal:</span>
              <span className="font-mono text-[11px] text-rose-700 max-w-xs truncate text-right">
                {summary?.queue_health?.latest_failure
                  ? `${summary.queue_health.latest_failure.job_type}: ${summary.queue_health.latest_failure.failure_message}`
                  : 'Tidak ada'}
              </span>
            </div>
          </div>
        </div>

        {/* Warning Flags & Integrity Summary */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
            <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert className="h-4 w-4 text-amber-600" />
              Peringatan & Flag Integritas
            </h3>
            {reviewFlagFilter && (
              <button
                type="button"
                onClick={() => {
                  setReviewFlagFilter('');
                  setPage(1);
                }}
                className="text-[10px] text-blue-600 hover:underline flex items-center gap-1"
              >
                Reset Flag <X className="h-3 w-3" />
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {summary?.integrity_flags &&
              Object.entries(summary.integrity_flags).map(([flag, count]) => {
                if (count === 0) return null;
                const label = FLAG_LABELS[flag] || flag;
                const isActive = reviewFlagFilter === flag;
                return (
                  <button
                    key={flag}
                    type="button"
                    onClick={() => handleFlagFilterClick(flag)}
                    className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg border transition-all ${
                      isActive
                        ? 'bg-amber-100 border-amber-400 text-amber-900 font-semibold ring-2 ring-amber-300'
                        : 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-amber-50'
                    }`}
                  >
                    <span>{label}</span>
                    <span className="bg-amber-200 text-amber-800 text-[10px] font-bold px-1.5 py-0.2 rounded-full">
                      {count}
                    </span>
                  </button>
                );
              })}
            {(!summary?.integrity_flags ||
              Object.values(summary.integrity_flags).every((cnt) => cnt === 0)) && (
              <p className="text-xs text-slate-400 italic py-2">
                Tidak ada dokumen dengan flag peringatan saat ini.
              </p>
            )}
          </div>
        </div>

        {/* WhatsApp Integration Health */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid="whatsapp-status-card">
          <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
            <h3 className="text-xs font-semibold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
              <MessageSquare className="h-4 w-4 text-emerald-600" />
              Integrasi WhatsApp
            </h3>
            <span
              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                waStatus?.connection_state === 'CONNECTED'
                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                  : waStatus?.connection_state === 'CONNECTING'
                  ? 'bg-amber-100 text-amber-800 border border-amber-200'
                  : 'bg-slate-100 text-slate-700 border border-slate-200'
              }`}
            >
              {waStatus?.connection_state === 'CONNECTED'
                ? 'Terhubung'
                : waStatus?.connection_state === 'CONNECTING'
                ? 'Menghubungkan'
                : 'Terputus'}
            </span>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Terakhir Masuk:</span>
              <span className="font-medium text-slate-800">
                {waStatus?.last_message_at ? formatDate(waStatus.last_message_at) : '-'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Antrean / Pending:</span>
              <span className="font-semibold text-slate-800">
                {waStatus?.pending_handoff_count ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Terakhir Berhasil:</span>
              <span className="font-medium text-slate-800">
                {waStatus?.last_successful_ingestion_at
                  ? formatDate(waStatus.last_successful_ingestion_at)
                  : '-'}
              </span>
            </div>
            <div className="flex items-start justify-between gap-2 pt-1 border-t border-slate-100">
              <span className="text-slate-500 shrink-0">Error Terakhir:</span>
              <span className="font-mono text-[11px] text-rose-600 text-right truncate max-w-[180px]">
                {waStatus?.last_error_message_safe || 'Tidak ada'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Cari kode dokumen, file, mitra..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setPage(1);
            }}
            className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <select
          aria-label="Filter Status"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Semua Status</option>
          <option value="REVIEW_REQUIRED">Status: Perlu Review</option>
          <option value="READY_TO_POST">Status: Siap Posting</option>
          <option value="READY_FOR_APPROVAL">Status: Siap Disetujui</option>
          <option value="UPLOADED">Status: Diterima</option>
          <option value="QUEUED">Status: Dalam Antrean</option>
          <option value="EXTRACTING">Status: Ekstraksi OCR</option>
          <option value="EXTRACTED">Status: Terekstraksi</option>
          <option value="POSTED">Status: Sudah Diposting</option>
          <option value="REJECTED">Status: Ditolak</option>
          <option value="FAILED">Status: Gagal</option>
        </select>

        <select
          aria-label="Filter Jenis Dokumen"
          value={documentTypeFilter}
          onChange={(e) => {
            setDocumentTypeFilter(e.target.value);
            setPage(1);
          }}
          className="text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Semua Jenis Dokumen</option>
          <option value="INVOICE">Jenis: Faktur / Tagihan</option>
          <option value="VENDOR_INVOICE">Jenis: Tagihan Vendor</option>
          <option value="RECEIPT">Jenis: Kuitansi / Bukti Bayar</option>
          <option value="SURAT_JALAN">Jenis: Surat Jalan</option>
          <option value="CONTRACT">Jenis: Kontrak / SPK</option>
          <option value="TAX_INVOICE">Jenis: Faktur Pajak</option>
          <option value="OTHER">Jenis: Lainnya</option>
        </select>

        <select
          aria-label="Filter Saluran"
          value={sourceChannelFilter}
          onChange={(e) => {
            setSourceChannelFilter(e.target.value);
            setPage(1);
          }}
          className="text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Semua Saluran</option>
          <option value="WEB">Saluran: Web Upload</option>
          <option value="WHATSAPP">Saluran: WhatsApp</option>
          <option value="API">Saluran: API</option>
        </select>

        <select
          aria-label="Filter Peringatan"
          value={reviewFlagFilter}
          onChange={(e) => {
            setReviewFlagFilter(e.target.value);
            setPage(1);
          }}
          className="text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Semua Peringatan</option>
          <option value="AMBIGUOUS_MATCH">Flag: Pencocokan Ambiguitas</option>
          <option value="DUPLICATE_SUSPECTED">Flag: Terduga Duplikat</option>
          <option value="PROJECT_UNKNOWN">Flag: Proyek Tidak Dikenal</option>
          <option value="VENDOR_UNKNOWN">Flag: Vendor Tidak Dikenal</option>
          <option value="CUSTOMER_UNKNOWN">Flag: Pelanggan Tidak Dikenal</option>
          <option value="TAX_REVIEW">Flag: Review Pajak</option>
          <option value="OCR_LOW_CONFIDENCE">Flag: Keyakinan OCR Rendah</option>
          <option value="AMOUNT_MISMATCH">Flag: Selisih Nominal</option>
        </select>

        {hasActiveFilters && (
          <Button size="sm" variant="ghost" onClick={resetFilters}>
            Reset Filter
          </Button>
        )}
      </div>

      {/* Main Operational Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        {isListLoading ? (
          <div className="p-6 space-y-3">
            <SkeletonLoader className="h-6 w-1/4" />
            <SkeletonLoader className="h-10 w-full" />
            <SkeletonLoader className="h-10 w-full" />
            <SkeletonLoader className="h-10 w-full" />
          </div>
        ) : items.length === 0 ? (
          <div className="py-12">
            <EmptyState
              title="Tidak ada dokumen dalam pipeline"
              description={
                hasActiveFilters
                  ? 'Tidak ada dokumen yang cocok dengan filter yang dipilih.'
                  : 'Unggah berkas bukti transaksi atau tunggu berkas masuk melalui WhatsApp.'
              }
              action={
                hasActiveFilters ? (
                  <Button size="sm" variant="outline" onClick={resetFilters}>
                    Hapus Filter
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    leftIcon={<UploadCloud className="h-4 w-4" />}
                    onClick={() => setUploadModalOpen(true)}
                  >
                    Unggah Dokumen Sekarang
                  </Button>
                )
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/75 text-slate-600 font-semibold">
                  <th
                    className="py-3 px-4 cursor-pointer select-none hover:text-blue-600"
                    onClick={() => handleSort('status')}
                  >
                    <div className="flex items-center gap-1">
                      <span>Status & Umur</span>
                      {sortBy === 'status' && (
                        <span className="text-[10px] font-mono">{sortDir === 'asc' ? '▲' : '▼'}</span>
                      )}
                    </div>
                  </th>
                  <th
                    className="py-3 px-4 cursor-pointer select-none hover:text-blue-600"
                    onClick={() => handleSort('document_code')}
                  >
                    <div className="flex items-center gap-1">
                      <span>Kode & Berkas</span>
                      {sortBy === 'document_code' && (
                        <span className="text-[10px] font-mono">{sortDir === 'asc' ? '▲' : '▼'}</span>
                      )}
                    </div>
                  </th>
                  <th className="py-3 px-4">Jenis</th>
                  <th className="py-3 px-4">Mitra & Proyek</th>
                  <th className="py-3 px-4 text-right">Estimasi Nominal</th>
                  <th className="py-3 px-4">Peringatan</th>
                  <th className="py-3 px-4">Transaksi / Posting</th>
                  <th className="py-3 px-4 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((doc) => (
                  <tr
                    key={doc.id}
                    className="hover:bg-slate-50/80 transition-colors"
                  >
                    {/* Status & Umur */}
                    <td className="py-3 px-4 align-top">
                      <div className="space-y-1">
                        <StatusBadge status={doc.processing_status} size="sm" />
                        {doc.is_stuck && (
                          <div>
                            <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                              <AlertTriangle className="h-3 w-3" /> Tertahan
                            </span>
                          </div>
                        )}
                        {doc.failure_code && (
                          <div className="text-[10px] text-rose-700 flex items-center gap-1 font-medium">
                            <AlertOctagon className="h-3 w-3 shrink-0" />
                            <span className="truncate max-w-[160px]" title={doc.failure_code}>
                              {formatFailureReason(doc.failure_code, doc.failure_message)}
                            </span>
                            <span className="sr-only">{doc.failure_code}</span>
                          </div>
                        )}
                        {doc.processing_attempts > 0 && doc.processing_status !== 'POSTED' && (
                          <div className="text-[10px] text-amber-700 font-medium">
                            Percobaan: {doc.processing_attempts}x
                          </div>
                        )}
                        <div className="text-[10px] text-slate-400">
                          {doc.age_display || formatDate(doc.received_at)}
                        </div>
                      </div>
                    </td>

                    {/* Kode & Berkas */}
                    <td className="py-3 px-4 align-top">
                      <div className="space-y-0.5">
                        <span className="font-mono font-semibold text-blue-600 block">
                          {doc.document_code}
                        </span>
                        <div className="flex items-center gap-1 text-slate-900 font-medium">
                          <FileText className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                          <span className="truncate max-w-[160px]" title={doc.file_name}>
                            {doc.file_name}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                          <span>{(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                          <span>•</span>
                          <span className="capitalize">{formatSourceChannel(doc.source_channel)}</span>
                        </div>
                      </div>
                    </td>

                    {/* Jenis Dokumen */}
                    <td className="py-3 px-4 align-top text-slate-700">
                      <span>{formatDocumentType(doc.document_type as DocumentType)}</span>
                    </td>

                    {/* Mitra & Proyek */}
                    <td className="py-3 px-4 align-top">
                      <div className="space-y-0.5">
                        <div className="font-medium text-slate-900">
                          {doc.counterparty_name || '-'}
                        </div>
                        <div className="text-[11px] text-slate-500 font-mono">
                          {doc.project_code || doc.project_name || '-'}
                        </div>
                      </div>
                    </td>

                    {/* Estimasi Nominal */}
                    <td className="py-3 px-4 align-top text-right font-medium text-slate-900">
                      {doc.amount != null ? formatIDR(doc.amount) : '-'}
                      {doc.currency && doc.currency !== 'IDR' && (
                        <span className="block text-[10px] text-slate-400">{doc.currency}</span>
                      )}
                    </td>

                    {/* Peringatan / Flags */}
                    <td className="py-3 px-4 align-top">
                      <div className="flex flex-wrap gap-1 max-w-[150px]">
                        {doc.review_flags && doc.review_flags.length > 0 ? (
                          doc.review_flags.map((flg) => (
                            <span
                              key={flg}
                              className="inline-flex text-[10px] bg-amber-50 text-amber-800 border border-amber-200 rounded px-1 py-0.2"
                            >
                              {FLAG_LABELS[flg] || flg}
                            </span>
                          ))
                        ) : doc.processing_status === 'FAILED' && doc.failure_message ? (
                          <span
                            className="inline-flex text-[10px] bg-rose-50 text-rose-800 border border-rose-200 rounded px-1 py-0.2 truncate max-w-[140px]"
                            title={doc.failure_message}
                          >
                            {doc.failure_message}
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-400">-</span>
                        )}
                      </div>
                    </td>

                    {/* Transaksi / Posting */}
                    <td className="py-3 px-4 align-top">
                      {doc.converted_transaction_id ? (
                        <button
                          type="button"
                          onClick={() => navigate(`/transactions/${doc.converted_transaction_id}`)}
                          className="inline-flex items-center gap-1 font-mono text-[11px] text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {doc.converted_transaction_code || 'Lihat Transaksi'}
                          <ExternalLink className="h-3 w-3" />
                        </button>
                      ) : doc.posting_job_status ? (
                        <span className="inline-flex items-center gap-1 text-[10px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded font-mono">
                          {doc.posting_job_status}
                        </span>
                      ) : (
                        <span className="text-[11px] text-slate-400">-</span>
                      )}
                    </td>

                    {/* Aksi */}
                    <td className="py-3 px-4 align-top text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {doc.can_review && (
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => {
                              const returnUrl = getReturnUrl();
                              const searchPart = returnUrl.includes('?') ? returnUrl.slice(returnUrl.indexOf('?')) : '';
                              navigate(`/documents/${doc.id}/review${searchPart}`, {
                                state: { returnTo: returnUrl },
                              });
                            }}
                          >
                            Periksa
                          </Button>
                        )}
                        {doc.can_post && (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={postingId === doc.id}
                            onClick={() => handlePostAccounting(doc.id)}
                          >
                            {postingId === doc.id ? 'Memposting...' : 'Posting'}
                          </Button>
                        )}
                        {doc.can_retry && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={retryingId === doc.id}
                            onClick={() => handleRetry(doc.id)}
                          >
                            {retryingId === doc.id ? 'Mencoba...' : 'Coba Lagi'}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedDoc(doc)}
                        >
                          Lihat
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Server-side Pagination Footer */}
        {!isListLoading && items.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 bg-slate-50/50 text-xs text-slate-600">
            <div>
              Menampilkan{' '}
              <span className="font-semibold text-slate-900">
                {(page - 1) * pageSize + 1}
              </span>{' '}
              -{' '}
              <span className="font-semibold text-slate-900">
                {Math.min(page * pageSize, total)}
              </span>{' '}
              dari <span className="font-semibold text-slate-900">{total}</span> dokumen
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Sebelumnya
              </Button>
              <span className="font-medium">
                {page} / {totalPages}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Berikutnya
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Preview Modal */}
      <DocumentPreviewModal
        document={selectedDoc}
        isOpen={Boolean(selectedDoc)}
        onClose={() => setSelectedDoc(null)}
      />

      {/* Upload Modal */}
      <Modal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        title="Unggah Dokumen Bukti Transaksi"
      >
        <FileDropzone
          onUploaded={() => {
            handleRefresh();
            setUploadModalOpen(false);
          }}
        />
      </Modal>
    </div>
  );
};
