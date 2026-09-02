import { apiClient } from './client';
import { UserSession } from '../types/api';

export interface LoginCredentials {
  email: string;
  password: string;
}

interface AuthenticatedUserResponse {
  id: string;
  email: string;
  full_name: string;
  role: 'ADMIN' | 'MANAGER' | 'OPERATOR' | 'VIEWER';
  organization_id: string;
  organization_name: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthenticatedUserResponse;
}

interface SessionResponse {
  user: AuthenticatedUserResponse;
}

const toSession = (user: AuthenticatedUserResponse, accessToken: string): UserSession => {
  if (!user.organization_id || !user.organization_name) {
    throw new Error('Authenticated organization identity is incomplete.');
  }
  return {
    userId: user.id,
    email: user.email,
    fullName: user.full_name,
    role: user.role,
    organizationId: user.organization_id,
    organizationName: user.organization_name,
    accessToken,
  };
};

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<UserSession> => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', credentials);
    return toSession(data.user, data.access_token);
  },
  getSession: async (accessToken: string): Promise<UserSession> => {
    const { data } = await apiClient.get<SessionResponse>('/auth/session');
    return toSession(data.user, accessToken);
  },
};
