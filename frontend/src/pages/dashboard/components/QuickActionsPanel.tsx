import React from 'react';
import { useNavigate } from 'react-router-dom';
import { PlusCircle, Building2, UploadCloud, AlertTriangle } from 'lucide-react';
import { Card } from '../../../components/ui/Card';

export const QuickActionsPanel: React.FC<{ reviewCount?: number }> = ({ reviewCount = 0 }) => {
  const navigate = useNavigate();

  return (
    <Card title="Aksi Cepat Operasional">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <button
          onClick={() => navigate('/transactions/new')}
          className="flex flex-col items-center justify-center p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-blue-50/50 hover:border-blue-300 transition-all text-center group cursor-pointer"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-600 group-hover:scale-105 transition-transform mb-2">
            <PlusCircle className="h-5 w-5" />
          </div>
          <span className="text-xs font-semibold text-slate-800">Catat Transaksi</span>
          <span className="text-[10px] text-slate-500 mt-0.5">Biaya / Nota Lapangan</span>
        </button>

        <button
          onClick={() => navigate('/projects/new')}
          className="flex flex-col items-center justify-center p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-emerald-50/50 hover:border-emerald-300 transition-all text-center group cursor-pointer"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-600 group-hover:scale-105 transition-transform mb-2">
            <Building2 className="h-5 w-5" />
          </div>
          <span className="text-xs font-semibold text-slate-800">Proyek Baru</span>
          <span className="text-[10px] text-slate-500 mt-0.5">Daftarkan SPK</span>
        </button>

        <button
          onClick={() => navigate('/documents')}
          className="flex flex-col items-center justify-center p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-purple-50/50 hover:border-purple-300 transition-all text-center group cursor-pointer"
        >
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 text-purple-600 group-hover:scale-105 transition-transform mb-2">
            <UploadCloud className="h-5 w-5" />
          </div>
          <span className="text-xs font-semibold text-slate-800">Unggah Bukti</span>
          <span className="text-[10px] text-slate-500 mt-0.5">Arsip Nota & SPK</span>
        </button>

        <button
          onClick={() => navigate('/review-queue')}
          className="flex flex-col items-center justify-center p-4 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-amber-50/50 hover:border-amber-300 transition-all text-center group cursor-pointer relative"
        >
          {reviewCount > 0 && (
            <span className="absolute top-2 right-2 flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-white shadow-xs">
              {reviewCount}
            </span>
          )}
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-amber-600 group-hover:scale-105 transition-transform mb-2">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <span className="text-xs font-semibold text-slate-800">Antrean Review</span>
          <span className="text-[10px] text-slate-500 mt-0.5">Periksa Ambigu</span>
        </button>
      </div>
    </Card>
  );
};
