/**
 * Financial and Date Formatting Utilities for Indonesian Contractor SaaS
 */

export function formatIDR(amount: number | string | undefined | null): string {
  if (amount === undefined || amount === null || amount === '') {
    return 'Rp 0';
  }
  const numericVal = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(numericVal)) {
    return 'Rp 0';
  }

  const fractionDigits = Number.isInteger(numericVal) ? 0 : 2;
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(numericVal).replace(/\u00a0/g, ' ');
}

export function formatCompactIDR(amount: number | string | undefined | null): string {
  if (amount === undefined || amount === null || amount === '') {
    return 'Rp 0';
  }
  const numericVal = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(numericVal)) {
    return 'Rp 0';
  }

  const absVal = Math.abs(numericVal);
  if (absVal >= 1_000_000_000) {
    return `Rp ${(numericVal / 1_000_000_000).toFixed(2)} M`;
  }
  if (absVal >= 1_000_000) {
    return `Rp ${(numericVal / 1_000_000).toFixed(2)} Jt`;
  }
  if (absVal >= 1_000) {
    return `Rp ${(numericVal / 1_000).toFixed(0)} Rb`;
  }
  return formatIDR(numericVal);
}

export function formatDate(dateString: string | undefined | null): string {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return new Intl.DateTimeFormat('id-ID', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date);
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString: string | undefined | null): string {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return new Intl.DateTimeFormat('id-ID', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  } catch {
    return dateString;
  }
}
