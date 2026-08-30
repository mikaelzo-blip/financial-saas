import { apiClient } from './client';
import {
  IntegrityReportResponse,
  TrialBalanceResponse,
  GeneralLedgerResponse,
  ProfitLossReportResponse,
  BalanceSheetReportResponse,
  CashFlowReportResponse,
  ARAgingReportResponse,
  APAgingReportResponse,
  ProjectProfitabilityReportResponse,
  ProjectCashPositionReportResponse,
  BudgetVsActualReportResponse,
  DashboardSummaryResponse
} from '../types/reporting';

export type ReportExportType =
  | 'profit-loss'
  | 'balance-sheet'
  | 'cash-flow'
  | 'trial-balance'
  | 'general-ledger'
  | 'receivables-aging'
  | 'payables-aging'
  | 'project-profitability';

export type ReportExportFormat = 'xlsx' | 'pdf';

export interface ReportDownload {
  blob: Blob;
  filename: string;
}

const filenameFromDisposition = (value: string | undefined, fallback: string): string => {
  const match = value?.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
  return match ? decodeURIComponent(match[1].replace(/"$/, '')) : fallback;
};

export const reportsApi = {
  downloadReport: async (
    reportType: ReportExportType,
    format: ReportExportFormat,
    params: Record<string, string | undefined> = {}
  ): Promise<ReportDownload> => {
    const response = await apiClient.get<Blob>(`/reports/export/${reportType}`, {
      params: { ...params, format },
      responseType: 'blob',
    });
    return {
      blob: response.data,
      filename: filenameFromDisposition(
        response.headers['content-disposition'],
        `${reportType}.${format}`
      ),
    };
  },
  getIntegrityReport: async (asOfDate?: string): Promise<IntegrityReportResponse> => {
    const params = asOfDate ? { as_of_date: asOfDate } : {};
    const res = await apiClient.get<IntegrityReportResponse>('/reports/integrity', { params });
    return res.data;
  },

  getDashboardSummary: async (asOfDate?: string): Promise<DashboardSummaryResponse> => {
    const params = asOfDate ? { as_of_date: asOfDate } : {};
    const res = await apiClient.get<DashboardSummaryResponse>('/reports/dashboard', { params });
    return res.data;
  },

  getTrialBalance: async (startDate?: string, endDate?: string, asOfDate?: string): Promise<TrialBalanceResponse> => {
    const params: Record<string, string> = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    if (asOfDate) params.as_of_date = asOfDate;
    const res = await apiClient.get<TrialBalanceResponse>('/reports/trial-balance', { params });
    return res.data;
  },

  getGeneralLedger: async (
    accountCode: string,
    startDate: string,
    endDate: string,
    projectId?: string
  ): Promise<GeneralLedgerResponse> => {
    const params: Record<string, string> = {
      account_code: accountCode,
      start_date: startDate,
      end_date: endDate,
    };
    if (projectId) params.project_id = projectId;
    const res = await apiClient.get<GeneralLedgerResponse>('/reports/general-ledger', { params });
    return res.data;
  },

  getProfitLoss: async (
    startDate?: string,
    endDate?: string,
    compareWith?: string
  ): Promise<ProfitLossReportResponse> => {
    const params: Record<string, string> = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    if (compareWith) params.compare_with = compareWith;
    const res = await apiClient.get<ProfitLossReportResponse>('/reports/profit-loss', { params });
    return res.data;
  },

  getBalanceSheet: async (asOfDate?: string): Promise<BalanceSheetReportResponse> => {
    const params = asOfDate ? { as_of_date: asOfDate } : {};
    const res = await apiClient.get<BalanceSheetReportResponse>('/reports/balance-sheet', { params });
    return res.data;
  },

  getCashFlow: async (startDate?: string, endDate?: string): Promise<CashFlowReportResponse> => {
    const params: Record<string, string> = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const res = await apiClient.get<CashFlowReportResponse>('/reports/cash-flow', { params });
    return res.data;
  },

  getARAging: async (asOfDate?: string): Promise<ARAgingReportResponse> => {
    const params = asOfDate ? { as_of_date: asOfDate } : {};
    const res = await apiClient.get<ARAgingReportResponse>('/reports/receivables-aging', { params });
    return res.data;
  },

  getAPAging: async (asOfDate?: string): Promise<APAgingReportResponse> => {
    const params = asOfDate ? { as_of_date: asOfDate } : {};
    const res = await apiClient.get<APAgingReportResponse>('/reports/payables-aging', { params });
    return res.data;
  },

  getProjectProfitability: async (projectId: string): Promise<ProjectProfitabilityReportResponse> => {
    const res = await apiClient.get<ProjectProfitabilityReportResponse>('/reports/project-profitability', {
      params: { project_id: projectId },
    });
    return res.data;
  },

  getProjectCashPosition: async (projectId: string): Promise<ProjectCashPositionReportResponse> => {
    const res = await apiClient.get<ProjectCashPositionReportResponse>('/reports/project-cash', {
      params: { project_id: projectId },
    });
    return res.data;
  },

  getBudgetVsActual: async (projectId: string): Promise<BudgetVsActualReportResponse> => {
    const res = await apiClient.get<BudgetVsActualReportResponse>('/reports/budget-vs-actual', {
      params: { project_id: projectId },
    });
    return res.data;
  },
};
