import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ProfitLossPage } from '../../src/pages/reports/ProfitLossPage';
import { reportsApi } from '../../src/api/reports';

vi.mock('../../src/api/reports', () => ({
  reportsApi: { getProfitLoss: vi.fn(), downloadReport: vi.fn() },
}));

const section = (code: string, name: string, lines: unknown[], subtotal: string) => ({ section_code: code, section_name: name, lines, subtotal });
const LedgerTarget = () => <div data-testid="ledger-location">{useLocation().search}</div>;

describe('Profit & Loss drill-down', () => {
  it('navigates an account line to General Ledger with account and period filters', async () => {
    vi.mocked(reportsApi.getProfitLoss).mockResolvedValue({
      organization_name: 'PT Test', period_label: 'Current Month', start_date: '2026-08-01', end_date: '2026-08-31', generated_at: '2026-08-30',
      revenue_section: section('REV', 'Pendapatan', [], '100.00'),
      cogs_section: section('COGS', 'HPP', [{ account_code: '5101', line_name: 'Biaya Material', amount: '30.00', drill_down_supported: true }], '30.00'),
      gross_profit: '70.00', gross_margin_percentage: '70.00',
      operating_expenses_section: section('OPEX', 'Beban', [], '0.00'), operating_profit: '70.00',
      other_income_expense_section: section('OTHER', 'Lain', [], '0.00'), earnings_before_tax: '70.00', tax_expense: '0.00', net_profit: '70.00',
    } as never);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/reports/profit-loss']}>
          <Routes>
            <Route path="/reports/profit-loss" element={<ProfitLossPage />} />
            <Route path="/reports/general-ledger" element={<LedgerTarget />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
    fireEvent.click(await screen.findByRole('button', { name: /5101.*Biaya Material/i }));
    const query = await screen.findByTestId('ledger-location');
    expect(query).toHaveTextContent('account_code=5101');
    expect(query).toHaveTextContent('start_date=');
    expect(query).toHaveTextContent('end_date=');
  });
});
