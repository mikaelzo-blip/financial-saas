import React from 'react';
import { AlertTriangle, ShieldCheck } from 'lucide-react';
import { Card } from '../ui/Card';

interface IntegrityAlertBannerProps {
  isBalanced: boolean;
  difference?: number | string;
  message?: string;
}

export const IntegrityAlertBanner: React.FC<IntegrityAlertBannerProps> = ({
  isBalanced,
  difference,
  message
}) => {
  if (isBalanced) {
    return (
      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-center justify-between text-emerald-800 mb-6">
        <div className="flex items-center space-x-3">
          <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0" />
          <span className="text-sm font-medium">
            Integritas Keuangan Valid — Total Aset seimbang dengan Total Kewajiban & Ekuitas (Rp 0,00 selisih).
          </span>
        </div>
      </div>
    );
  }

  return (
    <Card className="bg-red-50 border-red-300 mb-6 p-4">
      <div className="flex items-start space-x-3">
        <AlertTriangle className="w-6 h-6 text-red-600 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-bold text-red-900">
            PERINGATAN INTEGRITAS LAPORAN KEUANGAN (INTEGRITY_ERROR)
          </h4>
          <p className="text-xs text-red-700 mt-1">
            {message || 'Laporan keuangan tidak memenuhi persamaan dasar akuntansi (Aset != Kewajiban + Ekuitas).'}
            {difference && (
              <span className="font-mono font-bold block mt-1">
                Selisih: Rp {Number(difference).toLocaleString('id-ID', { minimumFractionDigits: 2 })}
              </span>
            )}
          </p>
          <p className="text-xs text-red-600 mt-2 italic">
            Sistem melarang penyeimbang otomatis (plug adjustment). Harap periksa jurnal penyesuaian yang belum seimbang.
          </p>
        </div>
      </div>
    </Card>
  );
};
