import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { transactionsApi } from '../../../api/transactions';
import { TransactionResponse } from '../../../types/api';
import { formatIDR, formatDate } from '../../../utils/formatters';
import { StatusBadge } from '../../../components/ui/StatusBadge';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';

export const RecentActivityTable: React.FC = () => {
  const navigate = useNavigate();

  const { data: transactions = [], isLoading } = useQuery({
    queryKey: ['recent-transactions'],
    queryFn: () => transactionsApi.list(),
  });

  const recent = transactions.slice(0, 5);

  return (
    <Card
      title="Aktivitas Transaksi Terbaru"
      action={
        <Button variant="ghost" size="sm" onClick={() => navigate('/transactions')}>
          Lihat Semua
        </Button>
      }
    >
      {isLoading ? (
        <div className="py-8 text-center text-xs text-slate-400">Memuat transaksi...</div>
      ) : recent.length === 0 ? (
        <div className="py-8 text-center text-xs text-slate-500">
          Belum ada aktivitas transaksi yang dicatat.
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {recent.map((trx: TransactionResponse) => (
            <div
              key={trx.id}
              onClick={() => navigate(`/transactions/${trx.id}`)}
              className="flex items-center justify-between py-3 hover:bg-slate-50/80 px-2 rounded-lg transition-colors cursor-pointer"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-blue-600">
                    {trx.transaction_code}
                  </span>
                  <StatusBadge status={trx.workflow_status} size="sm" />
                </div>
                <p className="text-xs font-medium text-slate-900 mt-1">{trx.description}</p>
                <p className="text-[10px] text-slate-400">
                  {formatDate(trx.transaction_date)} • {trx.counterparty_name || 'Operasional'}
                </p>
              </div>

              <div className="text-right">
                <p className="font-mono text-xs font-bold text-slate-900 tabular-nums">
                  {formatIDR(trx.amount)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};
