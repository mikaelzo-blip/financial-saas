import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText, Eye, UploadCloud, Hash, ShieldAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { documentsApi } from '../../api/documents';
import { DocumentResponse } from '../../types/api';
import { formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { DataTable, Column } from '../../components/tables/DataTable';
import { DocumentPreviewModal } from '../../components/documents/DocumentPreviewModal';
import { Modal } from '../../components/ui/Modal';
import { FileDropzone } from '../../components/forms/FileDropzone';

export const DocumentListPage: React.FC = () => {
  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const navigate = useNavigate();

  const { data: documents = [], isLoading, refetch } = useQuery({
    queryKey: ['documents'],
    queryFn: documentsApi.list,
  });

  const columns: Column<DocumentResponse>[] = [
    {
      key: 'processing_status',
      header: 'Status AI',
      render: (d) => (
        <span className={`inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-semibold ${d.review_flags.length ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}`}>
          {d.review_flags.length > 0 && <ShieldAlert className="h-3 w-3" />}{d.processing_status}
        </span>
      ),
    },
    {
      key: 'document_code',
      header: 'Kode Dokumen',
      sortable: true,
      render: (d) => (
        <span className="font-mono text-xs font-semibold text-blue-600">
          {d.document_code}
        </span>
      ),
    },
    {
      key: 'file_name',
      header: 'Nama File Bukti',
      sortable: true,
      render: (d) => (
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-slate-400" />
          <span className="font-medium text-slate-900">{d.file_name}</span>
        </div>
      ),
    },
    {
      key: 'file_hash',
      header: 'Kriptografi SHA-256',
      render: (d) => (
        <span className="inline-flex items-center gap-1 font-mono text-[11px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
          <Hash className="h-3 w-3" /> {d.file_hash.substring(0, 16)}...
        </span>
      ),
    },
    {
      key: 'file_size_bytes',
      header: 'Ukuran',
      sortable: true,
      render: (d) => (
        <span className="text-xs text-slate-600">
          {(d.file_size_bytes / 1024).toFixed(1)} KB
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Diunggah',
      sortable: true,
      render: (d) => <span className="text-xs text-slate-500">{formatDate(d.created_at)}</span>,
    },
    {
      key: 'actions',
      header: 'Aksi',
      align: 'right',
      render: (d) => (
        <Button
          size="sm"
          variant="ghost"
          leftIcon={<Eye className="h-3.5 w-3.5" />}
          onClick={(e) => {
            e.stopPropagation();
            if (d.processing_status === 'REVIEW_REQUIRED' || d.processing_status === 'READY_FOR_APPROVAL') navigate(`/documents/${d.id}/review`);
            else setSelectedDoc(d);
          }}
        >
          Lihat
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Arsip Dokumen Bukti</h2>
          <p className="text-xs text-slate-500 mt-1">
            Arsip dokumen nota fisik, kwitansi, SPK, dan faktur dengan perlindungan anti-duplikasi hash SHA-256.
          </p>
        </div>
        <Button
          leftIcon={<UploadCloud className="h-4 w-4" />}
          onClick={() => setUploadModalOpen(true)}
        >
          Unggah Dokumen
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={documents}
        keyExtractor={(d) => d.id}
        isLoading={isLoading}
        searchPlaceholder="Cari nama file atau kode dokumen..."
        searchKeys={['document_code', 'file_name', 'file_hash']}
        emptyTitle="Belum ada arsip dokumen"
        emptyDescription="Unggah nota atau faktur fisik untuk melampirkan bukti transaksi."
        emptyAction={
          <Button
            size="sm"
            leftIcon={<UploadCloud className="h-4 w-4" />}
            onClick={() => setUploadModalOpen(true)}
          >
            Unggah Dokumen Sekarang
          </Button>
        }
        onRowClick={(d) => setSelectedDoc(d)}
      />

      <DocumentPreviewModal
        document={selectedDoc}
        isOpen={!!selectedDoc}
        onClose={() => setSelectedDoc(null)}
      />

      <Modal
        isOpen={uploadModalOpen}
        onClose={() => setUploadModalOpen(false)}
        title="Unggah Dokumen Bukti Transaksi"
      >
        <FileDropzone
          onUploaded={() => {
            refetch();
            setUploadModalOpen(false);
          }}
        />
      </Modal>
    </div>
  );
};
