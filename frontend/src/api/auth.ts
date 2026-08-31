import { apiClient } from './client';
import { UserSession } from '../types/api';

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    role: 'ADMIN' | 'MANAGER' | 'OPERATOR' | 'VIEWER';
    organization_id: string;
    organization_name?: string;
  };
}

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<UserSession> => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', credentials);
    return {
      userId: data.user.id,
      email: data.user.email,
      fullName: data.user.full_name,
      role: data.user.role,
      organizationId: data.user.organization_id,
      organizationName: data.user.organization_name || data.user.email,
      accessToken: data.access_token,
    };
  },
};
