import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ApprovalActionControls } from '../../src/pages/review/components/ApprovalActionControls';
import { AuthProvider } from '../../src/store/AuthContext';

describe('ReviewFlow Approval Controls', () => {
  it('renders approval controls with unresolved flags count', () => {
    const handleApprove = vi.fn();
    const handleReject = vi.fn();

    render(
      <AuthProvider>
        <ApprovalActionControls
          onApprove={handleApprove}
          onReject={handleReject}
          unresolvedFlagsCount={2}
        />
      </AuthProvider>
    );

    expect(screen.getByText('Aksi Keputusan Manajer')).toBeInTheDocument();
    expect(screen.getByText('Terdapat 2 flag review yang masih belum terselesaikan.')).toBeInTheDocument();
    expect(screen.getByText('Tolak Transaksi')).toBeInTheDocument();
  });
});
