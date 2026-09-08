import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Eye, FileText, CheckCircle2 } from 'lucide-react';
import { reviewApi } from '../../api/review';
import { documentsApi } from '../../api/documents';
import { TransactionResponse, DocumentResponse, ReviewFlag } from '../../types/api';
import { formatIDR, formatDate } from '../../utils/formatters';
import { formatDocumentType, formatSourceChannel, formatTransactionType } from '../../utils/labels';
import { Button } from '../../components/ui/Button';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { DataTable, Column } from '../../components/tables/DataTable';
import { ReviewDrawer } from './components/ReviewDrawer';
import { useNavigate } from 'react-router-dom';

export const ReviewQueuePage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'documents' | 'transactions'>('documents');
  const [flagFilter, setFlagFilter] = useState<ReviewFlag | ''>('');
  const [selectedTrx, setSelectedTrx] = useState<TransactionResponse | null>(null);

  // Document review queue query
  const {
    data: documentQueue = [],
    isLoading: isDocsLoading,
    refetch: refetchDocs,
  } = useQuery({
    queryKey: ['document-review-queue'],
    queryFn: () => documentsApi.reviewQueue(),
  });

  // Transaction ambiguity review queue query
  const {
    data: queueItems = [],
    isLoading: isTrxLoading,
    refetch: refetchTrx,
  } = useQuery({
    queryKey: ['review-queue', flagFilter],
    queryFn: () => reviewApi.list(flagFilter || undefined),
  });

  const docColumns: Column<DocumentResponse>[] = [
    {
      key: 'file_name',
      header: 'Nama Berkas',
      sortable: true,
      render: (doc) => (
        <div>
          <span className="font-semibold text-xs text-slate-900 block truncate max-w-xs">
            {doc.file_name}
          </span>
          <span className="text-[11px] text-slate-400 font-mono">
            {formatSourceChannel(doc.source_channel)} • {formatDocumentType(doc.document_type)}
          </span>
        </div>
      ),
    },
    {
      key: 'created_at',
      header: 'Waktu Masuk',
      sortable: true,
      render: (doc) => (
        <span className="text-xs text-slate-600">{formatDate(doc.created_at)}</span>
      ),
    },
    {
      key: 'candidate_amount',
      header: 'Estimasi Nominal',
      sortable: true,
      align: 'right',
      render: (doc) => {
        const amt = doc.candidate_transaction?.amount || doc.extracted_data?.amount;
        return (
          <span className="font-semibold font-mono text-slate-900 tabular-nums text-xs">
            {amt ? formatIDR(Number(amt)) : '-'}
          </span>
        );
      },
    },
    {
      key: 'review_flags',
      header: 'Flag Review / Alasan',
      render: (doc) => (
        <div className="flex flex-wrap gap-1">
          {doc.review_flags && doc.review_flags.length > 0 ? (
            doc.review_flags.map((flag) => (
              <span
                key={flag}
                className="rounded bg-amber-100 text-amber-900 font-semibold px-2 py-0.5 text-[11px]"
              >
                {flag}
              </span>
            ))
          ) : (
            <span className="text-xs text-slate-400">Siap Verifikasi</span>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: 'Aksi',
      align: 'right',
      render: (doc) => (
        <Button
          size="sm"
          variant="primary"
          leftIcon={<Eye className="h-3.5 w-3.5" />}
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/documents/${doc.id}/review`);
          }}
        >
          Review Dokumen
        </Button>
      ),
    },
  ];

  const columns: Column<TransactionResponse>[] = [
    {
      key: 'transaction_code',
      header: 'Kode Transaksi',
      sortable: true,
      render: (t) => (
        <span className="font-mono text-xs font-semibold text-blue-600">
          {t.transaction_code}
        </span>
      ),
    },
    {
      key: 'transaction_date',
      header: 'Tanggal',
      sortable: true,
      render: (t) => <span className="text-xs text-slate-600">{formatDate(t.transaction_date)}</span>,
    },
    {
      key: 'description',
      header: 'Keterangan & Pihak Terkait',
      sortable: true,
      render: (t) => (
        <div>
          <p className="font-medium text-slate-900">{t.description}</p>
          <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-400">
            <span>{formatTransactionType(t.transaction_type)}</span>
            {t.counterparty_name && <span>• {t.counterparty_name}</span>}
          </div>
        </div>
      ),
    },
    {
      key: 'amount',
      header: 'Nominal',
      sortable: true,
      align: 'right',
      render: (t) => (
        <span className="font-semibold font-mono text-slate-900 tabular-nums">
          {formatIDR(t.amount)}
        </span>
      ),
    },
    {
      key: 'review_flags',
      header: 'Flag Review (Ambiguity)',
      render: (t) => (
        <div className="flex flex-wrap gap-1">
          {t.review_flags && t.review_flags.length > 0 ? (
            t.review_flags.map((f) => (
              <span key={f.id} title={f.message}>
                <StatusBadge status={f.flag} size="sm" />
              </span>
            ))
          ) : (
            <span className="text-xs text-slate-400">-</span>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      header: 'Aksi',
      align: 'right',
      render: (t) => (
        <Button
          size="sm"
          variant="outline"
          leftIcon={<Eye className="h-3.5 w-3.5" />}
          onClick={(e) => {
            e.stopPropagation();
            setSelectedTrx(t);
          }}
        >
          Tinjau
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Antrean Perlu Diperiksa
            </h2>
            {documentQueue.length + queueItems.length > 0 && (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-700 bg-amber-100 px-2.5 py-0.5 rounded-full">
                <AlertTriangle className="h-3.5 w-3.5" /> {documentQueue.length + queueItems.length} Perlu Diperiksa
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Pusat peninjauan dokumen masuk (OCR/WhatsApp) dan transaksi yang memerlukan konfirmasi sebelum pencatatan jurnal.
          </p>
        </div>
      </div>

      {/* Mode Tabs: Dokumen Sumber vs Transaksi */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab('documents')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
            activeTab === 'documents'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileText className="h-4 w-4" />
          Kandidat Dokumen Masuk
          {documentQueue.length > 0 && (
            <span className="rounded-full bg-blue-100 text-blue-700 text-xs px-2 py-0.5 font-bold">
              {documentQueue.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('transactions')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors cursor-pointer ${
            activeTab === 'transactions'
              ? 'border-blue-600 text-blue-600 font-semibold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <CheckCircle2 className="h-4 w-4" />
          Transaksi Ambigu / Verifikasi Manajer
          {queueItems.length > 0 && (
            <span className="rounded-full bg-amber-100 text-amber-700 text-xs px-2 py-0.5 font-bold">
              {queueItems.length}
            </span>
          )}
        </button>
      </div>

      {activeTab === 'documents' ? (
        <DataTable
          columns={docColumns}
          data={documentQueue}
          keyExtractor={(doc) => doc.id}
          isLoading={isDocsLoading}
          searchPlaceholder="Cari dokumen sumber..."
          searchKeys={['file_name', 'document_type', 'source_channel']}
          emptyTitle="Tidak ada dokumen memerlukan review"
          emptyDescription="Semua dokumen OCR atau kiriman WhatsApp telah selesai diverifikasi atau diproses."
          onRowClick={(doc) => navigate(`/documents/${doc.id}/review`)}
        />
      ) : (
        <div className="space-y-4">
          {/* Flag Filter Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto border-b border-slate-200 pb-2">
            {[
              { label: 'Semua Antrean', value: '' },
              { label: 'Selisih Nominal', value: 'AMOUNT_MISMATCH' },
              { label: 'Dugaan Duplikasi', value: 'DUPLICATE_SUSPECTED' },
              { label: 'Proyek Tidak Dikenal', value: 'PROJECT_UNKNOWN' },
              { label: 'Review Akun', value: 'ACCOUNT_REVIEW' },
              { label: 'Bukti Belum Lengkap', value: 'MISSING_DOCUMENT' },
            ].map((tab) => (
              <button
                key={tab.value}
                onClick={() => setFlagFilter(tab.value as any)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
                  flagFilter === tab.value
                    ? 'bg-blue-600 text-white shadow-xs font-semibold'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <DataTable
            columns={columns}
            data={queueItems}
            keyExtractor={(t) => t.id}
            isLoading={isTrxLoading}
            searchPlaceholder="Cari kode atau pihak..."
            searchKeys={['transaction_code', 'description', 'counterparty_name']}
            emptyTitle="Antrean review bersih"
            emptyDescription="Seluruh transaksi operasional telah ditinjau dan lolos verifikasi."
            onRowClick={(t) => setSelectedTrx(t)}
          />

          <ReviewDrawer
            transaction={selectedTrx}
            isOpen={!!selectedTrx}
            onClose={() => setSelectedTrx(null)}
            onRefresh={() => {
              refetchTrx();
              refetchDocs();
            }}
          />
        </div>
      )}
    </div>
  );
};

