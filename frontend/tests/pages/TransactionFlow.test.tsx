import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { TransactionForm } from '../../src/components/forms/TransactionForm';

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe('TransactionFlow Form', () => {
  it('renders natural business fields without debit or credit labels', () => {
    const queryClient = createTestQueryClient();
    const handleSubmit = vi.fn();

    render(
      <QueryClientProvider client={queryClient}>
        <TransactionForm onSubmit={handleSubmit} />
      </QueryClientProvider>
    );

    // Verify natural fields exist
    expect(screen.getByText('Jenis Transaksi *')).toBeInTheDocument();
    expect(screen.getByText('Nominal Transaksi (Rp) *')).toBeInTheDocument();
    expect(screen.getByText('Tanggal Transaksi *')).toBeInTheDocument();

    // Verify DEBIT / KREDIT terms are NOT exposed to end user
    expect(screen.queryByText('Pilih Debit')).toBeNull();
    expect(screen.queryByText('Pilih Kredit')).toBeNull();
  });

  it('toggles multi-project split mode when clicked', () => {
    const queryClient = createTestQueryClient();
    const handleSubmit = vi.fn();

    render(
      <QueryClientProvider client={queryClient}>
        <TransactionForm onSubmit={handleSubmit} />
      </QueryClientProvider>
    );

    const splitToggleBtn = screen.getByText('Bagi Multi-Proyek');
    fireEvent.click(splitToggleBtn);

    expect(screen.getByText('Mode Multi-Proyek Aktif')).toBeInTheDocument();
    expect(screen.getByText('Tambah Alokasi Proyek')).toBeInTheDocument();
  });
});
