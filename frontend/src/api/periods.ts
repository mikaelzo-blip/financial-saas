import { apiClient } from './client';

export interface AccountingPeriod {
  id: string;
  organization_id: string;
  period_name: string;
  start_date: string;
  end_date: string;
  status: 'OPEN' | 'SOFT_CLOSED' | 'CLOSED';
  closed_at?: string;
  closed_by?: string;
  created_at: string;
}

export interface AccountingPeriodCreateInput {
  period_name: string;
  start_date: string;
  end_date: string;
}

export interface AccountingPeriodUpdateInput {
  status: 'OPEN' | 'SOFT_CLOSED' | 'CLOSED';
  reason?: string;
}

export const getAccountingPeriods = async (): Promise<AccountingPeriod[]> => {
  const res = await apiClient.get<AccountingPeriod[]>('/periods');
  return res.data;
};

export const createAccountingPeriod = async (
  payload: AccountingPeriodCreateInput
): Promise<AccountingPeriod> => {
  const res = await apiClient.post<AccountingPeriod>('/periods', payload);
  return res.data;
};

export const updateAccountingPeriodStatus = async (
  periodId: string,
  payload: AccountingPeriodUpdateInput
): Promise<AccountingPeriod> => {
  const res = await apiClient.patch<AccountingPeriod>(`/periods/${periodId}/status`, payload);
  return res.data;
};
