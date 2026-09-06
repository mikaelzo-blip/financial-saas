import { apiClient } from './client';
import {
  ConsultantFinancialStatementData,
  ConsultantReconciliationReport,
} from '../types/reporting';

export const getVerifiedStatement = async (year: number): Promise<ConsultantFinancialStatementData> => {
  const response = await apiClient.get<ConsultantFinancialStatementData>(
    `/reports/consultant-reconciliation/verified/${year}`
  );
  return response.data;
};

export const reconcileVerified = async (year: number): Promise<ConsultantReconciliationReport> => {
  const response = await apiClient.post<ConsultantReconciliationReport>(
    `/reports/consultant-reconciliation/reconcile-verified/${year}`
  );
  return response.data;
};

export const compareStatement = async (
  data: ConsultantFinancialStatementData
): Promise<ConsultantReconciliationReport> => {
  const response = await apiClient.post<ConsultantReconciliationReport>(
    '/reports/consultant-reconciliation/compare',
    data
  );
  return response.data;
};

export const uploadStatement = async (file: File): Promise<ConsultantReconciliationReport> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post<ConsultantReconciliationReport>(
    '/reports/consultant-reconciliation/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};
