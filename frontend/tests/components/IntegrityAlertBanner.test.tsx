import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { IntegrityAlertBanner } from '../../src/components/reports/IntegrityAlertBanner';

describe('IntegrityAlertBanner Component', () => {
  it('renders green valid badge when isBalanced is true', () => {
    render(<IntegrityAlertBanner isBalanced={true} />);
    expect(screen.getByText(/Integritas Keuangan Valid/i)).toBeInTheDocument();
  });

  it('renders prominent red alert when isBalanced is false', () => {
    render(
      <IntegrityAlertBanner
        isBalanced={false}
        difference={500000}
        message="Neraca Tidak Seimbang"
      />
    );
    expect(screen.getByText(/PERINGATAN INTEGRITAS LAPORAN KEUANGAN/i)).toBeInTheDocument();
    expect(screen.getByText(/Neraca Tidak Seimbang/i)).toBeInTheDocument();
  });
});
