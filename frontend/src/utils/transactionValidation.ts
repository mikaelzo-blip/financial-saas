import { TransactionAllocationInput } from '../api/transactions';

export interface ValidationResult {
  isValid: boolean;
  allocationSum: number;
  totalNominal: number;
  difference: number;
  errorMessage?: string;
}

export function validateAllocationSum(
  nominal: number | string,
  allocations: TransactionAllocationInput[]
): ValidationResult {
  const total = typeof nominal === 'string' ? parseFloat(nominal) || 0 : nominal || 0;

  if (allocations.length === 0) {
    return {
      isValid: true,
      allocationSum: total,
      totalNominal: total,
      difference: 0,
    };
  }

  const sum = allocations.reduce((acc, curr) => {
    const itemAmount = typeof curr.amount === 'string' ? parseFloat(curr.amount) || 0 : curr.amount || 0;
    return acc + itemAmount;
  }, 0);

  const roundedSum = Math.round(sum * 100) / 100;
  const roundedTotal = Math.round(total * 100) / 100;
  const diff = Math.round((roundedTotal - roundedSum) * 100) / 100;

  if (Math.abs(diff) > 0.001) {
    return {
      isValid: false,
      allocationSum: roundedSum,
      totalNominal: roundedTotal,
      difference: diff,
      errorMessage: `Total alokasi proyek (Rp ${roundedSum.toLocaleString('id-ID')}) belum sama dengan nominal transaksi (Rp ${roundedTotal.toLocaleString('id-ID')}). Selisih: Rp ${diff.toLocaleString('id-ID')}.`,
    };
  }

  return {
    isValid: true,
    allocationSum: roundedSum,
    totalNominal: roundedTotal,
    difference: 0,
  };
}
