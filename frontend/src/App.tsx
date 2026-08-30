import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './api/queryClient';
import { AuthProvider } from './store/AuthContext';
import { ToastProvider } from './components/feedback/Toast';
import { ProtectedRoute } from './router/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/auth/LoginPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { ProjectListPage } from './pages/projects/ProjectListPage';
import { ProjectCreatePage } from './pages/projects/ProjectCreatePage';
import { ProjectDetailPage } from './pages/projects/ProjectDetailPage';
import { CustomerListPage } from './pages/master/CustomerListPage';
import { VendorListPage } from './pages/master/VendorListPage';
import { PaymentAccountsPage } from './pages/master/PaymentAccountsPage';
import { ChartOfAccountsPage } from './pages/master/ChartOfAccountsPage';
import { TransactionListPage } from './pages/transactions/TransactionListPage';
import { TransactionCreatePage } from './pages/transactions/TransactionCreatePage';
import { TransactionDetailPage } from './pages/transactions/TransactionDetailPage';
import { DocumentListPage } from './pages/documents/DocumentListPage';
import { ReceivablesPage } from './pages/receivables/ReceivablesPage';
import { PayablesPage } from './pages/payables/PayablesPage';
import { ReviewQueuePage } from './pages/review/ReviewQueuePage';
import { SettingsPage } from './pages/settings/SettingsPage';
import { TrialBalancePage } from './pages/reports/TrialBalancePage';
import { GeneralLedgerPage } from './pages/reports/GeneralLedgerPage';
import { ProfitLossPage } from './pages/reports/ProfitLossPage';
import { BalanceSheetPage } from './pages/reports/BalanceSheetPage';
import { CashFlowPage } from './pages/reports/CashFlowPage';
import { ARAgingPage } from './pages/reports/ARAgingPage';
import { APAgingPage } from './pages/reports/APAgingPage';
import { ProjectProfitabilityPage } from './pages/reports/ProjectProfitabilityPage';
import { ProjectCashPositionPage } from './pages/reports/ProjectCashPositionPage';
import { BudgetVsActualPage } from './pages/reports/BudgetVsActualPage';

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />

              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                
                {/* Projects */}
                <Route path="projects" element={<ProjectListPage />} />
                <Route path="projects/new" element={<ProjectCreatePage />} />
                <Route path="projects/:id" element={<ProjectDetailPage />} />
                
                {/* Master Data */}
                <Route path="customers" element={<CustomerListPage />} />
                <Route path="vendors" element={<VendorListPage />} />
                <Route path="payment-accounts" element={<PaymentAccountsPage />} />
                <Route path="chart-of-accounts" element={<ChartOfAccountsPage />} />

                {/* Transactions & Documents */}
                <Route path="transactions" element={<TransactionListPage />} />
                <Route path="transactions/new" element={<TransactionCreatePage />} />
                <Route path="transactions/:id" element={<TransactionDetailPage />} />
                <Route path="documents" element={<DocumentListPage />} />

                {/* AR, AP & Review Queue */}
                <Route path="receivables" element={<ReceivablesPage />} />
                <Route path="payables" element={<PayablesPage />} />
                <Route path="review-queue" element={<ReviewQueuePage />} />

                {/* Financial Reports */}
                <Route path="reports/profit-loss" element={<ProfitLossPage />} />
                <Route path="reports/balance-sheet" element={<BalanceSheetPage />} />
                <Route path="reports/cash-flow" element={<CashFlowPage />} />
                <Route path="reports/trial-balance" element={<TrialBalancePage />} />
                <Route path="reports/general-ledger" element={<GeneralLedgerPage />} />
                <Route path="reports/ar-aging" element={<ARAgingPage />} />
                <Route path="reports/ap-aging" element={<APAgingPage />} />
                <Route path="reports/project-profitability" element={<ProjectProfitabilityPage />} />
                <Route path="reports/project-cash" element={<ProjectCashPositionPage />} />
                <Route path="reports/budget-vs-actual" element={<BudgetVsActualPage />} />

                {/* Settings & Audit */}
                <Route path="settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
