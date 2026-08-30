import React, { useState } from 'react';
import { Download, FileSpreadsheet, FileText } from 'lucide-react';
import { reportsApi, ReportExportFormat, ReportExportType } from '../../api/reports';
import { Button } from '../ui/Button';

interface ReportHeaderProps {
  reportType: ReportExportType;
  params?: Record<string, string | undefined>;
  disabled?: boolean;
}

export const ReportHeader: React.FC<ReportHeaderProps> = ({ reportType, params = {}, disabled = false }) => {
  const [loadingFormat, setLoadingFormat] = useState<ReportExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = async (format: ReportExportFormat) => {
    setLoadingFormat(format);
    setError(null);
    try {
      const result = await reportsApi.downloadReport(reportType, format, params);
      const objectUrl = URL.createObjectURL(result.blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = result.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      setError(`Ekspor ${format.toUpperCase()} gagal. Silakan coba lagi.`);
    } finally {
      setLoadingFormat(null);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex flex-wrap items-center gap-2" aria-label="Ekspor laporan">
        <Button variant="outline" size="sm" onClick={() => download('xlsx')} isLoading={loadingFormat === 'xlsx'} disabled={disabled || loadingFormat !== null} leftIcon={<FileSpreadsheet className="h-4 w-4" />}>
          Excel
        </Button>
        <Button variant="outline" size="sm" onClick={() => download('pdf')} isLoading={loadingFormat === 'pdf'} disabled={disabled || loadingFormat !== null} leftIcon={<FileText className="h-4 w-4" />}>
          PDF
        </Button>
      </div>
      {error && <p role="alert" className="text-xs text-rose-700 flex items-center gap-1"><Download className="h-3 w-3" />{error}</p>}
    </div>
  );
};
