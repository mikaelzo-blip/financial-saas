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
    const res = await apiClient.get<CounterpartyResponse[]>('/counterparties?is_customer=true');
    return res.data;
  },

  getVendors: async (): Promise<CounterpartyResponse[]> => {
    const res = await apiClient.get<CounterpartyResponse[]>('/counterparties?is_vendor=true');
    return res.data;
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
