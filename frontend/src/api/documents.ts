import { apiClient } from './client';
import { DocumentResponse } from '../types/api';

export const documentsApi = {
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

  retry: async (id: string): Promise<DocumentResponse> => {
    const res = await apiClient.post<DocumentResponse>(`/documents/${id}/retry`);
    return res.data;
  },
};
