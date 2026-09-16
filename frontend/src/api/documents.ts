import { apiClient } from './client';
import {
  DocumentResponse,
  DocumentOperationsSummaryResponse,
  DocumentOperationalListResponse,
  DocumentOperationsListParams,
  DocumentPostingResponse,
  WhatsAppIntegrationStatusResponse,
} from '../types/api';

export const documentsApi = {
  whatsappStatus: async (): Promise<WhatsAppIntegrationStatusResponse> => {
    const res = await apiClient.get<WhatsAppIntegrationStatusResponse>('/integrations/whatsapp/status');
    return res.data;
  },

  operationsSummary: async (): Promise<DocumentOperationsSummaryResponse> => {
    const res = await apiClient.get<DocumentOperationsSummaryResponse>('/operations/documents/summary');
    return res.data;
  },

  operationsList: async (params?: DocumentOperationsListParams): Promise<DocumentOperationalListResponse> => {
    const res = await apiClient.get<DocumentOperationalListResponse>('/operations/documents', { params });
    return res.data;
  },

  postAccounting: async (id: string): Promise<DocumentPostingResponse> => {
    const res = await apiClient.post<DocumentPostingResponse>(`/documents/${id}/post`);
    return res.data;
  },
  reviewQueue: async (): Promise<DocumentResponse[]> => {
    try {
      const res = await apiClient.get<DocumentResponse[]>('/documents/review-queue');
      return res.data;
    } catch {
      return [];
    }
  },

  list: async (): Promise<DocumentResponse[]> => {
    try {
      const res = await apiClient.get<DocumentResponse[]>('/documents');
      return res.data;
    } catch {
      return [];
    }
  },

  get: async (id: string): Promise<DocumentResponse> => {
    const res = await apiClient.get<DocumentResponse>(`/documents/${id}`);
    return res.data;
  },

  upload: async (file: File, documentType: string = 'UNKNOWN'): Promise<DocumentResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    formData.append('source_channel', 'WEB');

    const res = await apiClient.post<DocumentResponse>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },

  content: async (id: string): Promise<Blob> => {
    const res = await apiClient.get<Blob>(`/documents/${id}/content`, { responseType: 'blob' });
    return res.data;
  },

  correct: async (id: string, changes: Record<string, unknown>, reason: string): Promise<DocumentResponse> => {
    const res = await apiClient.post<DocumentResponse>(`/documents/${id}/corrections`, { changes, reason });
    return res.data;
  },

  approve: async (id: string): Promise<unknown> => {
    const res = await apiClient.post(`/documents/${id}/approve`);
    return res.data;
  },

  reject: async (id: string, reason: string): Promise<DocumentResponse> => {
    const res = await apiClient.post<DocumentResponse>(`/documents/${id}/reject`, { reason });
    return res.data;
  },

  retry: async (id: string): Promise<DocumentResponse> => {
    const res = await apiClient.post<DocumentResponse>(`/documents/${id}/retry`);
    return res.data;
  },
};
