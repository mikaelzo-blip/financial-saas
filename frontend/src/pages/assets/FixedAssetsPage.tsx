import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Landmark,
  Plus,
  Play,
  Info,
  Trash2,
  HelpCircle
} from 'lucide-react';
import {
  fixedAssetsApi,
  FixedAsset,
  FixedAssetCreateInput,
  AssetStatus
} from '../../api/fixedAssets';
import { formatIDR, formatDate } from '../../utils/formatters';
import { Card } from '../../components/ui/Card';
import { DataTable, Column } from '../../components/tables/DataTable';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { useToast } from '../../components/feedback/Toast';

const CATEGORY_OPTIONS = [
  { value: 'KOMPUTER', label: 'Komputer & Laptop (Masa Manfaat Standar: 4 Tahun / 48 Bulan)', defaultMonths: 48 },
  { value: 'PERALATAN_KANTOR', label: 'Peralatan Kantor (Masa Manfaat Standar: 4 Tahun / 48 Bulan)', defaultMonths: 48 },
  { value: 'PERALATAN_PROYEK', label: 'Peralatan Proyek Ringan (Masa Manfaat Standar: 4 Tahun / 48 Bulan)', defaultMonths: 48 },
  { value: 'ALAT_BERAT', label: 'Alat Berat Proyek (Masa Manfaat Standar: 8 Tahun / 96 Bulan)', defaultMonths: 96 },
  { value: 'KENDARAAN', label: 'Kendaraan Operasional (Masa Manfaat Standar: 8 Tahun / 96 Bulan)', defaultMonths: 96 },
  { value: 'BANGUNAN', label: 'Bangunan Permanen (Masa Manfaat Standar: 20 Tahun / 240 Bulan)', defaultMonths: 240 },
];

