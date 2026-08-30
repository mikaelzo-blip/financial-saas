import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ReportHeader } from '../../src/components/reports/ReportHeader';
import { reportsApi } from '../../src/api/reports';

vi.mock('../../src/api/reports', () => ({
  reportsApi: { downloadReport: vi.fn() },
}));

describe('ReportHeader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    URL.createObjectURL = vi.fn(() => 'blob:report');
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });

  it('downloads an authenticated API blob with current report parameters', async () => {
    vi.mocked(reportsApi.downloadReport).mockResolvedValue({
      blob: new Blob(['xlsx']),
      filename: 'Laporan.xlsx',
    });
    render(<ReportHeader reportType="profit-loss" params={{ start_date: '2026-08-01', end_date: '2026-08-31' }} />);
    fireEvent.click(screen.getByRole('button', { name: /Excel/i }));
    await waitFor(() => expect(reportsApi.downloadReport).toHaveBeenCalledWith('profit-loss', 'xlsx', {
      start_date: '2026-08-01', end_date: '2026-08-31',
    }));
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:report');
  });

  it('shows a recoverable error when export fails', async () => {
    vi.mocked(reportsApi.downloadReport).mockRejectedValue(new Error('network'));
    render(<ReportHeader reportType="balance-sheet" />);
    fireEvent.click(screen.getByRole('button', { name: /PDF/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ekspor PDF gagal');
    expect(screen.getByRole('button', { name: /PDF/i })).toBeEnabled();
  });
});
