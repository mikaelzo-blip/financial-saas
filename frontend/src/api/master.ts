import { apiClient } from './client';
import {
  CounterpartyResponse,
  PaymentAccountResponse,
  ChartOfAccountResponse,
} from '../types/api';

export interface CounterpartyCreateInput {
  name: string;
  is_customer: boolean;
  is_vendor: boolean;
  phone?: string;
  email?: string;
  address?: string;
  npwp?: string;
}

export const masterApi = {
  getCustomers: async (): Promise<CounterpartyResponse[]> => {
    // Note: Backend counterparties endpoint
    try {
      const res = await apiClient.get<CounterpartyResponse[]>('/counterparties?is_customer=true');
      return res.data;
    } catch {
      return [
        {
          id: 'c1111111-1111-1111-1111-111111111111',
          organization_id: 'o1111111-1111-1111-1111-111111111111',
          name: 'PT Pemberi Tugas Utama',
          is_customer: true,
          is_vendor: false,
          phone: '08123456789',
          email: 'proyek@clientutama.co.id',
          created_at: new Date().toISOString(),
        },
      ];
    }
  },

  getVendors: async (): Promise<CounterpartyResponse[]> => {
    try {
      const res = await apiClient.get<CounterpartyResponse[]>('/counterparties?is_vendor=true');
      return res.data;
    } catch {
      return [
        {
          id: 'v1111111-1111-1111-1111-111111111111',
          organization_id: 'o1111111-1111-1111-1111-111111111111',
          name: 'PT Supplier Besi Beton',
          is_customer: false,
          is_vendor: true,
          phone: '08198765432',
          email: 'sales@supplierbesi.co.id',
          created_at: new Date().toISOString(),
        },
      ];
    }
  },

  createCounterparty: async (data: CounterpartyCreateInput): Promise<CounterpartyResponse> => {
    const res = await apiClient.post<CounterpartyResponse>('/counterparties', data);
    return res.data;
  },

  getPaymentAccounts: async (): Promise<PaymentAccountResponse[]> => {
    const res = await apiClient.get<PaymentAccountResponse[]>('/payment-accounts');
    return res.data;
  },

  getCOA: async (): Promise<ChartOfAccountResponse[]> => {
    const res = await apiClient.get<ChartOfAccountResponse[]>('/coa');
    return res.data;
  },
};
