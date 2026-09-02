import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../../src/App';
import { authApi } from '../../src/api/auth';

vi.mock('../../src/pages/reports/ProfitLossPage', () => ({ ProfitLossPage: () => <h1>Profit Loss Route</h1> }));
vi.mock('../../src/pages/reports/BalanceSheetPage', () => ({ BalanceSheetPage: () => <h1>Balance Sheet Route</h1> }));
vi.mock('../../src/pages/reports/CashFlowPage', () => ({ CashFlowPage: () => <h1>Cash Flow Route</h1> }));
vi.mock('../../src/pages/reports/TrialBalancePage', () => ({ TrialBalancePage: () => <h1>Trial Balance Route</h1> }));
vi.mock('../../src/pages/reports/GeneralLedgerPage', () => ({ GeneralLedgerPage: () => <h1>General Ledger Route</h1> }));
vi.mock('../../src/pages/reports/ARAgingPage', () => ({ ARAgingPage: () => <h1>AR Aging Route</h1> }));
vi.mock('../../src/pages/reports/APAgingPage', () => ({ APAgingPage: () => <h1>AP Aging Route</h1> }));
vi.mock('../../src/pages/reports/ProjectProfitabilityPage', () => ({ ProjectProfitabilityPage: () => <h1>Project Profitability Route</h1> }));
vi.mock('../../src/pages/reports/ProjectCashPositionPage', () => ({ ProjectCashPositionPage: () => <h1>Project Cash Route</h1> }));
vi.mock('../../src/pages/reports/BudgetVsActualPage', () => ({ BudgetVsActualPage: () => <h1>Budget Route</h1> }));

describe('reporting routes and sidebar navigation', () => {
  beforeEach(() => {
    const session = {
      userId: 'manager', email: 'manager@example.test', fullName: 'Manager', role: 'MANAGER' as const,
      organizationId: 'org-a', organizationName: 'PT Route Test', accessToken: 'token',
    };
    localStorage.setItem('financial_user_session', JSON.stringify(session));
    vi.spyOn(authApi, 'getSession').mockResolvedValue(session);
  });

  it.each([
    ['/reports/profit-loss', 'Profit Loss Route'],
    ['/reports/balance-sheet', 'Balance Sheet Route'],
    ['/reports/cash-flow', 'Cash Flow Route'],
    ['/reports/trial-balance', 'Trial Balance Route'],
    ['/reports/general-ledger', 'General Ledger Route'],
    ['/reports/receivables', 'AR Aging Route'],
    ['/reports/payables', 'AP Aging Route'],
    ['/reports/project-profitability', 'Project Profitability Route'],
    ['/reports/project-cash', 'Project Cash Route'],
    ['/reports/budget-vs-actual', 'Budget Route'],
  ])('renders %s', async (path, heading) => {
    window.history.pushState({}, '', path);
    render(<App />);
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
  });

  it('exposes every reporting destination in the sidebar', async () => {
    window.history.pushState({}, '', '/reports/profit-loss');
    render(<App />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Profit Loss Route' })).toBeInTheDocument());
    const expected = ['/reports/profit-loss', '/reports/balance-sheet', '/reports/cash-flow', '/reports/trial-balance', '/reports/general-ledger', '/reports/receivables', '/reports/payables', '/reports/project-profitability', '/reports/project-cash', '/reports/budget-vs-actual'];
    const hrefs = screen.getAllByRole('link').map((link) => link.getAttribute('href'));
    expected.forEach((href) => expect(hrefs).toContain(href));
  });
});
