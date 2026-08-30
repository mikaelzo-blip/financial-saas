import { apiClient } from './client';

export interface Insight {
  organization_id: string;
  headline: string;
  factual_metrics: Record<string, string | null>;
  analytical_narrative: string;
  actionable_recommendations: string[];
  confidence_score: 'HIGH' | 'MEDIUM' | 'LOW';
  period_label: string;
  data_as_of: string;
  generated_at: string;
  source_references: string[];
  metric_sources: Record<string, string>;
  unavailable_metrics: string[];
  anomalies_detected: { code: string; severity: string; description: string; metric_reference: string }[];
  provider_metadata: { provider: string; cached: boolean; latency_ms: number; tokens_used: number };
}

export interface InsightPeriod { start_date: string; end_date: string }

export const insightsApi = {
  executive: async (period: InsightPeriod, signal?: AbortSignal): Promise<Insight> =>
    (await apiClient.get<Insight>('/insights/executive-summary', {params: period, signal})).data,
};
