import { apiClient } from './client';

export interface VendorBillResponse {
  id: string;
  organization_id: string;
  vendor_id: string;
  vendor_name?: string;
  project_id?: string;
  project_name?: string;
  bill_number: string;
  bill_date: string;
  due_date: string;
  total_amount: string;
  paid_amount: string;
  outstanding_amount: string;
  status: 'NOT_DUE' | 'DUE' | 'OVERDUE' | 'PAID';
  created_at: string;
}

export const payablesApi = {
  list: async (): Promise<VendorBillResponse[]> => {
    try {
      const res = await apiClient.get<VendorBillResponse[]>('/vendor-bills');
      return res.data;
    } catch {
      return [];
    }
  },

  allocatePayment: async (data: {
    bill_id: string;
    payment_account_id: string;
    amount: number;
    payment_date: string;
    reference_no?: string;
  }) => {
    const res = await apiClient.post('/vendor-payments', data);
    return res.data;
  },

  settleAdvance: async (data: {
    vendor_id: string;
    bill_id: string;
    settlement_amount: number;
    notes?: string;
  }) => {
    const res = await apiClient.post('/vendor-advances/settle', data);
    return res.data;
  },
};
