import { apiClient } from './client';
import {
  ProjectResponse,
  ProjectProfitabilityResponse,
  ProjectStatus,
} from '../types/api';

export interface ProjectCreateInput {
  project_code?: string;
  project_name: string;
  customer_id: string;
  po_spk_no?: string;
  po_spk_date?: string;
  original_contract_value: number | string;
  start_date: string;
  target_end_date?: string;
  pic_user_id?: string;
}

export interface VariationOrderInput {
  variation_order_value: number | string;
  notes?: string;
}

export const projectsApi = {
  list: async (status?: ProjectStatus): Promise<ProjectResponse[]> => {
    const params = status ? { status } : {};
    const res = await apiClient.get<ProjectResponse[]>('/projects', { params });
    return res.data;
  },

  get: async (id: string): Promise<ProjectResponse> => {
    const res = await apiClient.get<ProjectResponse>(`/projects/${id}`);
    return res.data;
  },

  create: async (data: ProjectCreateInput): Promise<ProjectResponse> => {
    const res = await apiClient.post<ProjectResponse>('/projects', data);
    return res.data;
  },

  updateStatus: async (id: string, newStatus: ProjectStatus): Promise<ProjectResponse> => {
    const res = await apiClient.patch<ProjectResponse>(`/projects/${id}/status`, {
      project_status: newStatus,
    });
    return res.data;
  },

  getProfitability: async (id: string): Promise<ProjectProfitabilityResponse> => {
    const res = await apiClient.get<ProjectProfitabilityResponse>(`/projects/${id}/financial-summary`);
    return res.data;
  },
};