export const FixedAssetsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [batchDeprModalOpen, setBatchDeprModalOpen] = useState(false);

  // Form state for creating asset
  const [assetCode, setAssetCode] = useState('');
  const [assetName, setAssetName] = useState('');
  const [category, setCategory] = useState(CATEGORY_OPTIONS[0].value);
  const [purchaseDate, setPurchaseDate] = useState(new Date().toISOString().split('T')[0]);
  const [availableDate, setAvailableDate] = useState(new Date().toISOString().split('T')[0]);
  const [purchaseCost, setPurchaseCost] = useState('');
  const [salvageValue, setSalvageValue] = useState('0');
  const [usefulLifeMonths, setUsefulLifeMonths] = useState(CATEGORY_OPTIONS[0].defaultMonths.toString());
  const [overrideReason, setOverrideReason] = useState('');

  // Batch depreciation date
  const [deprPeriodDate, setDeprPeriodDate] = useState(new Date().toISOString().split('T')[0]);

  // Fetch list of fixed assets
  const { data: assets = [], isLoading } = useQuery({
    queryKey: ['fixed-assets'],
    queryFn: () => fixedAssetsApi.getAssets(),
  });

  // Calculate totals
  const totalCost = assets.reduce((sum, a) => sum + parseFloat(a.purchase_cost || '0'), 0);
  const totalAccDepr = assets.reduce((sum, a) => sum + parseFloat(a.accumulated_depreciation || '0'), 0);
  const totalNetBookValue = assets.reduce((sum, a) => sum + parseFloat(a.net_book_value || '0'), 0);

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: FixedAssetCreateInput) => fixedAssetsApi.createAsset(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fixed-assets'] });
      showToast('Aset Tetap berhasil didaftarkan.', 'success');
      setCreateModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      showToast(err.response?.data?.detail || 'Gagal mendaftarkan aset.', 'error');
    },
  });

  // Batch depreciation mutation
  const batchDeprMutation = useMutation({
    mutationFn: (periodDate: string) => fixedAssetsApi.depreciateBatch(periodDate),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['fixed-assets'] });
      showToast(
        `Penyusutan berhasil diposting untuk ${res.total_assets_processed} aset (Total: ${formatIDR(res.total_depreciation_amount)}).`,
        'success'
      );
      setBatchDeprModalOpen(false);
    },
    onError: (err: any) => {
      showToast(err.response?.data?.detail || 'Gagal menjalankan penyusutan.', 'error');
    },
  });

  // Single asset depreciation mutation
  const singleDeprMutation = useMutation({
    mutationFn: ({ id, date }: { id: string; date: string }) =>
      fixedAssetsApi.depreciateSingleAsset(id, date),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['fixed-assets'] });
      showToast(
        `Penyusutan ${res.asset_name} berhasil diposting (${formatIDR(res.depreciation_amount)}). No Jurnal: ${res.journal_entry_number || '-'}`,
        'success'
      );
    },
    onError: (err: any) => {
      showToast(err.response?.data?.detail || 'Gagal memposting penyusutan aset.', 'error');
    },
  });

  // Dispose mutation
  const disposeMutation = useMutation({
    mutationFn: (id: string) => fixedAssetsApi.disposeAsset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fixed-assets'] });
      showToast('Status aset berhasil diperbarui menjadi DIJUAL/DIHAPUS.', 'info');
    },
    onError: (err: any) => {
      showToast(err.response?.data?.detail || 'Gagal memperbarui status aset.', 'error');
    },
  });

  const resetForm = () => {
    setAssetCode('');
    setAssetName('');
    setCategory(CATEGORY_OPTIONS[0].value);
    setUsefulLifeMonths(CATEGORY_OPTIONS[0].defaultMonths.toString());
    setPurchaseCost('');
    setSalvageValue('0');
    setOverrideReason('');
  };

  const handleCategoryChange = (val: string) => {
    setCategory(val);
    const found = CATEGORY_OPTIONS.find((c) => c.value === val);
    if (found) {
      setUsefulLifeMonths(found.defaultMonths.toString());
    }
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!assetCode || !assetName || !purchaseCost) {
      showToast('Mohon lengkapi kode, nama, dan harga perolehan aset.', 'error');
      return;
    }
    createMutation.mutate({
      asset_code: assetCode.trim().toUpperCase(),
      asset_name: assetName.trim(),
      asset_category: category,
      purchase_date: purchaseDate,
      available_for_use_date: availableDate || purchaseDate,
      purchase_cost: purchaseCost,
      salvage_value: salvageValue || '0.00',
      useful_life_months: parseInt(usefulLifeMonths, 10),
      override_reason: overrideReason || undefined,
    });
  };

  const getStatusBadgeVariant = (status: AssetStatus) => {
    switch (status) {
      case 'ACTIVE':
        return 'success';
      case 'DRAFT':
        return 'neutral';
      case 'FULLY_DEPRECIATED':
        return 'warning';
      case 'DISPOSED':
      case 'WRITTEN_OFF':
        return 'danger';
      default:
        return 'neutral';
    }
  };

  const getStatusLabel = (status: AssetStatus) => {
    switch (status) {
      case 'ACTIVE':
        return 'Aktif';
      case 'DRAFT':
        return 'Draft';
      case 'FULLY_DEPRECIATED':
        return 'Selesai Disusutkan';
      case 'DISPOSED':
        return 'Dijual / Dihapus';
      case 'WRITTEN_OFF':
        return 'Dihapusbukukan';
      default:
        return status;
    }
  };

  const columns: Column<FixedAsset>[] = [
    {
      key: 'asset_code',
      header: 'Kode Aset',
      sortable: true,
      render: (a) => (
        <span className="font-mono text-xs font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-md">
          {a.asset_code}
        </span>
      ),
    },
    {
      key: 'asset_name',
      header: 'Nama Aset',
      sortable: true,
      render: (a) => (
        <div>
          <p className="font-semibold text-slate-900">{a.asset_name}</p>
          <p className="text-[11px] text-slate-500">{a.asset_category}</p>
        </div>
      ),
    },
    {
      key: 'purchase_date',
      header: 'Tanggal Pembelian',
      sortable: true,
      render: (a) => <span className="text-xs text-slate-600">{formatDate(a.purchase_date)}</span>,
    },
    {
      key: 'effective_available_date',
      header: 'Tanggal Mulai Digunakan',
      render: (a) => (
        <span className="text-xs text-slate-600">
          {formatDate(a.available_for_use_date || a.purchase_date)}
        </span>
      ),
    },
    {
      key: 'purchase_cost',
      header: 'Harga Perolehan',
      align: 'right',
      sortable: true,
      render: (a) => (
        <span className="font-mono text-xs font-semibold text-slate-900">
          {formatIDR(a.purchase_cost)}
        </span>
      ),
    },
    {
      key: 'useful_life_months',
      header: 'Masa Manfaat',
      align: 'center',
      render: (a) => (
        <span className="text-xs text-slate-700">
          {a.useful_life_months} bulan ({(a.useful_life_months / 12).toLocaleString('id-ID', { maximumFractionDigits: 1 })} tahun)
        </span>
      ),
    },
    {
      key: 'accumulated_depreciation',
      header: 'Akumulasi Penyusutan',
      align: 'right',
      render: (a) => (
        <span className="font-mono text-xs text-amber-700">
          {formatIDR(a.accumulated_depreciation)}
        </span>
      ),
    },
    {
      key: 'net_book_value',
      header: 'Nilai Buku',
      align: 'right',
      render: (a) => (
        <span className="font-mono text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
          {formatIDR(a.net_book_value)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      align: 'center',
      render: (a) => (
        <Badge variant={getStatusBadgeVariant(a.status)} size="sm">
          {getStatusLabel(a.status)}
        </Badge>
      ),
    },
    {
      key: 'id',
      header: 'Aksi',
      align: 'right',
      render: (a) => (
        <div className="flex items-center justify-end gap-1.5">
          {a.status === 'ACTIVE' && parseFloat(a.net_book_value) > 0 && (
            <button
              onClick={() => {
                const today = new Date().toISOString().split('T')[0];
                singleDeprMutation.mutate({ id: a.id, date: today });
              }}
              disabled={singleDeprMutation.isPending}
              className="px-2 py-1 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded transition-colors"
              title="Susutkan bulan ini"
            >
              Susutkan
            </button>
          )}
          {a.status === 'ACTIVE' && (
            <button
              onClick={() => {
                if (window.confirm(`Yakin ingin menandai aset "${a.asset_name}" sebagai Dijual / Dihapus?`)) {
                  disposeMutation.mutate(a.id);
                }
              }}
              className="p-1 text-slate-400 hover:text-red-600 rounded transition-colors"
              title="Hapus / Jual Aset"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Landmark className="h-6 w-6 text-blue-600" />
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Daftar Aset Tetap</h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Pencatatan barang modal dan penyusutan garis lurus yang berorientasi pada SAK EP.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setBatchDeprModalOpen(true)}
            className="flex items-center gap-1.5"
          >
            <Play className="h-4 w-4 text-emerald-600" />
            Jalankan Penyusutan Bulanan
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setCreateModalOpen(true)}
            className="flex items-center gap-1.5"
          >
            <Plus className="h-4 w-4" />
            Tambah Aset Baru
          </Button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 border-slate-200">
          <p className="text-xs text-slate-500 font-medium">Total Aset Terdaftar</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{assets.length}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {assets.filter((a) => a.status === 'ACTIVE').length} Aktif
          </p>
        </Card>

        <Card className="p-4 border-slate-200">
          <p className="text-xs text-slate-500 font-medium">Total Harga Perolehan</p>
          <p className="text-xl font-bold text-slate-900 mt-1 font-mono">{formatIDR(totalCost)}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Akun 1501 Aset Tetap</p>
        </Card>

        <Card className="p-4 border-slate-200">
          <p className="text-xs text-slate-500 font-medium">Akumulasi Penyusutan</p>
          <p className="text-xl font-bold text-amber-700 mt-1 font-mono">{formatIDR(totalAccDepr)}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">Akun 1502 Kontra Aset</p>
        </Card>

        <Card className="p-4 border-slate-200 bg-emerald-50/50 border-emerald-100">
          <p className="text-xs text-emerald-700 font-medium">Total Nilai Buku Bersih</p>
          <p className="text-xl font-bold text-emerald-800 mt-1 font-mono">{formatIDR(totalNetBookValue)}</p>
          <p className="text-[11px] text-emerald-600 mt-0.5">Harga Perolehan - Akumulasi</p>
        </Card>
      </div>

      {/* Capitalization Policy Banner */}
      <Card className="p-4 bg-blue-50/60 border-blue-200 flex items-start gap-3">
        <Info className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
        <div className="text-xs text-blue-900 space-y-1">
          <p className="font-semibold">Pedoman Kapitalisasi Aset Tetap Perusahaan:</p>
          <p className="text-blue-800 leading-relaxed">
            Barang modal dengan harga perolehan <strong>minimal Rp5.000.000</strong> dan masa manfaat <strong>lebih dari 12 bulan</strong> dicatat sebagai aset tetap.
            Pembelian di bawah Rp5.000.000 dibebankan langsung pada periode berjalan (Harga Pokok Proyek / Beban Operasional).
            Penyusutan mulai dihitung saat aset <strong>mulai digunakan</strong>.
          </p>
        </div>
      </Card>

      {/* Main Table */}
      <Card className="overflow-hidden border-slate-200">
        <DataTable
          data={assets}
          columns={columns}
          keyExtractor={(a) => a.id}
          isLoading={isLoading}
          emptyTitle="Belum ada aset tetap yang terdaftar"
          emptyDescription="Daftarkan aset tetap modal perusahaan untuk memulai pencatatan penyusutan."
        />
      </Card>

      {/* Create Modal */}
      {createModalOpen && (
        <Modal
          isOpen={createModalOpen}
          onClose={() => setCreateModalOpen(false)}
          title="Tambah Aset Tetap Baru"
        >
          <form onSubmit={handleCreateSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Kode Aset *
                </label>
                <Input
                  type="text"
                  placeholder="Misal: AST-LPT-001"
                  value={assetCode}
                  onChange={(e) => setAssetCode(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Kategori Aset *
                </label>
                <select
                  value={category}
                  onChange={(e) => handleCategoryChange(e.target.value)}
                  className="w-full text-xs rounded-md border border-slate-300 py-2 px-3 bg-white text-slate-800"
                >
                  {CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Nama Aset *
              </label>
              <Input
                type="text"
                placeholder="Misal: Laptop Asus Zenbook untuk Site Engineer"
                value={assetName}
                onChange={(e) => setAssetName(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Tanggal Pembelian *
                </label>
                <Input
                  type="date"
                  value={purchaseDate}
                  onChange={(e) => setPurchaseDate(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Tanggal Mulai Digunakan *
                </label>
                <Input
                  type="date"
                  value={availableDate}
                  onChange={(e) => setAvailableDate(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Harga Perolehan (Rp) *
                </label>
                <Input
                  type="number"
                  step="0.01"
                  placeholder="Contoh: 15000000"
                  value={purchaseCost}
                  onChange={(e) => setPurchaseCost(e.target.value)}
                  required
                />
                {purchaseCost && parseFloat(purchaseCost) < 5000000 && (
                  <p className="text-[11px] text-amber-600 mt-1 flex items-center gap-1">
                    <HelpCircle className="h-3 w-3" /> Di bawah Rp 5.000.000: pertimbangkan langsung dibebankan.
                  </p>
                )}
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Nilai Residu (Rp)
                </label>
                <Input
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={salvageValue}
                  onChange={(e) => setSalvageValue(e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Masa Manfaat (Bulan) *
                </label>
                <Input
                  type="number"
                  value={usefulLifeMonths}
                  onChange={(e) => setUsefulLifeMonths(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Metode Penyusutan
                </label>
                <input
                  type="text"
                  value="Garis Lurus (Straight Line)"
                  disabled
                  className="w-full text-xs rounded-md border border-slate-200 py-2 px-3 bg-slate-100 text-slate-500 cursor-not-allowed"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setCreateModalOpen(false)}
              >
                Batal
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Menyimpan...' : 'Daftarkan Aset'}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Batch Depreciation Modal */}
      {batchDeprModalOpen && (
        <Modal
          isOpen={batchDeprModalOpen}
          onClose={() => setBatchDeprModalOpen(false)}
          title="Jalankan Penyusutan Bulanan"
        >
          <div className="space-y-4">
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-600 space-y-1">
              <p className="font-semibold text-slate-800">Prinsip Akuntansi Penyusutan:</p>
              <p>
                Sistem akan menghitung penyusutan garis lurus untuk seluruh aset aktif yang telah mulai digunakan pada atau sebelum tanggal yang dipilih.
              </p>
              <p className="text-[11px] text-slate-500">
                Jurnal yang terbentuk: <strong>Debit Beban Penyusutan (6105)</strong> / <strong>Kredit Akumulasi Penyusutan (1502)</strong>.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Pilih Tanggal Periode Penyusutan *
              </label>
              <Input
                type="date"
                value={deprPeriodDate}
                onChange={(e) => setDeprPeriodDate(e.target.value)}
                required
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setBatchDeprModalOpen(false)}
              >
                Batal
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => batchDeprMutation.mutate(deprPeriodDate)}
                disabled={batchDeprMutation.isPending}
                className="flex items-center gap-1.5"
              >
                <Play className="h-4 w-4" />
                {batchDeprMutation.isPending ? 'Memposting...' : 'Jalankan Sekarang'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
