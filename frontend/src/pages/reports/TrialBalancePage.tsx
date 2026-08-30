import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Scale, RefreshCw } from 'lucide-react';
import { reportsApi } from '../../api/reports';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { formatIDR } from '../../utils/formatters';
import { ReportHeader } from '../../components/reports/ReportHeader';

export const TrialBalancePage: React.FC = () => {
  const today = new Date().toISOString().split('T')[0];
  const [asOfDate, setAsOfDate] = useState<string>(today);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['trial-balance', asOfDate],
    queryFn: () => reportsApi.getTrialBalance(undefined, undefined, asOfDate),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Neraca Saldo (Trial Balance)</h1>
          <p className="text-sm text-slate-500">
            Daftar saldo penutupan seluruh akun buku besar per tanggal pelaporan.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="w-44"
          />
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
            Muat Ulang
          </Button>
          <ReportHeader reportType="trial-balance" params={{ as_of_date: asOfDate }} disabled={!data || !data.is_balanced} />
        </div>
      </div>

      {isLoading ? (
        <SkeletonLoader count={8} />
      ) : data ? (
        <Card className="overflow-hidden p-0">
          <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center text-xs text-slate-600">
            <span>Entitas: <strong className="text-slate-900">{data.organization_name}</strong></span>
            <span>Per Tanggal: <strong className="text-slate-900">{data.as_of_date}</strong></span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 text-slate-700 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 border-b border-r border-slate-200">Kode Akun</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200">Nama Akun</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Mutasi Debet</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Mutasi Kredit</th>
                  <th className="px-4 py-3 border-b border-r border-slate-200 text-right">Saldo Akhir Debet</th>
                  <th className="px-4 py-3 border-b border-slate-200 text-right">Saldo Akhir Kredit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-xs">
                {data.lines.map((l) => (
                  <tr key={l.account_code} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-bold text-slate-800 border-r border-slate-100">{l.account_code}</td>
                    <td className="px-4 py-2 font-sans text-slate-700 border-r border-slate-100">{l.account_name}</td>
                    <td className="px-4 py-2 text-right border-r border-slate-100">{formatIDR(l.period_debit)}</td>
                    <td className="px-4 py-2 text-right border-r border-slate-100">{formatIDR(l.period_credit)}</td>
                    <td className="px-4 py-2 text-right font-bold text-slate-900 border-r border-slate-100">
                      {Number(l.ending_debit) > 0 ? formatIDR(l.ending_debit) : '-'}
                    </td>
                    <td className="px-4 py-2 text-right font-bold text-slate-900">
                      {Number(l.ending_credit) > 0 ? formatIDR(l.ending_credit) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-100 font-mono text-xs font-bold text-slate-900">
                <tr>
                  <td colSpan={2} className="px-4 py-3 text-right uppercase border-r border-slate-200">Total Keseimbangan:</td>
                  <td className="px-4 py-3 text-right border-r border-slate-200">{formatIDR(data.total_period_debit)}</td>
                  <td className="px-4 py-3 text-right border-r border-slate-200">{formatIDR(data.total_period_credit)}</td>
                  <td className="px-4 py-3 text-right border-r border-slate-200 text-emerald-800">{formatIDR(data.total_ending_debit)}</td>
                  <td className="px-4 py-3 text-right text-emerald-800">{formatIDR(data.total_ending_credit)}</td>
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="p-4 bg-emerald-50 border-t border-emerald-200 flex items-center justify-between text-xs text-emerald-800">
            <div className="flex items-center space-x-2">
              <Scale className="w-4 h-4 text-emerald-600" />
              <span>Status Keseimbangan: <strong>{data.is_balanced ? 'SEIMBANG (Rp 0,00 Selisih)' : 'TIDAK SEIMBANG'}</strong></span>
            </div>
          </div>
        </Card>
      ) : null}
    </div>
  );
};
