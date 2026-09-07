import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Trash2, Split, AlertCircle, Info } from 'lucide-react';
import { projectsApi } from '../../api/projects';
import { masterApi } from '../../api/master';
import { TransactionCreateInput, TransactionAllocationInput } from '../../api/transactions';
import { TransactionType, CostCategory, ExpenseCategory, DocumentResponse } from '../../types/api';
import { validateAllocationSum } from '../../utils/transactionValidation';
import { formatIDR } from '../../utils/formatters';
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
  const [destinationPaymentAccountId, setDestinationPaymentAccountId] = useState('');
  const [referenceNo, setReferenceNo] = useState('');
  const [documentIds, setDocumentIds] = useState<string[]>([]);

  // Project vs Office Context
  const [allocationContext, setAllocationContext] = useState<'PROJECT' | 'OFFICE'>('PROJECT');
  const [projectId, setProjectId] = useState('');
  const [costCategory, setCostCategory] = useState<CostCategory>('MAT');
  const [expenseCategory, setExpenseCategory] = useState<ExpenseCategory>('OFFICE_ADMIN');

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
  const isExpenseOrBillType =
    transactionType === 'DIRECT_PURCHASE' ||
    transactionType === 'VENDOR_BILL' ||
    transactionType === 'VENDOR_ADVANCE';

  const counterparties = isCustomerType ? customers : vendors;
  const activeProjects = projects.filter(
    (p) => !p.project_status || ['PLANNED', 'ACTIVE', 'ON_HOLD'].includes(p.project_status)
  );
  const selectedProject = projects.find((p) => p.id === projectId);
  const selectedCounterparty = counterparties.find((c) => c.id === counterpartyId);
  const selectedPaymentAccount = paymentAccounts.find((a) => a.id === paymentAccountId);

  const costCategoryLabels: Record<CostCategory, string> = {
    MAT: 'Material & Bahan Bangunan',
    SUB: 'Subkontraktor / Jasa Spesialis',
    LAB: 'Upah Tukang & Tenaga Kerja',
    TRN: 'Transportasi & BBM Lapangan',
    TRV: 'Perjalanan & Akomodasi Lapangan',
    LOG: 'Logistik & Ekspedisi Material',
    EQP: 'Sewa Alat Berat & Perkakas',
    SIT: 'Biaya Keselamatan & Lapangan',
    OTH: 'Biaya Lapangan Lainnya',
  };

  const expenseCategoryLabels: Record<ExpenseCategory, string> = {
    OFFICE_ADMIN: 'Keperluan Kantor & ATK',
    TRAVEL_OFFICE: 'BBM, Parkir & Transportasi Kantor',
    SALARY: 'Gaji & Upah Karyawan Kantor',
    FEE: 'Fee & Jasa Profesional Non-Proyek',
    PROFESSIONAL_SERVICE: 'Konsultan Pajak & Jasa Legalitas',
    PERMITS: 'Perizinan & Sertifikasi Perusahaan',
    BANK_CHARGES: 'Biaya Administrasi Bank',
    DEPRECIATION: 'Penyusutan Aset Tetap',
    OTHER_OPERATIONAL: 'Operasional Kantor Lainnya',
  };

  const getSummaryImpact = () => {
    switch (transactionType) {
      case 'DIRECT_PURCHASE':
        return allocationContext === 'PROJECT'
          ? 'Mencatat biaya langsung proyek dan pengeluaran kas/bank.'
          : 'Mencatat beban operasional umum kantor dan pengeluaran kas/bank.';
      case 'VENDOR_BILL':
        return allocationContext === 'PROJECT'
          ? 'Mencatat tagihan utang usaha vendor dan membebankan biaya proyek tanpa kas keluar sekarang.'
          : 'Mencatat tagihan utang usaha vendor dan membebankan beban kantor tanpa kas keluar sekarang.';
      case 'PAY_VENDOR_BILL':
        return 'Melunasi utang usaha vendor dan mencatat pengeluaran kas/bank.';
      case 'VENDOR_ADVANCE':
        return 'Mencatat kasbon/uang muka vendor dan pengeluaran kas/bank.';
      case 'CUSTOMER_INVOICE':
        return 'Mencatat piutang usaha pelanggan dan mengakui pendapatan proyek.';
      case 'CUSTOMER_PAYMENT':
        return 'Mencatat penerimaan kas/bank dari pelanggan dan mengurangi piutang usaha.';
      case 'INTERBANK_TRANSFER':
        return 'Mutasi dana antar rekening kas/bank tanpa mempengaruhi pendapatan atau beban.';
      case 'OWNER_CONTRIBUTION':
        return 'Mencatat setoran modal pemilik ke rekening kas/bank.';
      case 'OWNER_WITHDRAWAL':
        return 'Mencatat penarikan dana pemilik (prive) dari rekening kas/bank.';
      case 'BANK_TO_CASH':
        return 'Tarik tunai dari bank ke kas tanpa mempengaruhi laba rugi.';
      case 'CASH_TO_BANK':
        return 'Setor tunai dari kas ke bank tanpa mempengaruhi laba rugi.';
      default:
        return 'Transaksi operasional dicatat ke jurnal keuangan.';
    }
  };

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

    if (transactionType === 'INTERBANK_TRANSFER') {
      if (!paymentAccountId) {
        setFormError('Rekening asal transfer wajib dipilih.');
        return;
      }
      if (!destinationPaymentAccountId) {
        setFormError('Rekening tujuan transfer wajib dipilih.');
        return;
      }
      if (paymentAccountId === destinationPaymentAccountId) {
        setFormError('Rekening asal dan rekening tujuan transfer tidak boleh sama.');
        return;
      }
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
        destination_payment_account_id: transactionType === 'INTERBANK_TRANSFER' ? destinationPaymentAccountId || undefined : undefined,
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
        destination_payment_account_id: transactionType === 'INTERBANK_TRANSFER' ? destinationPaymentAccountId || undefined : undefined,
        reference_no: referenceNo || undefined,
        description,
        document_ids: documentIds,
        project_id: (allocationContext === 'PROJECT' || isCustomerType) && projectId ? projectId : undefined,
        cost_category: (allocationContext === 'PROJECT' && !isCustomerType) ? costCategory : undefined,
        expense_category: (allocationContext === 'OFFICE' && isExpenseOrBillType) ? expenseCategory : undefined,
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
          <option value="BANK_TO_CASH">Bank ke Kas</option>
          <option value="CASH_TO_BANK">Kas ke Bank</option>
          <option value="INTERBANK_TRANSFER">Transfer Antar Bank</option>

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
          <option value="">-- Pilih {transactionType === 'INTERBANK_TRANSFER' ? 'Akun Kas / Bank Asal' : 'Akun Kas / Bank'} --</option>
          {paymentAccounts.map((acc) => (
            <option key={acc.id} value={acc.id}>
              {acc.name} ({acc.coa_account_code})
            </option>
          ))}
        </Select>
      </div>

      {transactionType === 'INTERBANK_TRANSFER' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-blue-50/50 p-4 rounded-xl border border-blue-200">
          <Select
            label="Akun Kas / Bank Tujuan (Penerima Transfer) *"
            value={destinationPaymentAccountId}
            onChange={(e) => setDestinationPaymentAccountId(e.target.value)}
            required
          >
            <option value="">-- Pilih Rekening Kas / Bank Tujuan --</option>
            {paymentAccounts
              .filter((acc) => acc.id !== paymentAccountId)
              .map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name} ({acc.coa_account_code})
                </option>
              ))}
          </Select>
          <div className="flex items-center text-xs text-blue-800 bg-white p-3 rounded-lg border border-blue-100">
            <span>Mutasi Antar Rekening: Pemindahan dana tidak mempengaruhi pendapatan maupun beban operasional perusahaan.</span>
          </div>
        </div>
      )}

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
      {(isExpenseOrBillType || isCustomerType) && (
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Alokasi Proyek & Kategori Biaya
              </h4>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Tentukan konteks penggunaan dana dan kategori biaya atau pendapatan.
              </p>
            </div>

            {isExpenseOrBillType && (
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
            )}
          </div>

          {/* Context Selector: Proyek vs Kantor */}
          {isExpenseOrBillType && !isSplitMode && (
            <div className="space-y-2">
              <span className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Digunakan untuk apa?
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-md">
                <button
                  type="button"
                  onClick={() => setAllocationContext('PROJECT')}
                  className={`p-3 rounded-lg border text-left text-xs transition-all cursor-pointer ${
                    allocationContext === 'PROJECT'
                      ? 'border-blue-600 bg-blue-50 text-blue-900 font-semibold shadow-xs'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <span className="block font-semibold">Proyek tertentu</span>
                  <span className="text-[11px] text-slate-500 font-normal">Biaya langsung yang dibebankan ke satu proyek</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAllocationContext('OFFICE');
                    setProjectId('');
                  }}
                  className={`p-3 rounded-lg border text-left text-xs transition-all cursor-pointer ${
                    allocationContext === 'OFFICE'
                      ? 'border-blue-600 bg-blue-50 text-blue-900 font-semibold shadow-xs'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <span className="block font-semibold">Operasional kantor</span>
                  <span className="text-[11px] text-slate-500 font-normal">Biaya operasional kantor, ATK, transportasi kantor, gaji</span>
                </button>
              </div>
            </div>
          )}

          {!isSplitMode ? (
            allocationContext === 'PROJECT' || isCustomerType ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Select
                  label="Pilih Proyek"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                >
                  <option value="">-- Tanpa Alokasi Proyek (Operasional Umum) --</option>
                  {activeProjects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.project_name} ({p.project_code})
                    </option>
                  ))}
                </Select>

                {isExpenseOrBillType && (
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
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Select
                  label="Kategori Biaya Operasional Kantor"
                  value={expenseCategory}
                  onChange={(e) => setExpenseCategory(e.target.value as ExpenseCategory)}
                >
                  <option value="OFFICE_ADMIN">Keperluan Kantor & ATK</option>
                  <option value="TRAVEL_OFFICE">BBM, Parkir & Transportasi Kantor</option>
                  <option value="SALARY">Gaji & Upah Karyawan Kantor</option>
                  <option value="FEE">Fee & Jasa Profesional Non-Proyek</option>
                  <option value="PROFESSIONAL_SERVICE">Konsultan Profesional & Jasa Pajak</option>
                  <option value="PERMITS">Legalitas & Perizinan Perusahaan</option>
                  <option value="BANK_CHARGES">Biaya Administrasi Bank</option>
                  <option value="OTHER_OPERATIONAL">Operasional Kantor Lainnya</option>
                </Select>
                <div className="flex items-center text-xs text-slate-500 bg-white p-3 rounded-lg border border-slate-200">
                  <span>Beban kantor dicatat pada Laporan Laba Rugi dan tidak membebankan biaya langsung proyek.</span>
                </div>
              </div>
            )
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
      )}

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

      {/* Ringkasan Transaksi & Dampak Finansial */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 space-y-3" aria-label="Ringkasan Transaksi">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
          <Info className="h-4 w-4 text-blue-600" />
          Ringkasan Transaksi
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
          <div>
            <span className="text-slate-500 block">Konteks:</span>
            <strong className="text-slate-900">
              {allocationContext === 'PROJECT' && selectedProject
                ? selectedProject.project_name
                : allocationContext === 'OFFICE' && isExpenseOrBillType
                  ? 'Operasional Kantor'
                  : isCustomerType
                    ? 'Pelanggan Proyek'
                    : 'Umum'}
            </strong>
          </div>
          <div>
            <span className="text-slate-500 block">Kategori:</span>
            <strong className="text-slate-900">
              {allocationContext === 'PROJECT'
                ? costCategoryLabels[costCategory]
                : isExpenseOrBillType
                  ? expenseCategoryLabels[expenseCategory]
                  : 'Operasional'}
            </strong>
          </div>
          <div>
            <span className="text-slate-500 block">{isCustomerType ? 'Pelanggan:' : 'Vendor / Pihak:'}</span>
            <strong className="text-slate-900">
              {selectedCounterparty ? selectedCounterparty.name : '-'}
            </strong>
          </div>
          <div>
            <span className="text-slate-500 block">Nominal:</span>
            <strong className="text-slate-900 font-mono">
              {amount ? formatIDR(parseFloat(amount) || 0) : 'Rp 0'}
            </strong>
          </div>
          <div>
            <span className="text-slate-500 block">Rekening / Kas:</span>
            <strong className="text-slate-900">
              {selectedPaymentAccount ? selectedPaymentAccount.name : '-'}
            </strong>
          </div>
        </div>
        <div className="pt-2 border-t border-blue-200/60 text-blue-950 font-medium">
          <span className="text-blue-700">Dampak: </span>
          <span>{getSummaryImpact()}</span>
        </div>
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
