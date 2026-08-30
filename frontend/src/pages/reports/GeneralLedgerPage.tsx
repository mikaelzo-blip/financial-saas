import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { masterApi } from '../../api/master';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ChartOfAccountResponse } from '../../types/api';

export const GeneralLedgerPage: React.FC = () => {
  const today = new Date().toISOString().split('T')[0];
  const firstDayOfYear = `${new Date().getFullYear()}-01-01`;

  const [accountCode, setAccountCode] = useState<string>('1101');
  const [startDate, setStartDate] = useState<string>(firstDayOfYear);
  const [endDate, setEndDate] = useState<string>(today);

  // Fetch active COA accounts for selector
  const { data: coaList } = useQuery({
    queryKey: ['coa-list'],
    queryFn: () => masterApi.getCOA(),
  });

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['general-ledger', accountCode, startDate, endDate],
    queryFn: () => reportsApi.getGeneralLedger(accountCode, startDate, endDate),
    enabled: !!accountCode,
  });

  const accountOptions = coaList
    ? coaList.map((a: ChartOfAccountResponse) => ({
        value: a.account_code,
        label: `${a.account_code} — ${a.account_name}`,
      }))
    : [{ value: '1101', label: '1101 — Kas dan Bank' }];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Buku Besar (General Ledger)</h1>
          <p className="text-sm text-slate-500">
            Rincian mutasi transaksi dan saldo berjalan per akun buku besar.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => refetch()}
          disabled={isFetching}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
          Segarkan
        </Button>
      </div>

      {/* Filter Card */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
          <div>
            <Select
              label="Pilih Akun Buku Besar"
              options={accountOptions}
              value={accountCode}
              onChange={(e) => setAccountCode(e.target.value)}
            />
          </div>
          <div>
            <Input
              label="Dari Tanggal"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div>
            <Input
              label="Sampai Tanggal"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
        </div>
      </Card>

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <Card className="overflow-hidden p-0">
          <div className="p-4 bg-slate-50 border-b border-slate-200 flex flex-wrap justify-between items-center text-xs text-slate-600 gap-2">
            <div>
              <span className="font-bold text-slate-800 text-sm">
                {data.account_code} — {data.account_name}
              </span>
              <span className="ml-2 text-xs bg-slate-200 px-2 py-0.5 rounded text-slate-700">
                Saldo Normal: {data.normal_balance}
              </span>
            </div>
            <div>
              <span>Periode: <strong className="text-slate-900">{data.start_date} — {data.end_date}</strong></span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 text-slate-700 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 border-b border-r border-slate-200">Tanggal</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200">No. Jurnal</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200">Keterangan / Proyek</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Debet</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Kredit</th>
                  <th className="px-4 py-3 border-b border-slate-200 text-right">Saldo Berjalan</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-xs">
                <tr className="bg-amber-50/50">
                  <td colSpan={3} className="px-4 py-2 font-sans font-semibold text-slate-800 border-r border-slate-200">
                    Saldo Awal (Sebelum {data.start_date}):
                  </td>
                  <td className="px-4 py-2 text-right border-r border-slate-200">-</td>
                  <td className="px-4 py-2 text-right border-r border-slate-200">-</td>
                  <td className="px-4 py-2 text-right font-bold text-slate-900">
                    {formatIDR(data.opening_balance)}
                  </td>
                </tr>

                {data.entries.map((e, idx) => (
                  <tr key={`${e.journal_entry_id}-${idx}`} className="hover:bg-slate-50">
                    <td className="px-4 py-2 text-slate-700 border-r border-slate-100">{e.date}</td>
                    <td className="px-4 py-2 font-bold text-indigo-700 border-r border-slate-100">{e.journal_entry_number}</td>
                    <td className="px-4 py-2 font-sans text-slate-800 border-r border-slate-100">
                      <div>{e.description}</div>
                      {e.project_code && (
                        <div className="text-[11px] text-slate-500 font-mono">
                          Proyek: {e.project_code} {e.project_name ? `(${e.project_name})` : ''}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right border-r border-slate-100 font-bold text-slate-900">
                      {Number(e.debit) > 0 ? formatIDR(e.debit) : '-'}
                    </td>
                    <td className="px-4 py-2 text-right border-r border-slate-100 font-bold text-slate-900">
                      {Number(e.credit) > 0 ? formatIDR(e.credit) : '-'}
                    </td>
                    <td className="px-4 py-2 text-right font-bold text-slate-900">
                      {formatIDR(e.running_balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-100 font-mono text-xs font-bold text-slate-900">
                <tr>
                  <td colSpan={3} className="px-4 py-3 text-right uppercase border-r border-slate-200">Total Mutasi & Saldo Akhir:</td>
                  <td className="px-4 py-3 text-right border-r border-slate-200">{formatIDR(data.total_debit)}</td>
                  <td className="px-4 py-3 text-right border-r border-slate-200">{formatIDR(data.total_credit)}</td>
                  <td className="px-4 py-3 text-right text-indigo-900 bg-indigo-50/50">{formatIDR(data.closing_balance)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
};
