import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { transactionsApi, TransactionCreateInput } from '../../api/transactions';
import { useToast } from '../../components/feedback/Toast';
import { Card } from '../../components/ui/Card';
import { TransactionForm } from '../../components/forms/TransactionForm';

export const TransactionCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const { success, error } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (data: TransactionCreateInput) => {
    setIsLoading(true);
    try {
      const trx = await transactionsApi.create(data);
      if (trx.workflow_status === 'REVIEW_REQUIRED') {
        success(`Transaksi ${trx.transaction_code} tersimpan ke Antrean Review.`);
      } else {
        success(`Transaksi ${trx.transaction_code} berhasil dicatat.`);
      }
      navigate(`/transactions/${trx.id}`);
    } catch (err: any) {
      error(err.response?.data?.detail || 'Gagal menyimpan transaksi.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/transactions')}
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-200/60 hover:text-slate-900 transition-colors cursor-pointer"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Catat Transaksi Operasional Baru
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Input pembayaran, tagihan, kasbon, atau penerimaan proyek tanpa perlu memilih debit/kredit manual.
          </p>
        </div>
      </div>

      <Card>
        <TransactionForm
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onCancel={() => navigate('/transactions')}
        />
      </Card>
    </div>
  );
};
