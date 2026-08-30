import React, { useState } from 'react';
import { CheckSquare } from 'lucide-react';
import { ReviewFlagResponse } from '../../../types/api';
import { reviewApi } from '../../../api/review';
import { Modal } from '../../../components/ui/Modal';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { StatusBadge } from '../../../components/ui/StatusBadge';
import { useToast } from '../../../components/feedback/Toast';

export interface ResolveFlagModalProps {
  flag: ReviewFlagResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ResolveFlagModal: React.FC<ResolveFlagModalProps> = ({
  flag,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { success, error } = useToast();
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!flag) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolutionNotes.trim()) {
      error('Catatan resolusi/penjelasan wajib diisi.');
      return;
    }

    setIsLoading(true);
    try {
      await reviewApi.resolveFlag(flag.id, {
        resolution_notes: resolutionNotes,
      });
      success(`Flag ${flag.flag} berhasil diselesaikan.`);
      onSuccess();
      onClose();
    } catch (err: any) {
      error(err.response?.data?.detail || 'Gagal menyelesaikan flag.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="md"
      title="Penyelesaian Flag Ambiguity Review"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 space-y-2">
          <div className="flex items-center gap-2">
            <StatusBadge status={flag.flag} size="sm" />
            <span className="font-semibold text-amber-800">Tingkat: {flag.severity}</span>
          </div>
          <p className="font-medium text-slate-800">{flag.message}</p>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
            Catatan Penjelasan & Rekonsiliasi *
          </label>
          <Input
            value={resolutionNotes}
            onChange={(e) => setResolutionNotes(e.target.value)}
            placeholder="Jelaskan alasan resolusi (contoh: Nota telah dicocokkan dengan fisik SPK lapangan)..."
            required
          />
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Batal
          </Button>
          <Button
            type="submit"
            size="sm"
            variant="success"
            isLoading={isLoading}
            leftIcon={<CheckSquare className="h-4 w-4" />}
          >
            Tandai Flag Selesai
          </Button>
        </div>
      </form>
    </Modal>
  );
};
