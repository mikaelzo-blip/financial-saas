import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { inboxApi } from '../../src/api/inbox';
import { ToastProvider } from '../../src/components/feedback/Toast';
import { WhatsAppInboxPage } from '../../src/pages/inbox/WhatsAppInboxPage';

vi.mock('../../src/api/inbox', () => ({
  inboxApi: {
    listMessages: vi.fn(),
    syncBacklog: vi.fn(),
  },
}));

describe('WhatsApp inbox owner guidance', () => {
  it('states the local-first availability without promising offline capture', async () => {
    vi.mocked(inboxApi.listMessages).mockResolvedValue([]);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter>
            <WhatsAppInboxPage />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText('WhatsApp aktif saat sistem keuangan sedang berjalan.')).toBeInTheDocument();
    expect(screen.queryByText(/offline|backlog|durable|VPS|Worker|D1|R2/i)).not.toBeInTheDocument();
  });
});
