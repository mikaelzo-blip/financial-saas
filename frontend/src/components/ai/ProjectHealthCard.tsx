import { useQuery } from '@tanstack/react-query';
import { insightsApi } from '../../api/insights';
import { InsightContent } from './InsightContent';

export function ProjectHealthCard({ projectId }: { projectId: string }) {
  const query = useQuery({ queryKey: ['insights-project', projectId], queryFn: () => insightsApi.project(projectId), enabled: !!projectId, retry: false });
  if (query.isLoading) return <section aria-label="Kesehatan proyek">Memuat kesehatan proyek…</section>;
  if (query.isError) return <section role="alert" aria-label="Kesehatan proyek">Insight proyek tidak tersedia.</section>;
  return query.data ? <section aria-label="Kesehatan proyek"><InsightContent insight={query.data} /></section> : null;
}
