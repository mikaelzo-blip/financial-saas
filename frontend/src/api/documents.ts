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

  upload: async (file: File, documentType: string = 'OTHER'): Promise<DocumentResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    formData.append('source_channel', 'WEB_UPLOAD');

    const res = await apiClient.post<DocumentResponse>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return res.data;
  },
};
