import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../../src/store/AuthContext';
import { ExecutiveSummaryCard } from '../../src/components/ai/ExecutiveSummaryCard';
import { insightsApi, type Insight } from '../../src/api/insights';
import { authApi } from '../../src/api/auth';

vi.mock('../../src/api/insights', () => ({ insightsApi: { executive: vi.fn() } }));

const result: Insight = {
  organization_id: 'org-a',
  headline: 'Ringkasan pengujian', factual_metrics: { revenue: '1000000000.01', cash_balance: null },
  analytical_narrative: 'Interpretasi terverifikasi.', actionable_recommendations: ['Tinjau laporan.'],
  confidence_score: 'HIGH', period_label: 'Agustus 2026', data_as_of: '2026-08-31',
  generated_at: '2026-08-31T00:00:00Z', source_references: ['ProfitLossReportResponse'],
  metric_sources: { revenue: 'ProfitLossReportResponse.revenue_section.subtotal' }, unavailable_metrics: ['cash_balance'],
  anomalies_detected: [], provider_metadata: { provider: 'DETERMINISTIC_FALLBACK', cached: false, latency_ms: 1, tokens_used: 0 },
};

beforeEach(() => {
  vi.clearAllMocks();
  const session = {
    userId: 'user-a', email: 'user@example.test', fullName: 'User', role: 'MANAGER' as const,
    organizationId: 'org-a', organizationName: 'Organization A', accessToken: 'test',
  };
  localStorage.setItem('financial_user_session', JSON.stringify(session));
  vi.spyOn(authApi, 'getSession').mockResolvedValue(session);
});

function mount() {
  return render(<AuthProvider><QueryClientProvider client={new QueryClient({defaultOptions: {queries: {retry: false}}})}><ExecutiveSummaryCard /></QueryClientProvider></AuthProvider>);
}

it('renders exact facts separately, sources and fallback, and selects a period', async () => {
  vi.mocked(insightsApi.executive).mockResolvedValue(result);
  mount();
  expect(await screen.findByText('Ringkasan pengujian')).toBeInTheDocument();
  expect(screen.getByText('1000000000.01')).toBeInTheDocument();
  expect(screen.getByText('Data tidak tersedia')).toBeInTheDocument();
  expect(screen.getByText('Fallback deterministik')).toBeInTheDocument();
  expect(screen.getByText('Fakta laporan')).toBeInTheDocument();
  expect(screen.getByText('Interpretasi advisory')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Mulai periode'), {target:{value:'2026-07-01'}});
  await waitFor(() => expect(insightsApi.executive).toHaveBeenLastCalledWith(expect.objectContaining({start_date:'2026-07-01'}), expect.any(AbortSignal)));
});

it('shows loading and recoverable error states', async () => {
  vi.mocked(insightsApi.executive).mockRejectedValue(new Error('Unavailable'));
  mount();
  expect(await screen.findByRole('alert')).toHaveTextContent('Ringkasan tidak tersedia');
  expect(screen.getByRole('button', {name:'Coba lagi'})).toBeInTheDocument();
});
