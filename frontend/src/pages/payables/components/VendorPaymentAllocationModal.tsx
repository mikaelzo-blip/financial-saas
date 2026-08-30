import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { masterApi } from '../../../api/master';
import { payablesApi, VendorBillResponse } from '../../../api/payables';
import { formatIDR } from '../../../utils/formatters';
import { Modal } from '../../../components/ui/Modal';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { useToast } from '../../../components/feedback/Toast';

export interface VendorPaymentAllocationModalProps {
  bill: VendorBillResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const VendorPaymentAllocationModal: React.FC<VendorPaymentAllocationModalProps> = ({
  bill,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { success, error } = useToast();
  const [paymentAccountId, setPaymentAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [referenceNo, setReferenceNo] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const { data: paymentAccounts = [] } = useQuery({
    queryKey: ['payment-accounts'],
    queryFn: masterApi.getPaymentAccounts,
  });

  React.useEffect(() => {
    if (bill) {
      setAmount(bill.outstanding_amount);
    }
  }, [bill]);

  if (!bill) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paymentAccountId) {
      error('Pilih rekening kas/bank pengeluaran.');
      return;
    }
    const payAmount = parseFloat(amount);
    if (!payAmount || payAmount <= 0) {
      error('Nominal pembayaran harus lebih besar dari 0.');
      return;
    }

    setIsLoading(true);
    try {
      await payablesApi.allocatePayment({
        bill_id: bill.id,
        payment_account_id: paymentAccountId,
        amount: payAmount,
        payment_date: paymentDate,
        reference_no: referenceNo || undefined,
      });
      success(`Pembayaran tagihan vendor ${bill.bill_number} berhasil dicatat.`);
      onSuccess();
      onClose();
    } catch (err: any) {
      error(err.response?.data?.detail || 'Gagal mencatat pembayaran tagihan.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="md"
      title={`Bayar Tagihan Vendor — ${bill.bill_number}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-lg bg-slate-50 p-3 text-xs border border-slate-200">
          <div className="flex justify-between py-1">
            <span className="text-slate-500">Vendor / Subkon:</span>
            <span className="font-semibold text-slate-900">{bill.vendor_name}</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-slate-500">Sisa Utang:</span>
            <span className="font-mono font-bold text-rose-600">
              {formatIDR(bill.outstanding_amount)}
            </span>
          </div>
        </div>

        <Select
          label="Dibayar dari Rekening Kas / Bank *"
          value={paymentAccountId}
          onChange={(e) => setPaymentAccountId(e.target.value)}
          required
        >
          <option value="">-- Pilih Rekening Pengeluaran --</option>
          {paymentAccounts.map((acc) => (
            <option key={acc.id} value={acc.id}>
              {acc.account_name} ({acc.account_code})
            </option>
          ))}
        </Select>

        <Input
          label="Nominal Pembayaran (Rp) *"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />

        <Input
          label="Tanggal Pembayaran *"
          type="date"
          value={paymentDate}
          onChange={(e) => setPaymentDate(e.target.value)}
          required
        />

        <Input
          label="Nomor Referensi Transfer / Cek"
          value={referenceNo}
          onChange={(e) => setReferenceNo(e.target.value)}
          placeholder="Contoh: TRF-OUT-98124"
        />

        <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Batal
          </Button>
          <Button type="submit" size="sm" isLoading={isLoading}>
            Simpan Pengeluaran
          </Button>
        </div>
      </form>
    </Modal>
  );
};
