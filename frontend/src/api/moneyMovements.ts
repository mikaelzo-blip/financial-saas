import { apiClient } from './client';

export interface MoneyMovementDTO {
  id: string;
  organization_id: string;
  movement_code: string;
  payment_account_id: string;
  payment_account_name?: string;
  direction: 'IN' | 'OUT';
  amount: number;
  movement_date: string;
  source_type: 'TRANSFER_PROOF' | 'BANK_STATEMENT' | 'MANUAL';
  reference_no?: string;
  description?: string;
  created_at: string;
}

export interface CreateMoneyMovementRequest {
  payment_account_id: string;
  direction: 'IN' | 'OUT';
  amount: number;
  movement_date: string;
  source_type?: 'TRANSFER_PROOF' | 'BANK_STATEMENT' | 'MANUAL';
  reference_no?: string;
  description?: string;
}

export const moneyMovementsApi = {
  listMovements: async (paymentAccountId?: string, limit = 50, offset = 0): Promise<MoneyMovementDTO[]> => {
    const params = new URLSearchParams();
    if (paymentAccountId) {
      params.append('payment_account_id', paymentAccountId);
    }
    params.append('limit', String(limit));
    params.append('offset', String(offset));

    const response = await apiClient.get<MoneyMovementDTO[]>(`/api/v1/money-movements?${params.toString()}`);
    return response.data;
  },

  createMovement: async (payload: CreateMoneyMovementRequest): Promise<MoneyMovementDTO> => {
    const response = await apiClient.post<MoneyMovementDTO>('/api/v1/money-movements', payload);
    return response.data;
  },
};
