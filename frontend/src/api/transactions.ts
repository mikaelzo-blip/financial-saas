import { apiClient } from './client';
import {
  TransactionResponse,
  TransactionType,
  WorkflowStatus,
  CostCategory,
} from '../types/api';

export interface TransactionAllocationInput {
  project_id?: string;
  cost_category?: CostCategory;
  amount: number | string;
  notes?: string;
}

export interface TransactionCreateInput {
  transaction_type: TransactionType;
  transaction_date: string;
  amount: number | string;
  currency?: string;
  counterparty_id?: string;
  payment_account_id?: string;
  reference_no?: string;
  description: string;
  document_ids?: string[];
  project_id?: string;
  cost_category?: CostCategory;
  allocations?: TransactionAllocationInput[];
}

export const transactionsApi = {
  list: async (params?: {
    status?: WorkflowStatus;
    project_id?: string;
  }): Promise<TransactionResponse[]> => {
    const res = await apiClient.get<TransactionResponse[]>('/transactions', { params });
    return res.data;
  },

  get: async (id: string): Promise<TransactionResponse> => {
    const res = await apiClient.get<TransactionResponse>(`/transactions/${id}`);
    return res.data;
  },

  create: async (data: TransactionCreateInput): Promise<TransactionResponse> => {
    const res = await apiClient.post<TransactionResponse>('/transactions', data);
    return res.data;
  },

  approveAndPost: async (id: string): Promise<TransactionResponse> => {
    const res = await apiClient.post<TransactionResponse>(`/transactions/${id}/approve`);
    return res.data;
  },

  postDirect: async (id: string): Promise<TransactionResponse> => {
    const res = await apiClient.post<TransactionResponse>(`/transactions/${id}/post`);
    return res.data;
  },

  reverse: async (id: string, reason: string): Promise<TransactionResponse> => {
    const res = await apiClient.post<TransactionResponse>(`/transactions/${id}/reverse`, {
      reason,
    });
    return res.data;
  },
};
