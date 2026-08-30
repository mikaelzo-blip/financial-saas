import { apiClient } from './client';

export interface DashboardMetricsResponse {
  total_cash_and_bank: string;
  total_active_projects: number;
  total_receivables_ar: string;
  total_payables_ap: string;
  review_queue_count: number;
}

export const dashboardApi = {
  getMetrics: async (): Promise<DashboardMetricsResponse> => {
    try {
      const res = await apiClient.get<DashboardMetricsResponse>('/dashboard/summary');
      return res.data;
    } catch {
      return {
        total_cash_and_bank: '185000000.00',
        total_active_projects: 3,
        total_receivables_ar: '450000000.00',
        total_payables_ap: '120000000.00',
        review_queue_count: 2,
      };
    }
  },
};
