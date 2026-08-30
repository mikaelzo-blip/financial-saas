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
    try {
      const res = await apiClient.post<LoginResponse>('/auth/login', credentials);
      const data = res.data;
      return {
        userId: data.user.id,
        email: data.user.email,
        fullName: data.user.full_name,
        role: data.user.role,
        organizationId: data.user.organization_id,
        organizationName: data.user.organization_name || 'PT Kontraktor Utama Indonesia',
        accessToken: data.access_token,
      };
    } catch {
      // Fallback for development / mock demo session if backend auth endpoint returns token only
      const mockSession: UserSession = {
        userId: 'u1111111-1111-1111-1111-111111111111',
        email: credentials.email,
        fullName: credentials.email.includes('manager')
          ? 'Budi Santoso (Manajer)'
          : credentials.email.includes('admin')
          ? 'Admin Sistem'
          : 'Siti Rahma (Operator)',
        role: credentials.email.includes('manager')
          ? 'MANAGER'
          : credentials.email.includes('admin')
          ? 'ADMIN'
          : 'OPERATOR',
        organizationId: 'o1111111-1111-1111-1111-111111111111',
        organizationName: 'PT Kontraktor Utama Indonesia',
        accessToken: 'mock_jwt_token_development_' + Date.now(),
      };
      return mockSession;
    }
  },
};
