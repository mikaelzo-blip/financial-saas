import React, { useState, useEffect } from 'react';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { StatusBadge } from '../../../components/ui/StatusBadge';
import {
  AccountingPeriod,
  getAccountingPeriods,
  createAccountingPeriod,
  updateAccountingPeriodStatus
} from '../../../api/periods';

export const AccountingPeriodTab: React.FC = () => {
  const [periods, setPeriods] = useState<AccountingPeriod[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [periodName, setPeriodName] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [createSubmitting, setCreateSubmitting] = useState(false);

  // Modal / reason state
  const [selectedPeriod, setSelectedPeriod] = useState<AccountingPeriod | null>(null);
  const [targetStatus, setTargetStatus] = useState<'OPEN' | 'SOFT_CLOSED' | 'CLOSED'>('OPEN');
  const [reason, setReason] = useState('');
  const [isActionModalOpen, setIsActionModalOpen] = useState(false);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  const fetchPeriods = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getAccountingPeriods();
      setPeriods(data);
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Gagal mengambil data periode akuntansi.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPeriods();
  }, []);

  const handleCreatePeriod = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!periodName || !startDate || !endDate) {
      setError('Semua kolom periode akuntansi wajib diisi.');
      return;
    }
    try {
      setCreateSubmitting(true);
      setError(null);
      await createAccountingPeriod({
        period_name: periodName,
        start_date: startDate,
        end_date: endDate
      });
      setPeriodName('');
      setStartDate('');
      setEndDate('');
      await fetchPeriods();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Gagal membuat periode akuntansi.');
    } finally {
      setCreateSubmitting(false);
    }
  };

  const handleOpenAction = (period: AccountingPeriod, status: 'OPEN' | 'SOFT_CLOSED' | 'CLOSED') => {
    setSelectedPeriod(period);
    setTargetStatus(status);
    setReason('');
    setIsActionModalOpen(true);
  };

  const handleConfirmAction = async () => {
    if (!selectedPeriod) return;
    if (
      (selectedPeriod.status === 'CLOSED' || selectedPeriod.status === 'SOFT_CLOSED') &&
      targetStatus === 'OPEN' &&
      !reason.trim()
    ) {
      setError('Alasan pembukaan kembali periode wajib diisi.');
      return;
    }

    try {
      setActionSubmitting(true);
      setError(null);
      await updateAccountingPeriodStatus(selectedPeriod.id, {
        status: targetStatus,
        reason: reason.trim() || undefined
      });
      setIsActionModalOpen(false);
      setSelectedPeriod(null);
      await fetchPeriods();
    } catch (err: any) {
      setError(err?.response?.data?.message || 'Gagal memperbarui status periode.');
    } finally {
      setActionSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card title="Tambah Periode Akuntansi Baru">
        <form onSubmit={handleCreatePeriod} className="space-y-4 max-w-xl">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Input
              label="Nama Periode (contoh: 2026-01)"
              value={periodName}
              onChange={(e) => setPeriodName(e.target.value)}
              placeholder="2026-01"
              required
            />
            <Input
              label="Tanggal Mulai"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
            />
            <Input
              label="Tanggal Selesai"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
            />
          </div>
          <div className="flex justify-end">
            <Button type="submit" disabled={createSubmitting} size="sm">
              {createSubmitting ? 'Menyimpan...' : 'Buat Periode'}
            </Button>
          </div>
        </form>
      </Card>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg">
          {error}
        </div>
      )}

      <Card title="Daftar Periode Akuntansi">
        {loading ? (
          <p className="text-xs text-slate-500 py-4">Memuat daftar periode...</p>
        ) : periods.length === 0 ? (
          <p className="text-xs text-slate-500 py-4">Belum ada periode akuntansi yang dikonfigurasi.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Nama Periode</th>
                  <th className="py-2.5 px-3">Rentang Tanggal</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Ditutup Pada</th>
                  <th className="py-2.5 px-3 text-right">Aksi Manajemen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {periods.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="py-3 px-3 font-semibold text-slate-900">{p.period_name}</td>
                    <td className="py-3 px-3 font-mono text-slate-600">
                      {p.start_date} s/d {p.end_date}
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={p.status} size="sm" />
                    </td>
                    <td className="py-3 px-3 text-slate-500">
                      {p.closed_at ? new Date(p.closed_at).toLocaleString('id-ID') : '-'}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      {p.status === 'OPEN' && (
                        <>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleOpenAction(p, 'SOFT_CLOSED')}
                          >
                            Soft Close
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => handleOpenAction(p, 'CLOSED')}
                          >
                            Tutup (Hard Close)
                          </Button>
                        </>
                      )}
                      {p.status === 'SOFT_CLOSED' && (
                        <>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleOpenAction(p, 'OPEN')}
                          >
                            Buka Kembali
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            onClick={() => handleOpenAction(p, 'CLOSED')}
                          >
                            Tutup (Hard Close)
                          </Button>
                        </>
                      )}
                      {p.status === 'CLOSED' && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleOpenAction(p, 'OPEN')}
                        >
                          Buka Kembali (Reopen)
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Reopen / Status Modal */}
      {isActionModalOpen && selectedPeriod && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md bg-white rounded-xl shadow-xl p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900">
              Konfirmasi Perubahan Status: {selectedPeriod.period_name}
            </h3>
            <p className="text-xs text-slate-600">
              Status akan diubah dari <strong>{selectedPeriod.status}</strong> menjadi{' '}
              <strong>{targetStatus}</strong>.
            </p>

            {targetStatus === 'OPEN' && selectedPeriod.status !== 'OPEN' && (
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700">
                  Alasan Pembukaan Kembali (Audit Reason) *
                </label>
                <textarea
                  className="w-full text-xs p-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-blue-500 focus:outline-none"
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Jelaskan alasan pembukaan kembali periode akuntansi ini..."
                  required
                />
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setIsActionModalOpen(false);
                  setSelectedPeriod(null);
                }}
              >
                Batal
              </Button>
              <Button
                size="sm"
                disabled={actionSubmitting}
                onClick={handleConfirmAction}
              >
                {actionSubmitting ? 'Memproses...' : 'Konfirmasi'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
