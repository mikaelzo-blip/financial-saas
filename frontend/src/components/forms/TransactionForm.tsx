import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Trash2, Split, AlertCircle } from 'lucide-react';
import { projectsApi } from '../../api/projects';
import { masterApi } from '../../api/master';
import { TransactionCreateInput, TransactionAllocationInput } from '../../api/transactions';
import { TransactionType, CostCategory, DocumentResponse } from '../../types/api';
import { validateAllocationSum } from '../../utils/transactionValidation';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { FileDropzone } from './FileDropzone';

export interface TransactionFormProps {
  onSubmit: (data: TransactionCreateInput) => Promise<void>;
  isLoading?: boolean;
  onCancel?: () => void;
}

export const TransactionForm: React.FC<TransactionFormProps> = ({
  onSubmit,
  isLoading = false,
  onCancel,
}) => {
  const [transactionType, setTransactionType] = useState<TransactionType>('DIRECT_PURCHASE');
  const [transactionDate, setTransactionDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [counterpartyId, setCounterpartyId] = useState('');
  const [paymentAccountId, setPaymentAccountId] = useState('');
  const [referenceNo, setReferenceNo] = useState('');
  const [documentIds, setDocumentIds] = useState<string[]>([]);

  // Single-project mode (default)
  const [projectId, setProjectId] = useState('');
  const [costCategory, setCostCategory] = useState<CostCategory>('MAT');

  // Split-allocation mode
  const [isSplitMode, setIsSplitMode] = useState(false);
  const [allocations, setAllocations] = useState<TransactionAllocationInput[]>([
    { project_id: '', cost_category: 'MAT', amount: '' },
    { project_id: '', cost_category: 'MAT', amount: '' },
  ]);

  const [formError, setFormError] = useState<string | null>(null);

  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list(),
  });

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: masterApi.getCustomers,
  });

  const { data: vendors = [] } = useQuery({
    queryKey: ['vendors'],
    queryFn: masterApi.getVendors,
  });

  const { data: paymentAccounts = [] } = useQuery({
    queryKey: ['payment-accounts'],
    queryFn: masterApi.getPaymentAccounts,
  });

  const isCustomerType =
    transactionType === 'CUSTOMER_INVOICE' ||
    transactionType === 'CUSTOMER_PAYMENT' ||
    transactionType === 'CUSTOMER_ADVANCE';
  const requiresPaymentAccount =
    transactionType !== 'CUSTOMER_INVOICE' &&
    transactionType !== 'VENDOR_BILL';

  const counterparties = isCustomerType ? customers : vendors;

  const handleAddSplitLine = () => {
    setAllocations((prev) => [...prev, { project_id: '', cost_category: 'MAT', amount: '' }]);
  };

  const handleRemoveSplitLine = (index: number) => {
    setAllocations((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpdateSplitLine = (
    index: number,
    field: keyof TransactionAllocationInput,
    val: any
  ) => {
    setAllocations((prev) =>
      prev.map((line, i) => (i === index ? { ...line, [field]: val } : line))
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const totalNominal = parseFloat(amount);
    if (!totalNominal || totalNominal <= 0) {
      setFormError('Nominal transaksi harus lebih besar dari 0.');
      return;
    }

    if (!description.trim()) {
      setFormError('Keterangan transaksi wajib diisi.');
      return;
    }

    if (isSplitMode) {
      const validation = validateAllocationSum(totalNominal, allocations);
      if (!validation.isValid) {
        setFormError(validation.errorMessage || 'Alokasi proyek tidak seimbang.');
        return;
      }

      const invalidLines = allocations.some((a) => !a.project_id || !a.amount || Number(a.amount) <= 0);
      if (invalidLines) {
        setFormError('Semua baris alokasi proyek wajib memilih proyek dan mengisi nominal.');
        return;
      }

      await onSubmit({
        transaction_type: transactionType,
        transaction_date: transactionDate,
        amount: totalNominal,
        counterparty_id: counterpartyId || undefined,
        payment_account_id: requiresPaymentAccount ? paymentAccountId || undefined : undefined,
        reference_no: referenceNo || undefined,
        description,
        document_ids: documentIds,
        allocations: allocations.map((a) => ({
          project_id: a.project_id,
          cost_category: a.cost_category,
          amount: Number(a.amount),
          notes: a.notes,
        })),
      });
    } else {
      await onSubmit({
        transaction_type: transactionType,
        transaction_date: transactionDate,
        amount: totalNominal,
        counterparty_id: counterpartyId || undefined,
        payment_account_id: requiresPaymentAccount ? paymentAccountId || undefined : undefined,
        reference_no: referenceNo || undefined,
        description,
        document_ids: documentIds,
        project_id: projectId || undefined,
        cost_category: costCategory || undefined,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {formError && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{formError}</span>
        </div>
      )}

      {/* Row 1: Jenis Transaksi & Tanggal */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Select
          label="Jenis Transaksi *"
          value={transactionType}
          onChange={(e) => setTransactionType(e.target.value as TransactionType)}
          required
        >
          <option value="DIRECT_PURCHASE">Pembelian Langsung (Direct Purchase Cash)</option>
          <option value="VENDOR_BILL">Tagihan Vendor (Vendor Bill / Kredit)</option>
          <option value="PAY_VENDOR_BILL">Bayar Tagihan Vendor (Pay Bill)</option>
          <option value="VENDOR_ADVANCE">Kasbon / Uang Muka Vendor</option>
          <option value="CUSTOMER_INVOICE">Tagihan Pelanggan (Customer Invoice)</option>
          <option value="CUSTOMER_PAYMENT">Penerimaan Pembayaran Pelanggan</option>
          <option value="TRANSFER_INTERBANK">Transfer Antar Bank</option>
          <option value="OWNER_CONTRIBUTION">Setoran Modal Pemilik</option>
          <option value="OWNER_WITHDRAWAL">Penarikan Pemilik (Prive)</option>
        </Select>

        <Input
          label="Tanggal Transaksi *"
          type="date"
          value={transactionDate}
          onChange={(e) => setTransactionDate(e.target.value)}
          required
        />
      </div>

      {/* Row 2: Nominal & Rekening Kas/Bank */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Input
          label="Nominal Transaksi (Rp) *"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Contoh: 15000000"
          required
        />

        <Select
          label={`Akun Kas / Bank Pembayaran${requiresPaymentAccount ? ' *' : ''}`}
          value={paymentAccountId}
          onChange={(e) => setPaymentAccountId(e.target.value)}
          required={requiresPaymentAccount}
          disabled={!requiresPaymentAccount}
        >
          <option value="">-- Pilih Akun Kas / Bank --</option>
          {paymentAccounts.map((acc) => (
            <option key={acc.id} value={acc.id}>
              {acc.name} ({acc.coa_account_code})
            </option>
          ))}
        </Select>
      </div>

      {/* Row 3: Counterparty & No Referensi */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Select
          label={`${isCustomerType ? 'Pelanggan / Customer' : 'Vendor / Pemasok / Subkon'}`}
          value={counterpartyId}
          onChange={(e) => setCounterpartyId(e.target.value)}
        >
          <option value="">-- Pilih {isCustomerType ? 'Pelanggan' : 'Vendor'} --</option>
          {counterparties.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>

        <Input
          label="Nomor Referensi / Nomor Nota Fisik"
          value={referenceNo}
          onChange={(e) => setReferenceNo(e.target.value)}
          placeholder="Contoh: INV-2026-088 atau No. Kwitansi"
        />
      </div>

      {/* Row 4: Project Allocation Mode */}
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Alokasi Proyek & Kategori Biaya
            </h4>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Tentukan proyek yang membebankan biaya atau menerima pendapatan ini.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setIsSplitMode(!isSplitMode)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              isSplitMode
                ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-100'
            }`}
          >
            <Split className="h-3.5 w-3.5" />
            {isSplitMode ? 'Mode Multi-Proyek Aktif' : 'Bagi Multi-Proyek'}
          </button>
        </div>

        {!isSplitMode ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label="Pilih Proyek"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            >
              <option value="">-- Tanpa Alokasi Proyek (Operasional Umum) --</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.project_name} ({p.project_code})
                </option>
              ))}
            </Select>

            <Select
              label="Kategori Biaya Konstruksi"
              value={costCategory}
              onChange={(e) => setCostCategory(e.target.value as CostCategory)}
            >
              <option value="MAT">MAT — Material & Bahan Bangunan</option>
              <option value="SUB">SUB — Upah Subkontraktor</option>
              <option value="LAB">LAB — Upah Tukang & Tenaga Kerja</option>
              <option value="EQP">EQP — Sewa Alat Berat & Perkakas</option>
              <option value="TRN">TRN — Transportasi & Logistik</option>
              <option value="UTL">UTL — Listrik, Air & Utilitas Proyek</option>
              <option value="PRM">PRM — Perizinan & Koordinasi Lapangan</option>
              <option value="OHD">OHD — Biaya Operasional Lapangan</option>
              <option value="OTH">OTH — Biaya Lain-lain</option>
            </Select>
          </div>
        ) : (
          <div className="space-y-3">
            {allocations.map((line, idx) => (
              <div key={idx} className="flex items-center gap-3 bg-white p-3 rounded-lg border border-slate-200">
                <div className="flex-1">
                  <Select
                    value={line.project_id}
                    onChange={(e) => handleUpdateSplitLine(idx, 'project_id', e.target.value)}
                    required
                  >
                    <option value="">-- Pilih Proyek --</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.project_name} ({p.project_code})
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="w-48">
                  <Select
                    value={line.cost_category}
                    onChange={(e) => handleUpdateSplitLine(idx, 'cost_category', e.target.value as CostCategory)}
                  >
                    <option value="MAT">MAT (Material)</option>
                    <option value="SUB">SUB (Subkon)</option>
                    <option value="LAB">LAB (Tenaga)</option>
                    <option value="EQP">EQP (Alat)</option>
                    <option value="OTH">OTH (Lainnya)</option>
                  </Select>
                </div>

                <div className="w-48">
                  <Input
                    type="number"
                    placeholder="Nominal alokasi"
                    value={line.amount}
                    onChange={(e) => handleUpdateSplitLine(idx, 'amount', e.target.value)}
                    required
                  />
                </div>

                {allocations.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveSplitLine(idx)}
                    className="p-2 text-rose-500 hover:bg-rose-50 rounded-lg cursor-pointer"
                    title="Hapus baris"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}

            <Button
              type="button"
              variant="outline"
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={handleAddSplitLine}
            >
              Tambah Alokasi Proyek
            </Button>
          </div>
        )}
      </div>

      {/* Row 5: Keterangan */}
      <div>
        <Input
          label="Keterangan Transaksi *"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Contoh: Pembelian semen 100 sak Proyek A toko material jaya"
          required
        />
      </div>

      {/* Row 6: Upload Dokumen Bukti */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
          Lampirkan Bukti Dokumen (Nota / Faktur / SPK)
        </label>
        <FileDropzone
          onUploaded={(doc: DocumentResponse) => {
            setDocumentIds((prev) => [...prev, doc.id]);
          }}
        />
      </div>

      {/* Submit Button Bar */}
      <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
            Batal
          </Button>
        )}
        <Button type="submit" isLoading={isLoading}>
          Simpan Transaksi
        </Button>
      </div>
    </form>
  );
};
