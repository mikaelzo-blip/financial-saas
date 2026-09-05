import { apiClient } from './client';
import { InboxMessage, InboxMessageStatus } from '../types/api';

export interface SyncBacklogResponse {
  messages: InboxMessage[];
}

export const inboxApi = {
  listMessages: async (statusFilter?: InboxMessageStatus, limit = 50, offset = 0): Promise<InboxMessage[]> => {
    const params = new URLSearchParams();
    if (statusFilter) {
      params.append('status_filter', statusFilter);
    }
    params.append('limit', String(limit));
    params.append('offset', String(offset));

    const response = await apiClient.get<InboxMessage[]>(`/api/v1/inbox/messages?${params.toString()}`);
    return response.data;
  },

  syncBacklog: async (): Promise<InboxMessage[]> => {
    const response = await apiClient.post<InboxMessage[]>('/api/v1/inbox/sync');
    return response.data;
  },
};
