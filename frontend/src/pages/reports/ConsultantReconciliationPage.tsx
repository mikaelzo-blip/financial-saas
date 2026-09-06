import React, { useState, useEffect } from 'react';
import {
  FileText,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Upload,
  RefreshCw,
} from 'lucide-react';
import {
  reconcileVerified,
  uploadStatement,
} from '../../api/consultantReconciliation';
import {
  ConsultantReconciliationReport,
  LineItemComparison,
} from '../../types/reporting';

export const ConsultantReconciliationPage: React.FC = () => {
  const [selectedYear, setSelectedYear] = useState<number>(2025);
  const [report, setReport] = useState<ConsultantReconciliationReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await reconcileVerified(selectedYear);
        if (active) setReport(data);
      } catch (err: any) {
        if (active) {
          setError(
            err.response?.data?.detail ||
              'Gagal memuat rekonsiliasi laporan konsultan.'
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [selectedYear]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const data = await uploadStatement(file);
      setReport(data);
      if (data.year) {
        setSelectedYear(data.year);
      }
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          'Gagal mengunggah dan memproses file laporan konsultan.'
      );
    } finally {
      setUploading(false);
      // Reset file input
      e.target.value = '';
    }
  };

  const formatCurrency = (amount: number | string | undefined) => {
    if (amount === undefined || amount === null) return 'Rp 0';
    const num = typeof amount === 'string' ? parseFloat(amount) : amount;
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(num);
  };

  const getBadge = (classification: LineItemComparison['classification']) => {
    switch (classification) {
      case 'MATCH':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
            <CheckCircle2 className="w-3 h-3 mr-1" /> Cocok
          </span>
        );
      case 'CONSULTANT_REPORT_DIFFERENCE':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
            <AlertTriangle className="w-3 h-3 mr-1" /> Selisih Konsultan
          </span>
        );
      case 'MISSING_DATA':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
            <HelpCircle className="w-3 h-3 mr-1" /> Belum Diinput
          </span>
        );
      case 'FISCAL_DIFFERENCE':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
            Selisih Fiskal
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
            Selisih Pemetaan
          </span>
        );
    }
  };

  const renderComparisonTable = (
    title: string,
    items: LineItemComparison[]
  ) => (
    <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden mb-8">
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
        <h3 className="text-base font-semibold text-gray-900">{title}</h3>
        <span className="text-xs text-gray-500 font-normal">
          Perbandingan Angka Konsultan vs Sistem Keuangan SaaS
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                Pos Akun / Keterangan
              </th>
              <th className="px-6 py-3 text-right font-medium text-gray-500 uppercase tracking-wider">
                Laporan Konsultan
              </th>
              <th className="px-6 py-3 text-right font-medium text-gray-500 uppercase tracking-wider">
                Sistem Keuangan SaaS
              </th>
              <th className="px-6 py-3 text-right font-medium text-gray-500 uppercase tracking-wider">
                Selisih (SaaS - Konsultan)
              </th>
              <th className="px-6 py-3 text-center font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                Catatan Analisis
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {items.map((item) => {
              const isHighlight =
                item.item_key.includes('TOTAL') ||
                item.item_key.includes('PROFIT') ||
                item.item_key.includes('EARNINGS');
              return (
                <tr
                  key={item.item_key}
                  className={isHighlight ? 'bg-gray-50 font-semibold' : 'hover:bg-gray-50'}
                >
                  <td className="px-6 py-3 text-gray-900">
                    <div>{item.label_id}</div>
                    <div className="text-xs text-gray-500 font-normal">{item.label_en}</div>
                  </td>
                  <td className="px-6 py-3 text-right text-gray-900 font-mono">
                    {formatCurrency(item.consultant_amount)}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-900 font-mono">
                    {formatCurrency(item.saas_amount)}
                  </td>
                  <td
                    className={`px-6 py-3 text-right font-mono ${
                      Number(item.variance) === 0
                        ? 'text-gray-500'
                        : Number(item.variance) > 0
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`}
                  >
                    {formatCurrency(item.variance)}
                  </td>
                  <td className="px-6 py-3 text-center">{getBadge(item.classification)}</td>
                  <td className="px-6 py-3 text-xs text-gray-600">
                    {item.notes || '-'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileText className="w-7 h-7 text-indigo-600" />
            Rekonsiliasi Laporan Konsultan Keuangan
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Bandingkan angka laporan keuangan konsultan pajak (SPT) dengan buku besar sistem SaaS tanpa plug journal.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer">
            <Upload className="w-4 h-4 mr-2 text-gray-500" />
            {uploading ? 'Mengunggah...' : 'Upload PDF Konsultan'}
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFileUpload}
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {/* Year Selector Buttons */}
      <div className="flex items-center gap-2 bg-gray-100 p-1.5 rounded-lg w-fit">
        {[2023, 2024, 2025].map((year) => (
          <button
            key={year}
            onClick={() => setSelectedYear(year)}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              selectedYear === year
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Tahun {year}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="p-12 flex justify-center items-center text-gray-500 gap-2">
          <RefreshCw className="w-5 h-5 animate-spin" />
          Memuat data rekonsiliasi tahun {selectedYear}...
        </div>
      ) : report ? (
        <>
          {/* Internal Consultant Integrity Discrepancy Warning */}
          {!report.statement_integrity.is_balanced && (
            <div className="p-4 bg-amber-50 border-l-4 border-amber-500 rounded-r-lg shadow-sm">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-amber-900">
                    Peringatan Integritas Laporan Konsultan ({report.year})
                  </h4>
                  <p className="text-xs text-amber-700">
                    Laporan keuangan dari konsultan memiliki selisih aritmatika internal. Sistem SaaS mencatat selisih asli secara transparan tanpa memasukkan jurnal penyeimbang (no synthetic plug entries).
                  </p>
                  <ul className="list-disc list-inside text-xs text-amber-800 space-y-0.5 mt-2">
                    {report.statement_integrity.findings.map((f, idx) => (
                      <li key={idx}>{f}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
              <div className="text-xs font-medium text-gray-500">Total Pos Akun</div>
              <div className="text-2xl font-bold text-gray-900 mt-1">
                {report.summary.total_items_compared}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                Sumber: {report.consultant_data.source_document_name || 'Laporan Konsultan'}
              </div>
            </div>

            <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
              <div className="text-xs font-medium text-gray-500">Angka Cocok (Match)</div>
              <div className="text-2xl font-bold text-green-600 mt-1">
                {report.summary.match_count}
              </div>
              <div className="text-xs text-green-600 mt-1">Tepat sama dengan buku besar</div>
            </div>

            <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
              <div className="text-xs font-medium text-gray-500">Belum Diinput / Beda Pemetaan</div>
              <div className="text-2xl font-bold text-amber-600 mt-1">
                {report.summary.missing_data_count + report.summary.difference_count}
              </div>
              <div className="text-xs text-amber-600 mt-1">Memerlukan input / penjurnalan</div>
            </div>

            <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
              <div className="text-xs font-medium text-gray-500">Status Aritmatika Konsultan</div>
              <div
                className={`text-xl font-bold mt-1 ${
                  report.statement_integrity.is_balanced ? 'text-green-600' : 'text-amber-600'
                }`}
              >
                {report.statement_integrity.is_balanced ? 'Tersambung (Tie)' : 'Selisih Internal'}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {report.statement_integrity.is_balanced
                  ? 'Aktiva = Passiva'
                  : `Selisih Rp ${Number(report.statement_integrity.assets_liabilities_equity_discrepancy).toLocaleString('id-ID')}`}
              </div>
            </div>
          </div>

          {/* Tables */}
          {renderComparisonTable(
            `1. Laporan Laba Rugi Komparatif (${report.year})`,
            report.pl_comparisons
          )}
          {renderComparisonTable(
            `2. Neraca / Posisi Keuangan Komparatif (${report.year})`,
            report.bs_comparisons
          )}
        </>
      ) : null}
    </div>
  );
};
