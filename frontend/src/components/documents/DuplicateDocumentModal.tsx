import React from 'react';
import { ShieldAlert, FileText } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';

export interface DuplicateDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  message?: string;
  originalDocumentId?: string;
}

export const DuplicateDocumentModal: React.FC<DuplicateDocumentModalProps> = ({
  isOpen,
  onClose,
  message = 'Dokumen fisik ini sudah pernah diunggah ke sistem sebelumnya. Sistem mencegah duplikasi bukti transaksi secara otomatis.',
}) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="md" title="Peringatan Duplikasi Dokumen">
      <div className="space-y-4 text-center p-2">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-600">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <div>
          <h4 className="text-base font-bold text-slate-900">Dokumen Sudah Ada (SHA-256 Identik)</h4>
          <p className="mt-2 text-xs text-slate-600 leading-relaxed">{message}</p>
        </div>

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-left">
          <div className="flex items-start gap-2.5">
            <FileText className="h-4 w-4 text-amber-700 shrink-0 mt-0.5" />
            <p className="text-[11px] text-amber-900 leading-normal">
              Sesuai prinsip konstitusi SaaS, bukti yang sama tidak boleh didaftarkan dua kali untuk mencegah pengeluaran fiktif/ganda.
            </p>
          </div>
        </div>

        <div className="pt-3">
          <Button variant="secondary" size="sm" onClick={onClose} className="w-full">
            Saya Mengerti
          </Button>
        </div>
      </div>
    </Modal>
  );
};
