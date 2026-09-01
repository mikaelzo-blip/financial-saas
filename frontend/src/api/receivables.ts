import { apiClient } from './client';

export interface CustomerInvoiceResponse {
  id: string;
  organization_id: string;
  customer_id: string;
  customer_name?: string;
  project_id?: string;
  project_name?: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  total_amount: string;
  paid_amount: string;
  outstanding_amount: string;
  collection_status: 'NOT_DUE' | 'DUE' | 'OVERDUE' | 'COLLECTED';
  created_at: string;
}

export const receivablesApi = {
  list: async (): Promise<CustomerInvoiceResponse[]> => {
    try {
      const res = await apiClient.get<CustomerInvoiceResponse[]>('/customer-invoices');
      return res.data;
    } catch {
      return [];
    }
  },

  allocatePayment: async (data: {
    invoice_id: string;
    payment_account_id: string;
    amount: number;
    payment_date: string;
    reference_no?: string;
    description: string;
  }) => {
    const res = await apiClient.post('/customer-payments', data);
    return res.data;
  },
};
