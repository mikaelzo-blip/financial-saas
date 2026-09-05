import { apiClient } from './client';
import { CashCompletenessDashboard, ReconciliationStatus } from '../types/api';

export interface BankStatementImportDTO {
  id: string;
  organization_id: string;
  payment_account_id: string;
  period_start?: string;
  period_end?: string;
  file_hash: string;
  source_file: string;
  imported_at: string;
  status: string;
  line_count: number;
}

export interface BankReconciliationMatchRequest {
  statement_line_id: string;
  transaction_id?: string;
  money_movement_id?: string;
  status: ReconciliationStatus;
  notes?: string;
}

export const bankReconciliationApi = {
  uploadStatement: async (paymentAccountId: string, file: File): Promise<BankStatementImportDTO> => {
    const formData = new FormData();
    formData.append('payment_account_id', paymentAccountId);
    formData.append('file', file);

    const response = await apiClient.post<BankStatementImportDTO>(
      '/api/v1/bank-reconciliation/imports',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  autoMatch: async (importId: string): Promise<{ message: string; stats: Record<string, number> }> => {
    const response = await apiClient.post<{ message: string; stats: Record<string, number> }>(
      `/api/v1/bank-reconciliation/imports/${importId}/auto-match`
    );
    return response.data;
  },

  reconcileManual: async (payload: BankReconciliationMatchRequest): Promise<{ message: string; id: string }> => {
    const response = await apiClient.post<{ message: string; id: string }>(
      '/api/v1/bank-reconciliation/reconcile',
      payload
    );
    return response.data;
  },

  getCashCompletenessDashboard: async (paymentAccountId?: string): Promise<CashCompletenessDashboard> => {
    const params = paymentAccountId ? `?payment_account_id=${paymentAccountId}` : '';
    const response = await apiClient.get<CashCompletenessDashboard>(
      `/api/v1/bank-reconciliation/dashboard${params}`
    );
    return response.data;
  },
};
