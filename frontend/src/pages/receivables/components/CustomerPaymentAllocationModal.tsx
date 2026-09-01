import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { masterApi } from '../../../api/master';
import { receivablesApi, CustomerInvoiceResponse } from '../../../api/receivables';
import { formatIDR } from '../../../utils/formatters';
import { Modal } from '../../../components/ui/Modal';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Select } from '../../../components/ui/Select';
import { useToast } from '../../../components/feedback/Toast';

export interface CustomerPaymentAllocationModalProps {
  invoice: CustomerInvoiceResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const CustomerPaymentAllocationModal: React.FC<CustomerPaymentAllocationModalProps> = ({
  invoice,
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
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const { data: paymentAccounts = [] } = useQuery({
    queryKey: ['payment-accounts'],
    queryFn: masterApi.getPaymentAccounts,
  });

  React.useEffect(() => {
    if (invoice) {
      setAmount(invoice.outstanding_amount);
    }
  }, [invoice]);

  if (!invoice) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paymentAccountId) {
      error('Pilih rekening kas/bank penerima.');
      return;
    }
    const payAmount = parseFloat(amount);
    if (!payAmount || payAmount <= 0) {
      error('Nominal pembayaran harus lebih besar dari 0.');
      return;
    }

    setIsLoading(true);
    try {
      await receivablesApi.allocatePayment({
        invoice_id: invoice.id,
        payment_account_id: paymentAccountId,
        amount: payAmount,
        payment_date: paymentDate,
        reference_no: referenceNo || undefined,
        description,
      });
      success(`Pembayaran invoice ${invoice.invoice_number} berhasil dicatat.`);
      onSuccess();
      onClose();
    } catch (err: any) {
      error(err.response?.data?.detail || 'Gagal mencatat pembayaran invoice.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="md"
      title={`Terima Pembayaran — ${invoice.invoice_number}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-lg bg-slate-50 p-3 text-xs border border-slate-200">
          <div className="flex justify-between py-1">
            <span className="text-slate-500">Pelanggan:</span>
            <span className="font-semibold text-slate-900">{invoice.customer_name}</span>
          </div>
          <div className="flex justify-between py-1">
            <span className="text-slate-500">Sisa Piutang:</span>
            <span className="font-mono font-bold text-blue-600">
              {formatIDR(invoice.outstanding_amount)}
            </span>
          </div>
        </div>

        <Select
          label="Rekening Bank Penerimaan *"
          value={paymentAccountId}
          onChange={(e) => setPaymentAccountId(e.target.value)}
          required
        >
          <option value="">-- Pilih Rekening Kas/Bank --</option>
          {paymentAccounts.map((acc) => (
            <option key={acc.id} value={acc.id}>
              {acc.name} ({acc.coa_account_code})
            </option>
          ))}
        </Select>

        <Input
          label="Nominal Pembayaran Diterima (Rp) *"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />

        <Input
          label="Tanggal Penerimaan *"
          type="date"
          value={paymentDate}
          onChange={(e) => setPaymentDate(e.target.value)}
          required
        />

        <Input
          label="Nomor Bukti Transfer Bank"
          value={referenceNo}
          onChange={(e) => setReferenceNo(e.target.value)}
          placeholder="Contoh: TRF-BCA-98124"
        />

        <Input
          label="Keterangan Pembayaran *"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Contoh: Pelunasan invoice proyek"
          required
        />

        <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
          <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Batal
          </Button>
          <Button type="submit" size="sm" isLoading={isLoading}>
            Simpan Penerimaan
          </Button>
        </div>
      </form>
    </Modal>
  );
};
