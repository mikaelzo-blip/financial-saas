import React, { useState } from 'react';
import { Card } from '../../components/ui/Card';
import { useAuth } from '../../store/AuthContext';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Input } from '../../components/ui/Input';

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'profile' | 'organization' | 'audit'>('profile');

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">
          Pengaturan Sistem & Profil
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Kelola profil pengguna, konfigurasi perusahaan kontraktor, dan tinjau log audit aktivitas.
        </p>
      </div>

      <div className="flex border-b border-slate-200 gap-6">
        <button
          onClick={() => setActiveTab('profile')}
          className={`pb-3 text-xs font-semibold uppercase transition-colors cursor-pointer ${
            activeTab === 'profile'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          Profil Pengguna
        </button>
        <button
          onClick={() => setActiveTab('organization')}
          className={`pb-3 text-xs font-semibold uppercase transition-colors cursor-pointer ${
            activeTab === 'organization'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          Profil Perusahaan (Tenant)
        </button>
        <button
          onClick={() => setActiveTab('audit')}
          className={`pb-3 text-xs font-semibold uppercase transition-colors cursor-pointer ${
            activeTab === 'audit'
              ? 'border-b-2 border-blue-600 text-blue-600'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          Jejak Audit Aktivitas
        </button>
      </div>

      {activeTab === 'profile' && (
        <Card title="Informasi Akun Anda">
          <div className="max-w-xl space-y-4">
            <div className="flex items-center gap-3 pb-4 border-b border-slate-100">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white font-bold text-lg">
                {user?.fullName?.charAt(0) || 'U'}
              </div>
              <div>
                <p className="font-semibold text-slate-900">{user?.fullName}</p>
                <div className="flex items-center gap-2 mt-1">
                  <StatusBadge status={user?.role || 'OPERATOR'} size="sm" />
                  <span className="text-xs text-slate-400 font-mono">{user?.email}</span>
                </div>
              </div>
            </div>

            <Input label="Nama Lengkap" value={user?.fullName || ''} disabled />
            <Input label="Alamat Email" value={user?.email || ''} disabled />
            <Input label="ID Organisasi (Tenant)" value={user?.organizationId || ''} disabled />
          </div>
        </Card>
      )}

      {activeTab === 'organization' && (
        <Card title="Identitas Perusahaan Kontraktor">
          <div className="max-w-xl space-y-4">
            <Input
              label="Nama Perusahaan"
              value={user?.organizationName || 'PT Kontraktor Utama Indonesia'}
              disabled
            />
            <Input label="Sektor Usaha" value="Konstruksi & Sipil" disabled />
            <Input label="Mata Uang Pembukuan" value="IDR (Rupiah Indonesia)" disabled />
            <Input label="Standar Akuntansi" value="SAK ETAP / Standar Jasa Konstruksi" disabled />
          </div>
        </Card>
      )}

      {activeTab === 'audit' && (
        <Card title="Log Jejak Audit Kriptografis (Audit Trail)">
          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div>
                <p className="font-semibold text-slate-900">Sesi Login Pengguna Berhasil</p>
                <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                  Aktor: {user?.email} • Peran: {user?.role}
                </p>
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Hari ini, Sesi Aktif</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div>
                <p className="font-semibold text-slate-900">Verifikasi Integritas Sub-Ledger AR/AP</p>
                <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                  Sistem otomatis backend • Status: Seimbang & Sesuai Jurnal
                </p>
              </div>
              <span className="text-[10px] text-emerald-600 font-semibold font-mono">TERVERIFIKASI</span>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};
