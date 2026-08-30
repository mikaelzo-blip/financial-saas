import React from 'react';
import { CheckCircle2, XCircle, ShieldAlert } from 'lucide-react';
import { useAuth } from '../../../store/AuthContext';
import { Button } from '../../../components/ui/Button';

export interface ApprovalActionControlsProps {
  onApprove: () => void;
  onReject: () => void;
  isLoading?: boolean;
  unresolvedFlagsCount: number;
}

export const ApprovalActionControls: React.FC<ApprovalActionControlsProps> = ({
  onApprove,
  onReject,
  isLoading = false,
  unresolvedFlagsCount,
}) => {
  const { hasRole, user } = useAuth();
  const isManagerOrAdmin = hasRole(['ADMIN', 'MANAGER']);

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div>
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
          Aksi Keputusan Manajer
        </h4>
        <p className="text-[11px] text-slate-500 mt-0.5">
          {unresolvedFlagsCount > 0
            ? `Terdapat ${unresolvedFlagsCount} flag review yang masih belum terselesaikan.`
            : 'Seluruh flag telah diselesaikan. Siap diposting ke buku besar.'}
        </p>
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          leftIcon={<XCircle className="h-4 w-4 text-rose-500" />}
          onClick={onReject}
          disabled={isLoading}
        >
          Tolak Transaksi
        </Button>

        {isManagerOrAdmin ? (
          <Button
            variant="success"
            size="sm"
            leftIcon={<CheckCircle2 className="h-4 w-4" />}
            onClick={onApprove}
            isLoading={isLoading}
          >
            Setujui & Posting Transaksi
          </Button>
        ) : (
          <div className="flex items-center gap-1.5 rounded-lg bg-amber-100 px-3 py-1.5 text-xs text-amber-800 font-medium">
            <ShieldAlert className="h-4 w-4" />
            <span>Memerlukan Approval Manajer (Peran Anda: {user?.role})</span>
          </div>
        )}
      </div>
    </div>
  );
};
