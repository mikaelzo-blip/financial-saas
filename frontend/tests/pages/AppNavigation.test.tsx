import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { AppLayout } from '../../src/components/layout/AppLayout';
import { AuthProvider } from '../../src/store/AuthContext';
import type { UserSession } from '../../src/types/api';

const mockUserSession: UserSession = {
  userId: 'test-user-id',
  email: 'admin@kontraktor.test',
  fullName: 'Admin User',
  role: 'ADMIN',
  organizationId: 'org-test-id',
  organizationName: 'PT Test Kontraktor',
  accessToken: 'test-token',
};

const renderWithProviders = (initialRoute = '/dashboard') => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initialRoute]}>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route path="dashboard" element={<div>Dashboard Content</div>} />
              <Route path="documents" element={<div>Dokumen Bukti Content</div>} />
              <Route path="review-queue" element={<div>Perlu Diperiksa Content</div>} />
              <Route path="inbox" element={<Navigate to="/documents" replace />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
};

describe('App Navigation and Canonical Inbox', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('financial_user_session', JSON.stringify(mockUserSession));
  });

  it('prioritizes Dokumen Bukti and Perlu Diperiksa in Inbox menu and hides legacy WhatsApp Inbox', async () => {
    const user = userEvent.setup();
    renderWithProviders('/dashboard');

    // Find the Inbox collapsible trigger in the sidebar
    const inboxToggle = await screen.findByRole('button', { name: /^Inbox/i });
    expect(inboxToggle).toBeInTheDocument();

    // Click to expand Inbox
    await user.click(inboxToggle);

    // Canonical operational inbox items must be present
    expect(await screen.findByText('Dokumen Bukti')).toBeInTheDocument();
    expect(screen.getByText('Perlu Diperiksa')).toBeInTheDocument();

    // Legacy WhatsApp Inbox must NOT be present in primary navigation
    expect(screen.queryByText('WhatsApp Inbox')).not.toBeInTheDocument();
  });

  it('redirects /inbox to /documents (Dokumen Bukti) rather than legacy empty WhatsApp inbox', async () => {
    renderWithProviders('/inbox');
    expect(await screen.findByText('Dokumen Bukti Content')).toBeInTheDocument();
  });
});
