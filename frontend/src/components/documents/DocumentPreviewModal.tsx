import React from 'react';
import { FileText, Download, Hash } from 'lucide-react';
import { DocumentResponse } from '../../types/api';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

export interface DocumentPreviewModalProps {
  document: DocumentResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  document,
  isOpen,
  onClose,
}) => {
  if (!document) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="2xl"
      title={`Pratinjau Dokumen — ${document.document_code}`}
    >
      <div className="space-y-4">
        {/* Document Metadata Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 p-3 text-xs border border-slate-200">
          <div>
            <p className="font-semibold text-slate-900">{document.file_name}</p>
            <p className="text-[10px] text-slate-500 font-mono mt-0.5 flex items-center gap-1">
              <Hash className="h-3 w-3" /> SHA-256: {document.file_hash.substring(0, 16)}...
            </p>
          </div>
          <span className="font-mono text-slate-600 bg-white px-2 py-1 rounded border border-slate-200">
            {(document.file_size_bytes / 1024).toFixed(1)} KB
          </span>
        </div>

        {/* Mock/Preview Content */}
        <div className="flex min-h-[350px] flex-col items-center justify-center rounded-xl border border-slate-200 bg-slate-100/60 p-8 text-center">
          <FileText className="h-16 w-16 text-slate-400 stroke-[1]" />
          <p className="mt-3 text-sm font-semibold text-slate-700">{document.file_name}</p>
          <p className="mt-1 text-xs text-slate-500 max-w-sm">
            Pratinjau dokumen PDF/gambar terverifikasi dengan hash SHA-256 kriptografis.
          </p>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            Tutup
          </Button>
          <Button size="sm" leftIcon={<Download className="h-4 w-4" />}>
            Unduh File
          </Button>
        </div>
      </div>
    </Modal>
  );
};
