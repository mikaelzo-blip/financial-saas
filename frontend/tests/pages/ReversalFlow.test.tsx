import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TransactionReversalModal } from '../../src/components/transactions/TransactionReversalModal';

describe('ReversalFlow Modal', () => {
  it('renders reversal reason input and enforces non-destructive notice', () => {
    const handleConfirm = vi.fn();
    const handleClose = vi.fn();

    render(
      <TransactionReversalModal
        isOpen={true}
        onClose={handleClose}
        onConfirm={handleConfirm}
        transactionCode="TRX-2026-0001"
      />
    );

    expect(screen.getByText('Batalkan Transaksi — TRX-2026-0001')).toBeInTheDocument();
    expect(
      screen.getByText(/Transaksi yang sudah diposting tidak akan dihapus dari basis data/i)
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Salah input nominal nota/i)).toBeInTheDocument();
  });
});
