import React, { useState } from 'react';
import { RotateCcw, AlertTriangle } from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

export interface TransactionReversalModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
  transactionCode: string;
  isLoading?: boolean;
}

export const TransactionReversalModal: React.FC<TransactionReversalModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  transactionCode,
  isLoading = false,
}) => {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setError('Alasan pembatalan / koreksi wajib diisi.');
      return;
    }
    setError(null);
    await onConfirm(reason);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="md"
      title={`Batalkan Transaksi — ${transactionCode}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
          <p className="leading-relaxed">
            Transaksi yang sudah diposting tidak akan dihapus dari basis data, melainkan dibuatkan transaksi pembalik (Reversal) kompensasi untuk menjaga integritas jejak audit akuntansi.
          </p>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
            Alasan Pembatalan / Koreksi *
          </label>
          <Input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Contoh: Salah input nominal nota / Salah pilih proyek"
            error={error || undefined}
            required
          />
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Batal
          </Button>
          <Button
            type="submit"
            variant="danger"
            size="sm"
            isLoading={isLoading}
            leftIcon={<RotateCcw className="h-4 w-4" />}
          >
            Konfirmasi Reversal
          </Button>
        </div>
      </form>
    </Modal>
  );
};
