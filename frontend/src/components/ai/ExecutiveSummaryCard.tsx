import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { insightsApi } from '../../api/insights';
import { useAuth } from '../../store/AuthContext';
import { InsightContent } from './InsightContent';

export function ExecutiveSummaryCard() {
  const { user } = useAuth();
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0,10));
  const [start, setStart] = useState(() => end.slice(0,8)+'01');
  const valid = !!start && !!end && start <= end;
  const query = useQuery({
    queryKey: ['insights', user?.organizationId, user?.userId, start, end],
    queryFn: ({signal}) => insightsApi.executive({start_date:start, end_date:end}, signal),
    enabled: !!user && valid, retry: false,
  });
  return <section aria-label="Insight manajemen" className="rounded-lg border border-slate-200 bg-white p-5 space-y-4">
    <h2 className="font-semibold">Insight manajemen</h2>
    <div className="flex flex-wrap gap-3 text-sm">
      <label>Mulai periode<input aria-label="Mulai periode" type="date" value={start} onChange={e => setStart(e.target.value)} className="block border rounded p-1" /></label>
      <label>Akhir periode<input aria-label="Akhir periode" type="date" value={end} onChange={e => setEnd(e.target.value)} className="block border rounded p-1" /></label>
    </div>
    {!valid && <p role="alert">Periksa rentang tanggal.</p>}
    {query.isFetching && <p role="status">Memuat ringkasan…</p>}
    {query.isError && <div role="alert">Ringkasan tidak tersedia. <button onClick={() => query.refetch()}>Coba lagi</button></div>}
    {valid && !query.isError && query.data && <InsightContent insight={query.data} />}
  </section>;
}
