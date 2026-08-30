import { apiClient } from './client';
import { TransactionResponse, ReviewFlag } from '../types/api';

export interface ReviewQueueItemResponse extends TransactionResponse {
  unresolved_flags_count: number;
}

export const reviewApi = {
  list: async (flag?: ReviewFlag): Promise<TransactionResponse[]> => {
    const params = flag ? { flag } : {};
    const res = await apiClient.get<TransactionResponse[]>('/review-queue', { params });
    return res.data;
  },

  resolveFlag: async (
    flagId: string,
    data: {
      resolution_notes: string;
      corrected_amount?: number;
      corrected_project_id?: string;
      corrected_counterparty_id?: string;
    }
  ) => {
    const res = await apiClient.post(`/review-queue/flags/${flagId}/resolve`, data);
    return res.data;
  },

  approveAndPost: async (transactionId: string) => {
    const res = await apiClient.post(`/review-queue/${transactionId}/approve-and-post`);
    return res.data;
  },

  reject: async (transactionId: string, reason: string) => {
    const res = await apiClient.post(`/review-queue/${transactionId}/reject`, { reason });
    return res.data;
  },
};
